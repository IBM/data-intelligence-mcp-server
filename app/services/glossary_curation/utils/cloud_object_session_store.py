# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Intermediate abstract base class shared by COSSessionStore and S3SessionStore.

Subclasses must implement four backend primitives:
  _put(key, data, mime)   — write bytes to the object store
  _get(key)               — read bytes from the object store; return None if absent
  _delete(key)            — delete an object from the object store
  _list_keys()            — list all gc/-prefixed filenames (gc/ prefix stripped)

Everything else — the full AbstractSessionStore interface plus the _key / _dumps /
_loads helpers — lives here and is shared by both backends without duplication.
"""

import json
from abc import abstractmethod
from typing import Any, Optional

from app.services.glossary_curation.utils.abstract_session_store import (
    AbstractSessionStore,
)
from app.shared.logging import LOGGER


class CloudObjectSessionStore(AbstractSessionStore):
    """Shared implementation for object-store-backed session stores.

    Subclasses must implement `_put`, `_get`, `_delete`, and `_list_keys`.
    """

    GC_PREFIX = "gc/"

    # ── Backend primitives (must be implemented by each subclass) ─────────────

    @abstractmethod
    async def _put(
        self, key: str, data: bytes, mime: str = "application/json"
    ) -> None: ...

    @abstractmethod
    async def _get(self, key: str) -> bytes | None: ...

    @abstractmethod
    async def _delete(self, key: str) -> None: ...

    @abstractmethod
    async def _list_keys(self) -> list[str]: ...

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _key(self, filename: str) -> str:
        return f"{self.GC_PREFIX}{filename}"

    def _dumps(self, obj: Any) -> bytes:
        return json.dumps(obj, indent=2).encode()

    def _loads(self, raw: bytes) -> Any:
        return json.loads(raw.decode())

    # ── AbstractSessionStore implementation ───────────────────────────────────

    async def write_session_manifest(self, data: dict) -> str:
        filename = f"{data['session_id']}-session.json"
        await self._put(self._key(filename), self._dumps(data))
        LOGGER.info(f"[{type(self).__name__}] Session manifest written: {filename}")
        return filename

    async def read_session_manifest(self, session_id: str) -> dict | None:
        raw = await self._get(self._key(f"{session_id}-session.json"))
        return self._loads(raw) if raw else None

    async def overwrite_inflight_marker(
        self, session_id: str, chunk_index: int, marker: dict
    ) -> None:
        filename = f"{session_id}-chunk-inflight-{chunk_index:02d}.json"
        await self._put(self._key(filename), self._dumps(marker))

    async def read_inflight_marker(
        self, session_id: str, chunk_index: int
    ) -> dict | None:
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
        LOGGER.info(f"[{type(self).__name__}] Chunk result written: {filename}")
        return filename

    async def read_chunk_result(self, session_id: str, chunk_index: int) -> dict | None:
        filename = f"{session_id}-chunk-{chunk_index:02d}.json"
        raw = await self._get(self._key(filename))
        return self._loads(raw) if raw else None

    async def list_completed_chunks(
        self, session_id: str, total_chunks: int
    ) -> list[int]:
        all_keys = await self._list_keys()
        return [
            i
            for i in range(total_chunks)
            if f"{session_id}-chunk-{i:02d}.json" in all_keys
        ]

    async def write_pre_csv(self, session_id: str, content: str) -> str:
        filename = f"{session_id}-before.csv"
        await self._put(self._key(filename), content.encode(), mime="text/csv")
        LOGGER.info(f"[{type(self).__name__}] Pre-curation CSV written: {filename}")
        return filename

    async def read_pre_csv(self, session_id: str) -> str | None:
        filename = f"{session_id}-before.csv"
        raw = await self._get(self._key(filename))
        if raw is None:
            LOGGER.info(
                f"[{type(self).__name__}] Pre-curation CSV not found: {filename}"
            )
            return None
        return raw.decode()

    async def write_after_csv(self, session_id: str, content: str) -> str:
        filename = f"{session_id}-after.csv"
        await self._put(self._key(filename), content.encode(), mime=self.CSV_MIME_TYPE)
        LOGGER.info(f"[{type(self).__name__}] After-curation CSV written: {filename}")
        return filename

    async def read_after_csv(self, session_id: str) -> Optional[str]:  # noqa: UP045 # Baseline
        filename = f"{session_id}-after.csv"
        raw = await self._get(self._key(filename))
        if raw is None:
            LOGGER.info(
                f"[{type(self).__name__}] After-curation CSV not found: {filename}"
            )
            return None
        return raw.decode()

    async def delete_chunk_files(self, session_id: str, total_chunks: int) -> None:
        """Delete transient chunk and inflight files.

        The pre-curation (before.csv) and after-curation (after.csv) files are
        permanent outputs and are NOT deleted here.
        """
        for i in range(total_chunks):
            for filename in [
                f"{session_id}-chunk-{i:02d}.json",
                f"{session_id}-chunk-inflight-{i:02d}.json",
            ]:
                await self._delete(self._key(filename))

    async def list_all_session_manifests(self) -> list[dict]:
        all_keys = await self._list_keys()
        manifests = []
        for fname in all_keys:
            if not fname.endswith("-session.json"):
                continue
            raw = await self._get(self._key(fname))
            if raw:
                try:
                    manifests.append(self._loads(raw))
                except Exception as e:
                    LOGGER.warning(
                        f"[{type(self).__name__}] Could not parse {fname}: {e}"
                    )
        return manifests
