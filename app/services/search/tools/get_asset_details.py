# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import asyncio
from typing import Optional
from app.core.registry import service_registry
from app.services.search.models.get_asset_details import (
    GetAssetDetailsRequest,
    GetAssetDetailsResponse,
    AssetUsage,
    MemberRoles,
    Rov,
    SourceAsset,
)

from app.shared.logging import LOGGER, auto_context
from app.services.tool_utils import (
    find_asset_id,
    retrieve_container_id,
    get_user_info_from_iam_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.helpers import is_uuid
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT

@service_registry.tool(
    name="get_asset_details",
    description="""Understand user's request about getting an asset's details / metadata and return the retrieved metadata.
                    Possible details that the user could be looking for include: asset usage, rov, member roles, collaborators, sub-container,
                    asset name, asset description, asset tags, asset type, origin country, resource key, identity key, delete processing state,
                    delete reason, asset rating, total asset ratings, asset creation time, asset owner, asset size, asset version, asset state,
                    asset attributes, revision id, entity information (columns etc.) etc.
                    User could request for all details or specific details. 
                    Example: Find details for asset dummy_asset in test catalog.
                    In this case, asset parameter will be 'dummy_asset', catalog parameter will be 'test' and project parameter will be None.
                    Example: Find metadata for asset testdb in agent project.
                    In this case, asset parameter will be 'testdb', catalog parameter will be None, and project parameter will be 'agent'.
                    Example: Find asset attributes of asset dummy_asset in test catalog.
                    In this case, asset parameter will be 'dummy_asset', catalog parameter will be 'test' and project parameter will be None.
                    Example: Find creation time of asset testdb in agent project.
                    In this case, asset parameter will be 'testdb', catalog parameter will be None, and project parameter will be 'agent'.
                       
                    IMPORTANT CONSTRAINTS:
                    - Asset parameter is required, either name or UUID
                    - One of catalog or project parameters is required to be not null, both cannot be null, both cannot be not null
                    - Invalid values will result in errors""",
    tags={"search", "asset_metadata"},
    meta={"version": "1.0", "service": "search"}
)
@auto_context
async def get_asset_details(
    request: GetAssetDetailsRequest
) -> GetAssetDetailsResponse:
    #Validate the request
    if not request.asset:
        error_msg = "Asset identifier cannot be empty. Please provide a valid asset id or name."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)
    if not request.catalog and not request.project:
        error_msg = "Container identifier cannot be empty. Please provide either catalog or project id or name."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)
    if request.catalog and request.project:
        error_msg = "Both container identifiers cannot be provided. Please provide either catalog or project id or name."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)

    LOGGER.info(
        "Starting get asset details search with asset: '%s', catalog id: '%s' and project id: '%s'",
        request.asset,
        request.catalog,
        request.project
    )

    container_type = "catalog" if request.catalog else "project"
    container_id = request.catalog if request.catalog else request.project
    container_id = await retrieve_container_id(container_id, container_type)

    asset_id = request.asset.strip()
    try:
        is_uuid(asset_id)
    except ServiceError:
        asset_id = await find_asset_id(asset_id, container_id, container_type)

    params = {
        container_type + "_id": container_id,
        "hide_deprecated_response_fields": False
    }

    response = await tool_helper_service.execute_get_request(
        url=f"{str(tool_helper_service.base_url)}{CAMS_ASSETS_BASE_ENDPOINT}/{asset_id}",
        params=params,
        tool_name="get_asset_details"
    )

    output = None
    metadata = response.get("metadata", {})
    if metadata:
        output = await retrieve_asset_metadata(metadata)
        output.entity = response.get("entity", {})
    else:
        raise ServiceError(
            f"Could not find metadata for asset {request.asset}"
        )

    return output

@service_registry.tool(
    name="get_asset_details",
    description="""Understand user's request about searching an asset's details / metadata and return the retrieved metadata.
                    Example: Find details for asset dummy_asset in test catalog.
                    In this case, asset parameter will be 'dummy_asset', catalog parameter will be 'test' and project parameter will be None.
                    Example: Find metadata for asset testdb in agent project.
                    In this case, asset parameter will be 'testdb', catalog parameter will be None, and project parameter will be 'agent'.

                    IMPORTANT CONSTRAINTS:
                    - Asset parameter is required, either name or UUID
                    - One of catalog or project parameters is required to be not null, both cannot be null, both cannot be not null
                    - Invalid values will result in errors""",
    tags={"search", "asset_metadata"},
    meta={"version": "1.0", "service": "search"}
)
@auto_context
async def wxo_get_asset_details(
    asset: str, catalog: Optional[str], project: Optional[str]
) -> GetAssetDetailsResponse:
    """Watsonx Orchestrator compatible version that expands GetAssetDetailsRequest object into individual parameters."""

    request = GetAssetDetailsRequest(
        asset=asset, catalog=catalog, project=project
    )

    # Call the original get_asset_details function
    return await get_asset_details(request)

async def _get_user_info(iam_id: str) -> tuple[str, str]:
    """
    Helper function to retrieve user name and email from IAM ID.
    Returns "icp4d-dev" for both name and email if the IAM ID is "icp4d-dev".
    Returns empty strings if IAM ID is None, empty string, or whitespace.
    Optimized to make concurrent API calls for name and email.
    
    Args:
        iam_id (str): IAM ID of the user
        
    Returns:
        tuple[str, str]: A tuple containing (name, email)
    """
    # Handle None, empty string, or whitespace-only strings
    if not iam_id or not iam_id.strip():
        return "", ""
    
    # Since the asset is created/updated by service_id 'icp4d-dev' and will not appear in the user list,
    # skip traversing from user_profiles.
    if iam_id == "icp4d-dev":
        return "icp4d-dev", "icp4d-dev"
    
    # Make both calls concurrently to optimize performance
    name, email = await asyncio.gather(
        get_user_info_from_iam_id(iam_id, "name"),
        get_user_info_from_iam_id(iam_id, "email")
    )
    return name, email


async def retrieve_asset_metadata(metadata: dict[str, any]) -> GetAssetDetailsResponse:
    """
    Extracts the full metadata information from asset metadata response
    and returns it.

    Args:
        metadata (dict[str, any]): Metadata information returned in asset metadata

    Returns:
        GetAssetDetailsResponse: An object of GetAssetDetailsResponse class with populated attributes
    """
    
    # Retrieve user information concurrently for better performance
    # Use .get() with default values to handle missing fields gracefully
    owner_id = metadata.get("owner_id", None)
    creator_id = metadata.get("creator_id", "")
    
    (owner_name, owner_email), (creator_name, creator_email) = await asyncio.gather(
        _get_user_info(owner_id or ""),
        _get_user_info(creator_id)
    )

    return GetAssetDetailsResponse(
        usage=await retrieve_asset_usage(metadata.get("usage", {})),
        rov=retrieve_rov(metadata.get("rov", {})),
        sub_container_id=metadata.get("sub_container_id", None),
        is_linked_with_sub_container=metadata["is_linked_with_sub_container"],
        name=metadata["name"],
        description=metadata.get("description", None),
        tags=metadata.get("tags", None),
        asset_type=metadata["asset_type"],
        origin_country=metadata.get("origin_country", None),
        resource_key=metadata["resource_key"],
        identity_key=metadata.get("identity_key", None),
        delete_processing_state=metadata.get("delete_processing_state", None),
        delete_reason=metadata.get("delete_reason", None),
        rating=metadata["rating"],
        total_ratings=metadata["total_ratings"],
        catalog_id=metadata.get("catalog_id", None),
        project_id=metadata.get("project_id", None),
        space_id=metadata.get("space_id", None),
        created=metadata["created"],
        created_at=metadata["created_at"],
        owner_id=owner_id,
        owner_name=owner_name,
        owner_email=owner_email,
        size=metadata["size"],
        version=metadata["version"],
        asset_state=metadata.get("asset_state", "available"),
        asset_attributes=metadata.get("asset_attributes", None),
        asset_id=metadata["asset_id"],
        source_asset=retrieve_source_asset(metadata.get("source_asset", {})),
        asset_category=metadata.get("asset_category", "USER"),
        revision_id=metadata.get("revision_id", None),
        number_of_shards=metadata.get("number_of_shards", None),
        creator_id=creator_id,
        creator_name=creator_name,
        creator_email=creator_email,
        is_branched=metadata.get("is_branched", None),
        set_id=metadata.get("set_id", None),
        is_managed_asset=metadata.get("is_managed_asset", False),
        entity={}
    )

def retrieve_source_asset(source_asset_info: dict[str, any]) -> Optional[SourceAsset]:
    """
    Extracts the source asset information from asset metadata response
    and returns it.

    Args:
        source_asset_info (dict[str, any]): Source asset information returned in asset metadata

    Returns:
        SourceAsset: An object of SourceAsset class with populated attributes
    """
    if not source_asset_info:
        return None

    return SourceAsset(
        action=source_asset_info.get("action", None),
        catalog_id=source_asset_info.get("catalog_id", None),
        project_id=source_asset_info.get("project_id", None),
        space_id=source_asset_info.get("space_id", None),
        asset_id=source_asset_info.get("asset_id", None),
        revision_id=source_asset_info.get("revision_id", None),
        bss_account_id=source_asset_info.get("bss_account_id", None),
        asset_name=source_asset_info["asset_name"],
        source_url=source_asset_info.get("source_url", None),
        resource_key=source_asset_info.get("resource_key", None),
        identity_key=source_asset_info.get("identity_key", None)
    )

def retrieve_rov(rov_info: dict[str, any]) -> Rov:
    """
    Extracts the ROV information from asset metadata response
    and returns it.

    Args:
        rov_info (dict[str, any]): ROV information returned in asset metadata

    Returns:
        Rov: An object of Rov class with populated attributes
    """

    member_roles = []
    for member in rov_info.get("member_roles", {}).values():
        member_role = MemberRoles(
            user_iam_id=member.get("user_iam_id", None),
            roles=member.get("roles", None)
        )
        member_roles.append(member_role)

    collaborator_ids = list(rov_info.get("collaborator_ids", {}).keys())

    return Rov(
        mode=rov_info["mode"],
        collaborator_ids=collaborator_ids,
        member_roles=member_roles
    )

async def retrieve_asset_usage(usage_info: dict[str, any]) -> AssetUsage:
    """
    Extracts the usage information from asset metadata response
    and returns it.

    Args:
        usage_info (dict[str, any]): Usage information returned in asset metadata

    Returns:
        AssetUsage: An object of AssetUsage class with populated attributes
    """
    
    # Retrieve user information concurrently for better performance
    # Use .get() with default values to handle missing fields gracefully
    last_updater_id = usage_info.get("last_updater_id", "")
    last_accessor_id = usage_info.get("last_accessor_id", "")
    
    (last_updater_name, last_updater_email), (last_accessor_name, last_accessor_email) = await asyncio.gather(
        _get_user_info(last_updater_id),
        _get_user_info(last_accessor_id)
    )

    return AssetUsage(
        last_updated_at=usage_info["last_updated_at"],
        last_updater_id=last_updater_id,
        last_updater_name=last_updater_name,
        last_updater_email=last_updater_email,
        last_update_time=usage_info["last_update_time"],
        last_accessed_at=usage_info["last_accessed_at"],
        last_access_time=usage_info["last_access_time"],
        last_accessor_id=last_accessor_id,
        last_accessor_name=last_accessor_name,
        last_accessor_email=last_accessor_email,
        access_count=usage_info["access_count"]
    )
