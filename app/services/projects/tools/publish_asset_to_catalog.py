# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Any, cast

from app.core.registry import service_registry
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.services.projects.models.publish_asset_to_catalog import (
    PublishAssetToCatalogRequest,
    PublishAssetToCatalogResponse,
)
from app.services.tool_utils import find_asset_id, retrieve_container_id, check_catalog_access
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url, is_uuid_bool
from app.shared.utils.tool_helper_service import tool_helper_service
from typing import Annotated, List, Optional
from pydantic import Field


async def _publish_asset_to_catalog(
    request: PublishAssetToCatalogRequest,
) -> PublishAssetToCatalogResponse:
    if not request.asset or not request.asset.strip():
        error_msg = "Asset identifier cannot be empty. Please provide a valid asset id or name."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg, remediation_steps="Call the search_asset tool twice: first with search_prompt set to '*' and container_type set to 'catalog', then with search_prompt set to '*' and container_type set to 'project'. Retrieve the available assets from both calls, then provide a valid asset name or id from the combined results.",
                               tool="publish_asset_to_catalog")

    if not request.project or not request.project.strip():
        error_msg = "Project identifier cannot be empty. Please provide a valid project id or name."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg, remediation_steps="Call the list_containers tool with container_type set to 'project' to retrieve the list of available projects. Then provide a project id or name from the list.",
                               tool="publish_asset_to_catalog")

    if not request.catalog or not request.catalog.strip():
        error_msg = "Catalog identifier cannot be empty. Please provide a valid catalog id or name."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg, remediation_steps="Call the list_containers tool with container_type set to 'catalog' to retrieve the list of available catalogs. Then provide a catalog id or name from the list.",
                               tool="publish_asset_to_catalog")

    LOGGER.info(
        "Starting publish asset to catalog with asset: '%s', project: '%s', catalog: '%s'",
        request.asset,
        request.project,
        request.catalog,
    )

    source_project_id = await retrieve_container_id(request.project.strip(), "project")
    target_catalog_id = await retrieve_container_id(request.catalog.strip(), "catalog")
    
    # Validate that the caller has admin or editor access to the target catalog
    has_access = await check_catalog_access(target_catalog_id, ["admin", "editor"])
    if not has_access:
        error_msg = (
            f"Access denied: You must have 'admin' or 'editor' role in catalog '{request.catalog}' "
            f"to publish assets to it. Please contact the catalog administrator to request access."
        )
        LOGGER.error(error_msg)
        raise ServiceError(error_msg,
                           tool="publish_asset_to_catalog")

    source_asset_id = request.asset.strip()
    if not is_uuid_bool(source_asset_id):
        source_asset_id = await find_asset_id(source_asset_id, source_project_id, "project")

    params = {
        "project_id": source_project_id,
    }

    body = {
        "catalog_id": target_catalog_id,
    }

    response = await tool_helper_service.execute_post_request(
        url=f"{str(tool_helper_service.base_url)}{CAMS_ASSETS_BASE_ENDPOINT}/{source_asset_id}/publish",
        params=params,
        json=body,
        tool_name="publish_asset_to_catalog",
    )
    response_dict = cast(dict[str, Any], response)

    metadata = cast(dict[str, Any], response_dict.get("metadata", {}))
    entity = cast(dict[str, Any], response_dict.get("entity", {}))
    published_asset_id = metadata.get("asset_id")
    published_asset_name = metadata.get("name") or entity.get("name") or request.asset.strip()

    if not published_asset_id:
        raise ServiceError("Publish asset to catalog succeeded but no published asset id was returned.", tool="publish_asset_to_catalog")

    asset_url = append_context_to_url(
        f"{tool_helper_service.ui_base_url}/data/catalogs/{target_catalog_id}/asset/{published_asset_id}"
    )

    return PublishAssetToCatalogResponse(
        message=(
            f"Successfully published asset '{published_asset_name}' from project "
            f"'{source_project_id}' to catalog '{target_catalog_id}'."
        ),
        asset_id=published_asset_id,
        asset_name=published_asset_name,
        catalog_id=target_catalog_id,
        source_project_id=source_project_id,
        source_asset_id=source_asset_id,
        url=asset_url,
    )


@service_registry.tool(
    name="publish_asset_to_catalog",
    annotations={
        "title": "Publish Asset from Project to Catalog",
        "destructiveHint": True,
    },
    description="""Use this tool to Publish an asset from a project to a catalog.
                    This tool resolves the source project, target catalog, and source asset, then invokes the
                    platform publish API so the asset is published with the platform's existing semantics,
                    including metadata and revision handling.
                    Return: The asset added to the catalog and the API location URL to access it.",

                    IMPORTANT CONSTRAINTS:
                    - asset is required and must identify an asset in the source project
                    - project is required and must identify the source project
                    - catalog is required and must identify the target catalog""",
    tags={"search", "asset_publish"},
    meta={"version": "1.0", "service": "projects"},
)
@auto_context
async def publish_asset_to_catalog(
    asset: Annotated[str, Field(description="The name of the asset to be poblished")],
    project: Annotated[str, Field(description="The source project")],
    catalog: Annotated[str, Field(description="The target catalog")]
) -> PublishAssetToCatalogResponse:
    request = PublishAssetToCatalogRequest(
        asset=asset,
        project=project,
        catalog=catalog,
    )
    return await _publish_asset_to_catalog(request)

# Made with Bob, Corrected using non-AI
