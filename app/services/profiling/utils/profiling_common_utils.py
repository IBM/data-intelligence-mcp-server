# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Any, Dict, List, Optional
from app.services.constants import DATA_PROFILES_BASE_ENDPOINT
from app.services.profiling.models.create_data_profiles import (
    CreateDataProfilesResponse,
    DataProfileOptions,
)
from app.services.tool_utils import find_asset_id, find_catalog_id
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER
from app.shared.utils.helpers import is_uuid_bool
from app.shared.utils.tool_helper_service import tool_helper_service

DATA_PROFILES_URL = str(tool_helper_service.base_url) + DATA_PROFILES_BASE_ENDPOINT


async def resolve_catalog_id(catalog_id_or_name: str) -> str:
    """
    Resolves a catalog identifier to its UUID.
    
    Args:
        catalog_id_or_name: Catalog UUID or name
        
    Returns:
        str: The resolved catalog UUID
    """
    if is_uuid_bool(catalog_id_or_name):
        return catalog_id_or_name
    return await find_catalog_id(catalog_id_or_name)


async def resolve_dataset_ids(dataset_ids_or_names: List[str], catalog_id: str) -> List[str]:
    """
    Resolves a list of dataset identifiers to UUIDs.

    Each entry is passed through unchanged if it is already a UUID, otherwise
    ``find_asset_id`` is called to look up the asset by name within the catalog.

    Args:
        dataset_ids_or_names: List of dataset UUIDs or asset names.
        catalog_id: Resolved catalog UUID used for name lookups.

    Returns:
        List[str]: The resolved list of dataset UUIDs.
    """
    resolved: List[str] = []
    for entry in dataset_ids_or_names:
        if is_uuid_bool(entry):
            resolved.append(entry)
        else:
            LOGGER.info(
                "[PROFILING] Resolving dataset name '%s' to ID in catalog '%s'",
                entry,
                catalog_id,
            )
            asset_id = await find_asset_id(entry, catalog_id, "catalog")
            resolved.append(asset_id)
    return resolved


def get_asset_profiling_ui_url(catalog_id: str, dataset_id: str) -> str:
    """
    Constructs the per-asset profiling UI URL.

    The correct UI route is:
        /data/catalogs/<catalog_id>/asset/<dataset_id>/profiling

    Args:
        catalog_id (str): The catalog UUID.
        dataset_id (str): The dataset (asset) UUID.

    Returns:
        str: The UI URL for the asset's profiling page with context appended.
    """
    from app.shared.utils.helpers import append_context_to_url

    base_url = f"{tool_helper_service.ui_base_url}/data/catalogs/{catalog_id}/asset/{dataset_id}/profiling"
    return append_context_to_url(base_url)


async def create_data_profiles(
    catalog_id_or_name: str,
    dataset_ids: List[str],
    options: Optional[DataProfileOptions] = None,
) -> CreateDataProfilesResponse:
    """
    Create data profiles for specified datasets in a catalog.
    
    Args:
        catalog_id_or_name (str): Catalog ID or name
        dataset_ids (List[str]): List of dataset UUIDs or asset names to profile.
            Names are automatically resolved to UUIDs via the catalog asset search API.
        options (Optional[DataProfileOptions]): Profiling options
        
    Returns:
        CreateDataProfilesResponse: Profile information including ID, status, and UI URL
        
    Raises:
        ServiceError: If profile creation fails
    """
    
    LOGGER.info(
        "[PROFILING] Creating data profiles for catalog=%s, datasets=%s",
        catalog_id_or_name,
        dataset_ids,
    )
    
    # Resolve catalog ID if name provided
    catalog_id = await resolve_catalog_id(catalog_id_or_name)

    # Resolve any dataset names to UUIDs
    dataset_ids = await resolve_dataset_ids(dataset_ids, catalog_id)
    
    # Build request payload matching the API specification
    resolved_options = options or DataProfileOptions()
    payload = {
        "metadata": {
            "dataset_ids": dataset_ids,
            "catalog_id": catalog_id,
        },
        "entity": {
            "data_profile": {
                "options": resolved_options.model_dump()
            }
        }
    }
    
    try:
        LOGGER.info(
            "[PROFILING] Sending profile creation request to %s",
            DATA_PROFILES_URL,
        )

        response = await tool_helper_service.execute_post_request(
            url=DATA_PROFILES_URL,
            json=payload,
            params={"start": "true"},
            tool_name="create_data_profiles",
        )
    except ExternalAPIError as e:
        LOGGER.error(
            "[PROFILING] Failed to create profiles: %s",
            str(e),
        )
        raise ServiceError(
            f"Profile creation failed due to: {str(e)}",
            remediation_steps=(
                "Verify the catalog name is correct by calling `list_containers`, "
                "then retry with the correct catalog_id."
            ),
        )
    
    response_dict: Dict[str, Any] = response if isinstance(response, dict) else {}

    # The POST /v2/data_profiles response is a single resource object.
    # The profile ID lives at metadata.asset_id; execution status at
    # entity.data_profile.execution.status.
    metadata = response_dict.get("metadata", {})
    profile_id = metadata.get("asset_id")

    if not profile_id:
        LOGGER.error(
            "[PROFILING] No profile ID returned from API. Response: %s",
            response_dict,
        )
        raise ServiceError(
            "Profile creation failed: No profile ID returned from API",
            remediation_steps=(
                "Check that the dataset IDs are valid assets in the catalog "
                "by calling `search_asset`, then retry with the correct dataset_ids."
            ),
        )

    execution = response_dict.get("entity", {}).get("data_profile", {}).get("execution", {})
    status = execution.get("status", "pending")

    # For a single-asset profile, metadata.dataset_ids is [] and the real ID
    # is only in metadata.dataset_id (singular).
    # For a multi-asset (bulk) profile, metadata.dataset_ids has the full list.
    # Fall back to the locally-resolved list we submitted if the API returns nothing useful.
    api_dataset_ids: List[str] = metadata.get("dataset_ids") or []
    if not api_dataset_ids:
        single_id = metadata.get("dataset_id")
        api_dataset_ids = [single_id] if single_id else dataset_ids

    # Build one profiling UI URL per dataset using the correct per-asset route:
    #   /data/catalogs/<catalog_id>/asset/<dataset_id>/profiling
    ui_urls = [get_asset_profiling_ui_url(catalog_id, did) for did in api_dataset_ids]

    LOGGER.info(
        "[PROFILING] Profile created successfully. profile_id=%s, status=%s, bulk=%s, datasets=%s",
        profile_id,
        status,
        execution.get("bulk", False),
        api_dataset_ids,
    )

    return CreateDataProfilesResponse(
        profile_id=profile_id,
        catalog_id=catalog_id,
        dataset_ids=api_dataset_ids,
        status=status,
        ui_urls=ui_urls,
    )
