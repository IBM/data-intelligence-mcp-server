# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Any, List

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.services.search.models.search_asset import (
    SearchAssetRequest,
    SearchAssetResponse,
)
from app.shared.utils.helpers import is_none, append_context_to_url
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError


@service_registry.tool(
    name="search_asset",
    description="""Understand user's request about searching data assets and return list of retrieved assets.
                       This function takes a user's search prompt as input and may take container type: project or catalog. Default container type to catalog.
                       It then returns list of asset that has been found.
                       
                       IMPORTANT CONSTRAINTS:
                       - search_prompt cannot be empty
                       - container_type must be one of: "catalog", "project"
                       - Invalid values will result in errors""",
)
@auto_context
async def search_asset(
    request: SearchAssetRequest, ctx=None
) -> List[SearchAssetResponse]:
    # Validate search_prompt is not empty
    if not request.search_prompt or request.search_prompt.strip() == "":
        error_msg = "Search prompt cannot be empty. Please provide a valid search term."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)
    
    # Validate container_type
    valid_container_types = ["project", "catalog"]
    auth_scope = "catalog"  # Default
    
    if not is_none(request.container_type):
        if request.container_type not in valid_container_types:
            error_msg = f"Invalid container_type: '{request.container_type}'. Valid values are: {valid_container_types}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)
        auth_scope = request.container_type

    LOGGER.info(
        "Starting asset search with prompt: '%s' and container_type: '%s'",
        request.search_prompt,
        auth_scope,
    )

    payload = {
        "query": {
            "bool": {
                "must": [
                    {
                        "gs_user_query": {
                            "search_string": request.search_prompt,
                            "semantic_search_enabled": True,
                        }
                    },
                    {"term": {"metadata.artifact_type": "data_asset"}},
                ]
            }
        }
    }

    params = {"auth_scope": request.container_type} if request.container_type else {}

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        params=params,
        json=payload,
    )

    search_response = response.get("rows", [])
    li = list(map(_construct_search_asset, search_response)) if search_response else []

    return li


@service_registry.tool(
    name="search_asset",
    description="""Understand user's request about searching data assets and return list of retrieved assets.
                       This function takes a user's search prompt as input and may take container type: project or catalog. Default container type to catalog.
                       It then returns list of asset that has been found.
                       
                       IMPORTANT CONSTRAINTS:
                       - search_prompt cannot be empty
                       - container_type must be one of: "catalog", "project"
                       - Invalid values will result in errors""",
)
@auto_context
async def wxo_search_asset(
    search_prompt: str, container_type: str = "catalog"
) -> List[SearchAssetResponse]:
    """Watsonx Orchestrator compatible version that expands SearchAssetRequest object into individual parameters."""
    
    request = SearchAssetRequest(
        search_prompt=search_prompt, container_type=container_type
    )

    # Call the original search_asset function
    return await search_asset(request)


def _construct_search_asset(row: Any):
    asset_id = row["artifact_id"]
    catalog_id = row["entity"]["assets"].get("catalog_id", None)
    project_id = row["entity"]["assets"].get("project_id", None)
    base_url = (
        f"{tool_helper_service.ui_base_url}/data/catalogs/{catalog_id}/asset/{asset_id}"
        if catalog_id
        else f"{tool_helper_service.ui_base_url}/projects/{project_id}/data-assets/{asset_id}"
    )

    url = append_context_to_url(base_url)

    return SearchAssetResponse(
        id=asset_id,
        name=row["metadata"]["name"],
        catalog_id=catalog_id,
        project_id=project_id,
        url=url,
    )
