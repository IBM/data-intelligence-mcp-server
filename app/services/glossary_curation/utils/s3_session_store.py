# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""AWS S3 implementation of CloudObjectSessionStore.

All files are stored in the project's S3 bucket under a ``gc/`` prefix:
  gc/{session_id}-session.json
  gc/{session_id}-chunk-NN.json
  gc/{session_id}-chunk-inflight-NN.json
  gc/{session_id}-before.csv
  gc/{session_id}-after.csv

The bucket name, region, and credentials are resolved at session-start time via
``get_project_storage_details(project_id)`` and passed as ``storage_details``
to the constructor (same shape that ``S3Handler`` expects).

Credential refresh
------------------
AWS temporary credentials (STS session tokens) expire.  When a ``ClientError``
with ``ExpiredTokenException`` is raised, this store refreshes credentials via
``get_project_storage_details`` and recreates the aioboto3 client before
retrying.  Each public method that touches S3 is wrapped in
``_with_credential_refresh`` to handle this transparently.

Write durability
----------------
S3 PUT is strongly consistent since December 2020 — an object written with
``put_object`` is immediately visible to subsequent ``get_object`` and
``head_object`` calls in the same region.  No polling loop is needed.
"""

from typing import Any, Callable, Coroutine, TypeVar  # noqa: UP035 # Baseline

import aioboto3
from botocore.exceptions import ClientError

from app.services.glossary_curation.utils.cloud_object_session_store import (
    CloudObjectSessionStore,
)
from app.shared.logging import LOGGER

_EXPIRED_TOKEN_CODES = ("ExpiredTokenException", "ExpiredToken")

T = TypeVar("T")


class S3SessionStore(CloudObjectSessionStore):
    """Session store backed by Amazon S3.

    Args:
        storage_details: Dict returned by ``get_project_storage_details()``.
            Must contain ``properties.bucket_name``, ``properties.bucket_region``,
            and ``properties.credentials`` with ``access_key_id``,
            ``secret_access_key``, and optionally ``session_token``.
        project_id: IKC project ID — used only to refresh credentials when
            the STS session token expires.
        credential_refresh_callback: Async callable that returns fresh
            ``storage_details``.  Defaults to calling
            ``get_project_storage_details(project_id)`` if not supplied.
    """

    def __init__(
        self,
        storage_details: dict[str, Any],
        project_id: str,
        credential_refresh_callback: Callable[[], Coroutine[Any, Any, dict[str, Any]]]
        | None = None,
    ) -> None:
        self._project_id = project_id
        self._credential_refresh_callback = credential_refresh_callback
        self._session: aioboto3.Session | None = None
        self._client_context = None
        self._client = None
        self._update_credentials(storage_details)

    # ── Credential / client management ───────────────────────────────────────

    def _update_credentials(self, storage_details: dict[str, Any]) -> None:
        props = storage_details.get("properties", {})
        self._bucket_name: str = props.get("bucket_name", "")
        self._bucket_region: str = props.get("bucket_region", "us-east-1")
        creds = props.get("credentials", {})
        self._access_key_id: str = creds.get("access_key_id", "")
        self._secret_access_key: str = creds.get("secret_access_key", "")
        self._session_token: str | None = creds.get("session_token")

    async def _get_client(self):  # noqa: ANN202 # Baseline
        """Return a cached aioboto3 S3 client, creating it on first call."""
        if self._client is None:
            self._session = aioboto3.Session(
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                aws_session_token=self._session_token,
                region_name=self._bucket_region,
            )
            self._client_context = self._session.client("s3")
            self._client = await self._client_context.__aenter__()
        return self._client

    async def _close_client(self) -> None:
        if self._client_context is not None:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.warning(f"[S3SessionStore] Error closing S3 client: {e}")
            finally:
                self._session = None
                self._client_context = None
                self._client = None

    async def _refresh_credentials(self) -> None:
        """Fetch fresh credentials and recreate the S3 client."""
        if self._credential_refresh_callback is not None:
            new_details = await self._credential_refresh_callback()
        else:
            from app.shared.storage.project_utils import get_project_storage_details

            new_details = await get_project_storage_details(self._project_id)

        self._update_credentials(new_details)
        await self._close_client()
        LOGGER.info("[S3SessionStore] Credentials refreshed.")

    def _is_expired_token(self, exc: ClientError) -> bool:
        code = exc.response.get("Error", {}).get("Code", "")
        return code in _EXPIRED_TOKEN_CODES

    async def _with_credential_refresh(
        self, coro_fn: Callable[[], Coroutine[Any, Any, T]]
    ) -> T:
        """Execute an async callable, retrying once after a credential refresh."""
        try:
            return await coro_fn()
        except ClientError as e:
            if self._is_expired_token(e):
                LOGGER.info("[S3SessionStore] Token expired — refreshing credentials.")
                await self._refresh_credentials()
                return await coro_fn()
            raise

    # ── Backend primitives ──────────────────────────────────────────

    async def _put(self, key: str, data: bytes, mime: str = "application/json") -> None:
        """PUT an object to S3, then register in CAMS so the file appears in the Project UI."""

        async def _do() -> None:
            client = await self._get_client()
            await client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=data,
                ContentType=mime,
            )

        await self._with_credential_refresh(_do)
        LOGGER.info(f"[S3SessionStore] Written: {key}")
        await self._register_cams(key, mime)

    async def _get(self, key: str) -> bytes | None:
        """GET an object from S3.  Returns None if the key does not exist."""

        async def _do() -> bytes | None:
            client = await self._get_client()
            try:
                response = await client.get_object(Bucket=self._bucket_name, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "404", "NoSuchBucket"):
                    return None
                raise

        try:
            return await self._with_credential_refresh(_do)
        except Exception as e:
            LOGGER.warning(f"[S3SessionStore] Could not read {key}: {e}")
            return None

    async def _delete(self, key: str) -> None:
        """DELETE an S3 object and remove its CAMS entry."""

        async def _do() -> None:
            client = await self._get_client()
            try:
                await client.delete_object(Bucket=self._bucket_name, Key=key)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in ("NoSuchKey", "404"):
                    return  # already gone — still deregister CAMS in case entry exists
                raise

        try:
            await self._with_credential_refresh(_do)
            LOGGER.info(f"[S3SessionStore] Deleted: {key}")
        except Exception as e:
            LOGGER.warning(f"[S3SessionStore] Could not delete {key}: {e}")
        await self._deregister_cams(key)

    async def _list_keys(self) -> list[str]:
        """List all S3 objects under the gc/ prefix.

        Uses ``list_objects_v2`` with a Prefix filter and returns bare filenames
        (``gc/`` prefix stripped) so callers can pass them back through ``_key()``.
        """

        async def _do() -> list[str]:
            client = await self._get_client()
            response = await client.list_objects_v2(
                Bucket=self._bucket_name, Prefix=self.GC_PREFIX
            )
            filenames = []
            for obj in response.get("Contents", []):
                full_key: str = obj.get("Key", "")
                filenames.append(full_key[len(self.GC_PREFIX) :])
            return filenames

        try:
            return await self._with_credential_refresh(_do)
        except Exception as e:
            LOGGER.warning(f"[S3SessionStore] Could not list keys: {e}")
            return []
