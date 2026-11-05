# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""IBM Cloud Object Storage (COS) implementation of CloudObjectSessionStore

All files are stored in the project's COS bucket under a ``gc/`` prefix:
  gc/{session_id}-session.json
  gc/{session_id}-chunk-NN.json
  gc/{session_id}-chunk-inflight-NN.json
  gc/{session_id}-before.csv
  gc/{session_id}-after.csv

The bucket URL and credentials are resolved at session-start time via
``get_project_storage_details(project_id)`` and passed as ``storage_details``
to the constructor (same shape that ``COSHandler`` expects).

Write durability
----------------
COS PUT is synchronous — the object is immediately consistent after a
successful 200 response.  No polling loop is needed (unlike the CPD
asset-files backend).  Each write therefore goes directly to a single
``tool_helper_service.execute_put_request`` call.

List / delete use the S3-compatible XML list API exposed by IBM COS.
"""

import json  # noqa: I001 # Baseline
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET
import re

from app.services.glossary_curation.utils.cloud_object_session_store import (
    CloudObjectSessionStore,
)
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service

_NOT_FOUND_PATTERNS = ("404", "not found", "nosuchkey")

# Polling config (used only as a safety net — COS PUT is synchronous)
_PUT_MAX_RETRIES = 5
_PUT_INITIAL_DELAY = 0.5


class COSSessionStore(CloudObjectSessionStore):
    """Session store backed by IBM Cloud Object Storage.

    Args:
        storage_details: Dict returned by ``get_project_storage_details()``.
            Must contain ``properties.endpoint_url`` and ``properties.bucket_name``.
        project_id: IKC project ID — used only for CAMS registration calls
            (not for COS I/O itself).
    """

    def __init__(self, storage_details: dict[str, Any], project_id: str) -> None:
        props = storage_details.get("properties", {})
        self._bucket_name: str = props.get("bucket_name", "")
        self._bucket_url: str = f"{props.get('endpoint_url', '')}/{self._bucket_name}"
        self._project_id = project_id

    # ── Backend primitives ────────────────────────────────────────────────────

    async def _put(self, key: str, data: bytes, mime: str = "application/json") -> None:
        """PUT an object to COS, then register in CAMS so the file appears in the Project UI."""
        encoded = quote(key, safe="")
        url = f"{self._bucket_url}/{encoded}"
        await tool_helper_service.execute_put_request(
            url=url,
            content=data,
            headers={"Content-Type": mime},
        )
        LOGGER.info(f"[COSSessionStore] Written: {key}")
        await self._register_cams(key, mime)

    async def _get(self, key: str) -> bytes | None:  # noqa: PLR0911 # Baseline
        """GET an object from COS.  Returns None if the key does not exist."""
        encoded = quote(key, safe="")
        url = f"{self._bucket_url}/{encoded}"
        try:
            response = await tool_helper_service.execute_get_request(
                url=url,
                tool_name="glossary_curator",
            )
            if isinstance(response, bytes):
                return response
            if isinstance(response, list):
                return json.dumps(response).encode()
            if isinstance(response, dict):
                content = response.get("content", response)
                if isinstance(content, bytes):
                    return content
                return json.dumps(content).encode()
            return None
        except Exception as e:
            if any(p in str(e).lower() for p in _NOT_FOUND_PATTERNS):
                return None
            LOGGER.warning(f"[COSSessionStore] Could not read {key}: {e}")
            return None

    async def _delete(self, key: str) -> None:
        """DELETE a COS object and remove its CAMS entry."""
        encoded = quote(key, safe="")
        url = f"{self._bucket_url}/{encoded}"
        try:
            await tool_helper_service.execute_delete_request(
                url=url,
                tool_name="glossary_curator",
            )
            LOGGER.info(f"[COSSessionStore] Deleted: {key}")
        except Exception as e:
            if any(p in str(e).lower() for p in _NOT_FOUND_PATTERNS):
                pass  # already gone — still deregister CAMS in case entry exists
            else:
                LOGGER.warning(f"[COSSessionStore] Could not delete {key}: {e}")
        await self._deregister_cams(key)

    async def _list_keys(self) -> list[str]:
        """List all COS objects under the gc/ prefix.

        Uses the S3-compatible list-objects-v2 query against the bucket URL and
        filters to filenames only (strips the ``gc/`` prefix).
        """
        try:
            response = await tool_helper_service.execute_get_request(
                url=self._bucket_url,
                params={"list-type": 2, "prefix": self.GC_PREFIX},
                tool_name="glossary_curator",
            )
            xml_data: bytes = (
                response.get("content", response)
                if isinstance(response, dict)
                else response
            )
            return self._parse_list_xml(xml_data)
        except Exception as e:
            LOGGER.warning(f"[COSSessionStore] Could not list keys: {e}")
            return []

    def _parse_list_xml(self, xml_data: bytes) -> list[str]:
        """Parse S3 list-objects XML and return filenames (gc/ prefix stripped)."""
        try:
            root = ET.fromstring(xml_data)  # noqa: S314 # Baseline
            m = re.match(r"\{(.*)\}", root.tag)
            namespace = m.group(1) if m else ""
            ns = {"s3": namespace} if namespace else {}
            key_tag = "s3:Key" if namespace else "Key"
            contents_tag = "s3:Contents" if namespace else "Contents"

            filenames = []
            for content in root.findall(contents_tag, ns):
                key_elem = content.find(key_tag, ns)
                if key_elem is not None and key_elem.text:
                    # Strip the gc/ prefix so callers get bare filenames
                    filenames.append(key_elem.text[len(self.GC_PREFIX) :])
            return filenames
        except ET.ParseError as e:
            LOGGER.warning(f"[COSSessionStore] XML parse error listing keys: {e}")
            return []
