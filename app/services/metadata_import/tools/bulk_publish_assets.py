# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json
from typing import Annotated, List
from pydantic import Field
from app.core.registry import service_registry
from app.services.metadata_import.models.bulk_publish_assets import (
    BulkPublishAssetsRequest,
    BulkPublishAssetsResponse,
)
from app.services.tool_utils import (
    find_project_id,
    find_connection_id,
    find_catalog_id,
    find_metadata_import_id,
    find_asset_id,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError
from app.services.constants import METADATA_IMPORT_BASE_ENDPOINT


async def _resolve_asset_names_to_ids(
    asset_names: List[str], project_id: str
) -> List[str]:
    """
    Resolve a list of asset names to their corresponding asset IDs.

    Args:
        asset_names: List of asset names to resolve
        project_id: ID of the project containing the assets

    Returns:
        List of asset IDs in the same order as asset_names

    Raises:
        ServiceError: If one or more asset names cannot be resolved, listing
            all unresolvable names in the error message.
    """
    asset_ids = []
    unresolved_names = []

    for asset_name in asset_names:
        LOGGER.debug("Resolving asset name '%s' to ID in project %s", asset_name, project_id)
        try:
            asset_id = await find_asset_id(asset_name, project_id, "project")
            asset_ids.append(asset_id)
            LOGGER.debug("Resolved asset '%s' to ID: %s", asset_name, asset_id)
        except ServiceError as e:
            LOGGER.error("Failed to resolve asset name '%s': %s", asset_name, e)
            unresolved_names.append(asset_name)

    if unresolved_names:
        names_list = ", ".join(f"'{n}'" for n in unresolved_names)
        raise ServiceError(
            f"Could not find the following asset(s) in the project: {names_list}. "
            "Please verify the asset names and ensure they exist in the project.",
            remediation_steps=(
                f"Verify that the following asset(s) exist in the project: {names_list}. "
                "Use 'get_asset_details' to check a specific asset by name."
            ),
        )

    return asset_ids


async def _bulk_publish_assets(
    request: BulkPublishAssetsRequest,
) -> BulkPublishAssetsResponse:
    """
    Publish multiple data assets in bulk from a metadata import operation.
    
    This tool publishes data assets (tables, views, files) that have been
    imported via a metadata import to a catalog. Only data_asset types are
    supported for publishing.
    
    Args:
        request: BulkPublishAssetsRequest containing project name, connection name,
                 catalog name, metadata import name, and list of asset names
        
    Returns:
        BulkPublishAssetsResponse containing success message, published count,
        and all relevant IDs
        
    Raises:
        ServiceError: If any required resource is not found or API call fails
    """
    LOGGER.info(
        "Publishing %d assets from metadata import '%s' in project '%s' to catalog '%s'",
        len(request.asset_names),
        request.metadata_import_name,
        request.project_name,
        request.catalog_name,
    )
    
    # Resolve all IDs
    LOGGER.debug("Resolving project name to ID")
    project_id = await find_project_id(request.project_name)
    
    LOGGER.debug("Resolving connection name to ID")
    connection_id = await find_connection_id(
        request.connection_name, project_id, "project"
    )
    
    LOGGER.debug("Resolving catalog name to ID")
    catalog_id = await find_catalog_id(request.catalog_name)
    
    LOGGER.debug("Resolving metadata import name to ID")
    mdi_id = await find_metadata_import_id(
        request.metadata_import_name, project_id
    )
    
    LOGGER.debug(
        "Resolved IDs - project_id=%s, connection_id=%s, catalog_id=%s, mdi_id=%s",
        project_id,
        connection_id,
        catalog_id,
        mdi_id,
    )
    
    LOGGER.debug("Converting %d asset names to IDs", len(request.asset_names))
    asset_ids = await _resolve_asset_names_to_ids(request.asset_names, project_id)
    
    url = f"{tool_helper_service.base_url}{METADATA_IMPORT_BASE_ENDPOINT}/bulk_publish_assets"
    query_params = {
        "project_id": project_id,
        "connection_id": connection_id,
        "catalog_id": catalog_id,
        "mdi_id": mdi_id,
    }
    
    LOGGER.debug("Executing POST request to %s", url)
    LOGGER.debug("Query params: %s", query_params)
    LOGGER.debug("Request body (asset IDs): %s", asset_ids)
    
    json_content = json.dumps(asset_ids).encode('utf-8')
    
    await tool_helper_service.execute_post_request(
        url=url,
        params=query_params,
        content=json_content,
        tool_name="bulk_publish_assets",
    )
    
    LOGGER.info(
        "Successfully published %d assets from metadata import '%s'",
        len(asset_ids),
        request.metadata_import_name,
    )
    
    message = (
        f"Successfully published {len(asset_ids)} asset(s) from metadata import "
        f"'{request.metadata_import_name}' in project '{request.project_name}' "
        f"to catalog '{request.catalog_name}'."
    )
    
    return BulkPublishAssetsResponse(
        message=message,
        published_count=len(asset_ids),
        project_id=project_id,
        connection_id=connection_id,
        catalog_id=catalog_id,
        mdi_id=mdi_id,
        asset_ids=asset_ids,
    )


@service_registry.tool(
    name="bulk_publish_assets",
    description="""Publish multiple data assets in bulk from a metadata import operation.
    
    This tool publishes assets that have been imported via a metadata import to a catalog.
    All parameters are required.
    
    ERROR HANDLING:
    - If project not found: Use 'list_containers' to find available projects
    - If connection not found: Use 'search_connection' to find available connections
    - If catalog not found: Use 'list_containers' to find available catalogs
    - If metadata import not found: Use 'search_metadata_import' to find existing imports
    - If asset not found: Verify asset names exist in the project
    
    Returns: Success message with count of published assets and all relevant IDs.""",
    tags={"metadata-import", "bulk-publish", "publish-assets","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "metadata-import"},
    annotations={
        "title": "Bulk Publish Assets from Metadata Import",
        "destructiveHint": True
    }
)
@auto_context
async def bulk_publish_assets(
    project_name: Annotated[str, Field(description="The name of the project containing the metadata import and assets.")],
    connection_name: Annotated[str, Field(description="The name of the connection used by the metadata import.")],
    catalog_name: Annotated[str, Field(description="The name of the target catalog to publish the assets to.")],
    metadata_import_name: Annotated[str, Field(description="The name of the metadata import the assets were imported with.")],
    asset_names: Annotated[List[str], Field(description="List of asset names to publish from the metadata import.")],
) -> BulkPublishAssetsResponse:
    """Wrapper that expands BulkPublishAssetsRequest object into individual parameters."""
    request = BulkPublishAssetsRequest(
        project_name=project_name,
        connection_name=connection_name,
        catalog_name=catalog_name,
        metadata_import_name=metadata_import_name,
        asset_names=asset_names,
    )
    
    return await _bulk_publish_assets(request)
