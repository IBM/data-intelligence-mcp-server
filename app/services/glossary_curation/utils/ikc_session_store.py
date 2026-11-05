# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""IKC project asset-files implementation of AbstractSessionStore.

All files are stored as raw asset files under:
  data_asset/gc-{filename}

inside the IKC project supplied to the constructor (resolved from
``start.project_id`` or ``start.project_name``).

The flat data_asset/ prefix (one path level, no subdirectory) is the only
layout CPD's asset-files API persists reliably.  A two-level path such as
data_asset/glossary-curation/{filename} produces a 200 on PUT but a 404 on
any subsequent GET — the file is never durably committed.

Write durability pattern
------------------------
1. PUT the file via /v2/asset_files/.
2. Poll the file's own GET until it returns 200 — confirms the object is
   durably committed to CPD's object storage (eventually consistent PUT).
3. POST /v2/assets to register a CAMS entry — anchors ownership so CPD GC
   does not evict the file between sessions.
Without step 2, CAMS registration races object-storage commit and the file may
disappear minutes after write (observed with chunk files).
"""

import asyncio
import json
from typing import Optional
from urllib.parse import quote

from app.services.glossary_curation.utils.abstract_session_store import (
    AbstractSessionStore,
)
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service

_PREFIX = "data_asset"
_GC_FILENAME_PREFIX = "gc-"
_NOT_FOUND = "not found"

# Polling config for post-PUT storage readability confirmation
_PUT_MAX_RETRIES = 10
_PUT_INITIAL_DELAY = 1.0  # seconds
_PUT_MAX_DELAY = 30.0  # seconds


class IKCSessionStore(AbstractSessionStore):
    def __init__(self, project_id: str) -> None:
        self._project_id = project_id

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _key(self, filename: str) -> str:
        return f"{_PREFIX}/{_GC_FILENAME_PREFIX}{filename}"

    async def _put(self, key: str, data: bytes, mime: str = "application/json") -> None:
        """PUT a file, poll until it's readable, then register in CAMS if not already registered."""
        encoded = quote(key, safe="/")
        url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded}"
        # Step 1: PUT the file.
        await tool_helper_service.execute_put_request(
            url=url,
            files={"file": (key.rsplit("/", maxsplit=1)[-1], data, mime)},
            params={"project_id": self._project_id},
            headers={"accept": "*/*"},
        )
        # Step 2: confirm the object is readable in CPD storage before registering
        # in CAMS. Without this confirmation, CAMS registration may race the
        # object-storage commit and the file gets GC-ed.
        await self._poll_storage_readable(key)
        # Step 3: anchor ownership in CAMS catalog so CPD GC retains the file.
        # _register_cams (base class) is idempotent — skips if entry already exists.
        await self._register_cams(key, mime)

    async def _poll_storage_readable(self, key: str) -> None:
        """Poll GET on *key* until CPD storage confirms the file is readable.

        On CPD, /v2/asset_files/ PUT is eventually consistent — the object may
        return 404 for several seconds after a successful PUT response.  Registering
        in CAMS before the object is confirmed readable can cause GC eviction.
        """
        encoded = quote(key, safe="/")
        url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded}"
        delay = _PUT_INITIAL_DELAY
        filename = key.rsplit("/", maxsplit=1)[-1]
        for attempt in range(1, _PUT_MAX_RETRIES + 1):
            try:
                await tool_helper_service.execute_get_request(
                    url=url,
                    params={"project_id": self._project_id},
                    tool_name="glossary_curator",
                )
                LOGGER.info(
                    f"[IKCSessionStore] Storage confirmed readable after {attempt} attempt(s): {filename}"
                )
                return  # file is readable — proceed to CAMS registration
            except Exception as e:
                if "404" in str(e) or _NOT_FOUND in str(e).lower():
                    LOGGER.info(
                        f"[IKCSessionStore] Storage not yet readable (attempt {attempt}/{_PUT_MAX_RETRIES}): {filename}"
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, _PUT_MAX_DELAY)
                else:
                    # Unexpected error — don't block CAMS, log and return
                    LOGGER.warning(
                        f"[IKCSessionStore] Unexpected poll error for {filename}: {e}"
                    )
                    return
        LOGGER.warning(
            f"[IKCSessionStore] File not confirmed readable after {_PUT_MAX_RETRIES} attempts: {filename}. "
            f"Proceeding to CAMS registration anyway."
        )

    async def _get(self, key: str) -> Optional[bytes]:  # noqa: PLR0911, UP045 # Baseline
        encoded = quote(key, safe="/")
        url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded}"
        try:
            response = await tool_helper_service.execute_get_request(
                url=url,
                params={"project_id": self._project_id},
                tool_name="glossary_curator",
            )
            if isinstance(response, bytes):
                return response
            if isinstance(response, str):
                # HTTP client returned a decoded string — encode it as-is so
                # callers can do .decode() without double-encoding corruption.
                return response.encode()
            if isinstance(response, list):
                # HTTP client parsed application/json into a list (e.g. a top-level array).
                return json.dumps(response).encode()
            if isinstance(response, dict):
                content = response.get("content", response)
                if isinstance(content, bytes):
                    return content
                if isinstance(content, str):
                    return content.encode()
                return json.dumps(content).encode()
            return None
        except Exception as e:
            if "404" in str(e) or _NOT_FOUND in str(e).lower():
                return None
            LOGGER.warning(f"[IKCSessionStore] Could not read {key}: {e}")
            return None

    # ── File deletion helpers ─────────────────────────────────────────────────

    async def _delete_file(self, filename: str) -> None:
        object_key = f"data_asset/{filename}"
        LOGGER.info(f"Preparing to delete file: {filename}")
        await self._delete_file_from_storage(object_key)
        await self._deregister_cams(object_key)

    async def _delete_file_from_storage(self, object_key: str) -> None:
        """Delete the file at *object_key* from /v2/asset_files/."""
        encoded = quote(object_key, safe="/")
        url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded}"

        LOGGER.info(f"Deleting file from CPD storage: {object_key}")
        try:
            await tool_helper_service.execute_delete_request(
                url=url,
                params={"project_id": self._project_id},
                tool_name="glossary_curator",
            )
        except Exception as e:
            if "404" in str(e) or _NOT_FOUND in str(e).lower():
                return  # already gone — treat as success
            raise

    async def _list_keys(self) -> list[str]:
        """Return glossary-curation filenames (without the gc- prefix) for this project.

        Lists all files under data_asset/, filters to those starting with the gc-
        prefix, then strips the prefix so callers can pass names back through _key().
        """
        url = f"{tool_helper_service.base_url}/v2/asset_files/{_PREFIX}"
        try:
            response = await tool_helper_service.execute_get_request(
                url=url,
                params={"project_id": self._project_id},
                tool_name="glossary_curator",
            )
            resources = (
                (response or {}).get("resources", [])
                if isinstance(response, dict)
                else []
            )
            result = []
            for r in resources:
                if r.get("type") != "file":
                    continue
                fname = r.get("path", "").split("/")[-1]
                if fname.startswith(_GC_FILENAME_PREFIX):
                    result.append(fname[len(_GC_FILENAME_PREFIX) :])
            return result
        except Exception as e:
            LOGGER.warning(f"[IKCSessionStore] Could not list keys: {e}")
            return []

    def _dumps(self, obj: object) -> bytes:
        return json.dumps(obj, indent=2).encode()

    def _loads(self, raw: bytes) -> object:
        return json.loads(raw.decode())

    # ── AbstractSessionStore implementation ───────────────────────────────────

    async def write_session_manifest(self, data: dict) -> str:
        filename = f"{data['session_id']}-session.json"
        await self._put(self._key(filename), self._dumps(data))
        LOGGER.info(f"[IKCSessionStore] Session manifest written: {filename}")
        return filename

    async def read_session_manifest(self, session_id: str) -> Optional[dict]:  # noqa: UP045 # Baseline
        raw = await self._get(self._key(f"{session_id}-session.json"))
        return self._loads(raw) if raw else None

    async def overwrite_inflight_marker(
        self, session_id: str, chunk_index: int, marker: dict
    ) -> None:
        filename = f"{session_id}-chunk-inflight-{chunk_index:02d}.json"
        await self._put(self._key(filename), self._dumps(marker))

    async def read_inflight_marker(
        self, session_id: str, chunk_index: int
    ) -> Optional[dict]:  # noqa: UP045 # Baseline
        filename = f"{session_id}-chunk-inflight-{chunk_index:02d}.json"
        raw = await self._get(self._key(filename))
        return self._loads(raw) if raw else None

    async def chunk_result_exists(self, session_id: str, chunk_index: int) -> bool:
        filename = f"{session_id}-chunk-{chunk_index:02d}.json"
        raw = await self._get(self._key(filename))
        return raw is not None

    async def write_chunk_result(
        self, session_id: str, chunk_index: int, data: dict
    ) -> str:
        filename = f"{session_id}-chunk-{chunk_index:02d}.json"
        await self._put(self._key(filename), self._dumps(data))
        LOGGER.info(f"[IKCSessionStore] Chunk result written: {filename}")
        return filename

    async def read_chunk_result(
        self, session_id: str, chunk_index: int
    ) -> Optional[dict]:  # noqa: UP045 # Baseline
        filename = f"{session_id}-chunk-{chunk_index:02d}.json"
        raw = await self._get(self._key(filename))
        return self._loads(raw) if raw else None

    async def list_completed_chunks(
        self, session_id: str, total_chunks: int
    ) -> list[int]:
        # Single directory listing — one HTTP call instead of N existence checks.
        all_keys = await self._list_keys()
        completed = []
        for i in range(total_chunks):
            expected = f"{session_id}-chunk-{i:02d}.json"
            if expected in all_keys:
                completed.append(i)
        return completed

    async def write_pre_csv(self, session_id: str, content: str) -> str:
        filename = f"{session_id}-before.csv"
        await self._put(self._key(filename), content.encode(), mime=self.CSV_MIME_TYPE)
        LOGGER.info(f"[IKCSessionStore] Pre-curation CSV written: {filename}")
        return filename

    async def read_pre_csv(self, session_id: str) -> Optional[str]:  # noqa: UP045 # Baseline
        filename = f"{session_id}-before.csv"
        raw = await self._get(self._key(filename))
        if raw is None:
            LOGGER.info(f"[IKCSessionStore] Pre-curation CSV not found: {filename}")
            return None
        return raw.decode()

    async def write_after_csv(self, session_id: str, content: str) -> str:
        filename = f"{session_id}-after.csv"
        await self._put(self._key(filename), content.encode(), mime=self.CSV_MIME_TYPE)
        LOGGER.info(f"[IKCSessionStore] After-curation CSV written: {filename}")
        return filename

    async def read_after_csv(self, session_id: str) -> Optional[str]:  # noqa: UP045 # Baseline
        filename = f"{session_id}-after.csv"
        raw = await self._get(self._key(filename))
        if raw is None:
            LOGGER.info(f"[IKCSessionStore] After-curation CSV not found: {filename}")
            return None
        return raw.decode()

    async def delete_chunk_files(self, session_id: str, total_chunks: int) -> None:
        """Delete transient chunk and inflight files.

        The pre-curation (before.csv) and after-curation (after.csv) files are
        permanent outputs and are NOT deleted here.
        """
        filenames = []
        for i in range(total_chunks):
            filenames.append(f"gc-{session_id}-chunk-{i:02d}.json")
            filenames.append(f"gc-{session_id}-chunk-inflight-{i:02d}.json")
        for filename in filenames:
            try:
                await self._delete_file(filename)
                LOGGER.info(f"[IKCSessionStore] Deleted: {filename}")
            except Exception as e:
                LOGGER.warning(f"[IKCSessionStore] Could not delete {filename}: {e}")

    async def list_all_session_manifests(self) -> list[dict]:
        all_keys = await self._list_keys()
        manifests = []
        for fname in all_keys:
            if fname.endswith("-session.json"):
                raw = await self._get(self._key(fname))
                if raw:
                    try:
                        manifests.append(self._loads(raw))
                    except Exception as e:
                        LOGGER.warning(
                            f"[IKCSessionStore] Could not parse {fname}: {e}"
                        )
        return manifests
