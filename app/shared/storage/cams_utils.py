# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Shared CAMS (Catalog Asset Management Service) utility functions.

These functions are used by both BaseFileHandler (create_glossary_from_files)
and COSSessionStore (glossary_curator) to register, look up, and delete CAMS
assets so that files written to COS buckets are visible in the project UI.
"""

import os
from typing import Any, Dict, List, Optional, cast

from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service


async def get_cams_asset_id(project_id: str, object_key: str) -> Optional[str]:
    """Return the CAMS asset_id for *object_key* in *project_id*, or None.

    Searches by the basename of *object_key* so both full paths
    (``gc/session.json``) and bare filenames (``session.json``) resolve
    correctly.

    Args:
        project_id: Project ID to search in.
        object_key: Full storage path or bare filename of the asset.

    Returns:
        Asset ID string if a matching asset is found, else None.

    Raises:
        ServiceError: If the search request itself fails.
    """
    from app.shared.exceptions.base import ServiceError

    filename = os.path.basename(object_key)
    LOGGER.info(
        f"[cams_utils] Searching for CAMS asset: filename={filename!r} "
        f"object_key={object_key!r} project_id={project_id!r}"
    )
    try:
        search_url = f"{tool_helper_service.base_url}/v2/asset_types/asset/search"
        search_response = cast(
            Dict[str, Any],
            await tool_helper_service.execute_post_request(
                url=search_url,
                json={"query": f"asset.name:{filename}", "limit": 10000},
                params={"project_id": project_id},
            ),
        )
        results = search_response.get("results") or []
        LOGGER.info(f"[cams_utils] CAMS search returned {len(results)} result(s)")
        asset_id = next(
            (
                r.get("metadata", {}).get("asset_id")
                for r in results
                if r.get("metadata", {}).get("name") == filename
            ),
            None,
        )
        if asset_id:
            LOGGER.info(
                f"[cams_utils] Found CAMS asset_id={asset_id!r} for {filename!r}"
            )
        else:
            LOGGER.info(f"[cams_utils] No CAMS asset found for {filename!r}")
        return asset_id
    except Exception as e:
        LOGGER.warning(f"[cams_utils] Error looking up CAMS asset for {filename!r}: {e}")
        raise ServiceError(f"Error finding CAMS asset for file {filename}: {e}") from e


async def create_cams_asset(
    project_id: str,
    object_key: str,
    mime_type: str,
) -> None:
    """Create a new CAMS data_asset entry with an attachment pointing to *object_key*.

    Args:
        project_id: Project in which to create the asset.
        object_key: Full storage path used as the attachment ``object_key``.
        mime_type: MIME type of the file (e.g. ``"application/json"``).
    """
    filename = os.path.basename(object_key)
    LOGGER.info(
        f"[cams_utils] Creating CAMS asset: filename={filename!r} "
        f"object_key={object_key!r} mime_type={mime_type!r}"
    )
    payload: Dict[str, Any] = {
        "metadata": {
            "project_id": project_id,
            "name": filename,
            "asset_type": "data_asset",
            "asset_attributes": ["data_asset"],
            "asset_category": "USER",
        },
        "entity": {
            "data_asset": {"dataset": False, "mime_type": mime_type}
        },
        "attachments": [
            {
                "object_key": object_key,
                "object_key_is_read_only": False,
                "mime": mime_type,
                "asset_type": "data_asset",
                "name": filename,
                "description": "",
            }
        ],
    }
    await tool_helper_service.execute_post_request(
        url=(
            f"{tool_helper_service.base_url}/v2/assets"
            f"?project_id={project_id}&duplicate_action=IGNORE"
        ),
        json=payload,
    )
    LOGGER.info(f"[cams_utils] CAMS asset created for {filename!r}")


async def delete_cams_assets(
    project_id: str,
    asset_ids: List[Optional[str]],
) -> None:
    """Bulk-delete CAMS assets by ID.

    None values in *asset_ids* are silently filtered out.  A 404 response
    is treated as success (asset already gone).

    Args:
        project_id: Project in which the assets reside.
        asset_ids: Asset IDs to delete (may contain None).
    """
    valid_ids = [aid for aid in asset_ids if aid is not None]
    if not valid_ids:
        LOGGER.info("[cams_utils] delete_cams_assets: no valid IDs to delete")
        return
    LOGGER.info(f"[cams_utils] Deleting CAMS assets: {valid_ids}")
    try:
        await tool_helper_service.execute_delete_request(
            url=f"{tool_helper_service.base_url}/v2/assets/bulk",
            params={
                "project_id": project_id,
                "asset_ids": ",".join(valid_ids),
                "purge_on_delete": True,
            },
        )
        LOGGER.info(f"[cams_utils] CAMS assets deleted: {valid_ids}")
    except Exception as e:
        if "404" in str(e):
            LOGGER.warning(
                f"[cams_utils] 404 deleting assets {valid_ids} — already gone"
            )
        else:
            raise
