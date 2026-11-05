# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Abstract interface for glossary curation session storage.

Three concrete implementations exist:
  IKCSessionStore  — writes to /v2/asset_files/ inside an IKC project (CPD)
  COSSessionStore  — writes to IBM Cloud Object Storage (SaaS IBM Cloud)
  S3SessionStore   — writes to AWS S3

Use get_session_store() to obtain the correct instance.  On first call for a given
(storage_type, project_id) pair the backend is selected from storage_details returned by
get_project_storage_details(); subsequent calls with the same project_id hit the cache.
"""

from abc import ABC, abstractmethod  # noqa: I001 # Baseline
from datetime import datetime, timezone, UTC  # noqa: F401 # Baseline
from typing import Optional

from app.shared.logging import LOGGER
from app.shared.storage.cams_utils import (
    create_cams_asset,
    delete_cams_assets,
    get_cams_asset_id,
)


class AbstractSessionStore(ABC):
    CSV_MIME_TYPE = "text/csv"

    @abstractmethod
    async def write_session_manifest(self, data: dict) -> str: ...

    @abstractmethod
    async def read_session_manifest(self, session_id: str) -> Optional[dict]: ...  # noqa: UP045 # Baseline

    async def write_inflight_marker(
        self,
        session_id: str,
        chunk_index: int,
        respawn_entry: Optional[dict] = None,  # noqa: UP045 # Baseline
    ) -> int:
        """Write or update the inflight marker for a chunk.

        First call (respawn_entry=None): create the marker with chunk_index and
        started_at only — no respawns key.  Returns 0.

        Subsequent calls (respawn_entry supplied): read the existing marker, append
        respawn_entry to the respawns list, write back.  Returns the new list length.

        The return value lets _get_chunk_prompt enforce the respawn cap (>= 2) without
        a separate read call.
        """
        if respawn_entry is None:
            # First attempt — create marker with no respawns key.
            payload: dict = {
                "chunk_index": chunk_index,
                "started_at": datetime.now(UTC).isoformat(),
            }
            await self.overwrite_inflight_marker(session_id, chunk_index, payload)
            return 0
        # Respawn — read existing marker, append entry, write back.
        marker = await self.read_inflight_marker(session_id, chunk_index)
        if marker is None:
            marker = {
                "chunk_index": chunk_index,
                "started_at": datetime.now(UTC).isoformat(),
            }
        respawns: list = marker.get("respawns", [])
        respawns.append(respawn_entry)
        marker["respawns"] = respawns
        await self.overwrite_inflight_marker(session_id, chunk_index, marker)
        return len(respawns)

    @abstractmethod
    async def read_inflight_marker(
        self, session_id: str, chunk_index: int
    ) -> Optional[dict]: ...  # noqa: UP045 # Baseline

    @abstractmethod
    async def chunk_result_exists(self, session_id: str, chunk_index: int) -> bool: ...

    @abstractmethod
    async def write_chunk_result(
        self, session_id: str, chunk_index: int, data: dict
    ) -> str: ...

    @abstractmethod
    async def read_chunk_result(
        self, session_id: str, chunk_index: int
    ) -> Optional[dict]: ...  # noqa: UP045 # Baseline

    @abstractmethod
    async def list_completed_chunks(
        self, session_id: str, total_chunks: int
    ) -> list[int]: ...

    @abstractmethod
    async def write_pre_csv(self, session_id: str, content: str) -> str: ...

    @abstractmethod
    async def read_pre_csv(self, session_id: str) -> Optional[str]: ...  # noqa: UP045 # Baseline

    @abstractmethod
    async def write_after_csv(self, session_id: str, content: str) -> str: ...

    @abstractmethod
    async def read_after_csv(self, session_id: str) -> Optional[str]: ...  # noqa: UP045 # Baseline

    @abstractmethod
    async def delete_chunk_files(self, session_id: str, total_chunks: int) -> None: ...

    @abstractmethod
    async def list_all_session_manifests(self) -> list[dict]: ...

    @abstractmethod
    async def overwrite_inflight_marker(
        self, session_id: str, chunk_index: int, marker: dict
    ) -> None:
        """Overwrite the inflight marker with *marker* verbatim — no append logic.

        Used internally by _get_chunk_prompt to persist a backfilled marker
        (stalled outcome on the previous respawn entry) before appending the
        new respawn entry via write_inflight_marker.
        """
        ...

    # ── Shared CAMS helpers ───────────────────────────────────────────────────
    # Concrete (non-abstract) — all subclasses share the same implementation.
    # The log prefix uses the concrete class name so log lines remain identifiable.

    async def _register_cams(self, object_key: str, mime: str) -> None:
        """Register *object_key* in CAMS so the file appears in the project UI.

        Idempotent: skips if an entry already exists (e.g. session.json
        re-written at complete_session).  Failure is non-fatal.
        """
        prefix = type(self).__name__
        try:
            existing_id = await get_cams_asset_id(self._project_id, object_key)
            if existing_id is not None:
                LOGGER.info(
                    f"[{prefix}] CAMS asset already exists for {object_key!r}, skipping."
                )
                return
            await create_cams_asset(self._project_id, object_key, mime)
            LOGGER.info(f"[{prefix}] CAMS registered: {object_key!r}")
        except Exception as e:
            LOGGER.warning(
                f"[{prefix}] CAMS registration failed for {object_key!r} (non-fatal): {e}"
            )

    async def _deregister_cams(self, object_key: str) -> None:
        """Remove the CAMS entry for *object_key* when a file is deleted.

        Keeps the project UI in sync with storage.  Failure is non-fatal.
        """
        prefix = type(self).__name__
        try:
            existing_id = await get_cams_asset_id(self._project_id, object_key)
            if existing_id is None:
                return
            await delete_cams_assets(self._project_id, [existing_id])
            LOGGER.info(f"[{prefix}] CAMS deregistered: {object_key!r}")
        except Exception as e:
            LOGGER.warning(
                f"[{prefix}] CAMS deregistration failed for {object_key!r} (non-fatal): {e}"
            )


# Maps project storage API type → internal backend name.
_STORAGE_TYPE_MAP = {
    "assetfiles": "ikc",
    "bmcos_object_storage": "cos",
    "amazon_s3": "s3",
}


def get_session_store(
    project_id: str = "",
    storage_details: Optional[dict] = None,  # noqa: UP045 # Baseline
) -> AbstractSessionStore:
    """Return a fresh session store for the given project_id."""

    raw_type = (storage_details or {}).get("type", "assetfiles")
    storage = _STORAGE_TYPE_MAP.get(raw_type, "ikc")

    LOGGER.debug(
        f"[session_store] Creating {storage!r} store for project_id={project_id!r}"
    )
    if storage == "cos":
        from app.services.glossary_curation.utils.cos_session_store import (
            COSSessionStore,
        )

        return COSSessionStore(storage_details or {}, project_id)
    if storage == "s3":
        from app.services.glossary_curation.utils.s3_session_store import S3SessionStore

        return S3SessionStore(storage_details or {}, project_id)
    from app.services.glossary_curation.utils.ikc_session_store import IKCSessionStore

    return IKCSessionStore(project_id)
