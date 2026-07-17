# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Any, List, Annotated
from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.services.search.models.search_asset import (
    SearchAssetRequest,
    SearchAssetResponse,
)
from app.services.text_to_query_search.utils.entity_resolver import find_container_id
from app.shared.utils.helpers import is_none, append_context_to_url
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.utils_tools import format_search_results_for_table

def _add_ui_message_if_results(results: List[SearchAssetResponse]) -> None:
    """Add UI message if search results exist."""
    if results:
        formatted_results = format_search_results_for_table(results)
        ui_message_context.add_table_ui_message(
            tool_name="search_asset",
            formatted_data=formatted_results,
            title="Search Results"
        )


async def _search_asset(
    request: SearchAssetRequest, ctx=None
) -> List[SearchAssetResponse]:
    # Validate search_prompt is not empty
    if not request.search_prompt or request.search_prompt.strip() == "":
        error_msg = "Search prompt cannot be empty. Please provide a valid search term."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)
    
    # Validate container_type
    valid_container_types = ["project", "catalog", "project_and_catalog"]
    auth_scope = "catalog"  # Default
    
    if not is_none(request.container_type):
        if request.container_type not in valid_container_types:
            error_msg = f"Invalid container_type: '{request.container_type}'. Valid values are: {valid_container_types}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)
        # Convert project_and_catalog to the format expected by the API
        auth_scope = "project,catalog" if request.container_type == "project_and_catalog" else request.container_type

    # Resolve container_name to container_id if provided
    container_id = None
    if request.container_name and request.container_type:
        container_id = await find_container_id(request.container_name, request.container_type)
        LOGGER.info(
            "Resolved container '%s' (type: %s) to ID: %s",
            request.container_name,
            request.container_type,
            container_id,
        )

    LOGGER.info(
        "Starting asset search with prompt: '%s', container_type: '%s', container_id: '%s'",
        request.search_prompt,
        auth_scope,
        container_id,
    )

    # Build query with optional container filter
    must_clauses = [
        {
            "gs_user_query": {
                "search_string": request.search_prompt,
                "semantic_search_enabled": True,
            }
        }
    ]
    
    # Add container filter if container_id is resolved
    if container_id:
        if request.container_type == "project":
            must_clauses.append({"term": {"entity.assets.project_id": container_id}})
        elif request.container_type == "catalog":
            must_clauses.append({"term": {"entity.assets.catalog_id": container_id}})
        elif request.container_type == "project_and_catalog":
            # For project_and_catalog, use should clause with both options
            must_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"entity.assets.project_id": container_id}},
                        {"term": {"entity.assets.catalog_id": container_id}}
                    ],
                    "minimum_should_match": 1
                }
            })

    payload = {
        "query": {
            "bool": {
                "must": must_clauses
            }
        },
        "_source": ["metadata", "entity.assets", "artifact_id"]
    }

    params = {"auth_scope": auth_scope, "auth_cache": True, "tenant_scope": True}

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        params=params,
        json=payload,
    )

    search_response = response.get("rows", [])
    results = list(map(_construct_search_asset, search_response)) if search_response else []

    _add_ui_message_if_results(results)

    return results


@service_registry.tool(
    name="search_asset",
    annotations={
        "readOnlyHint": True,
        "title": "Semantic Search for Data Assets Across Catalogs and Projects"
    },
    description="""Use this tool when you need to find data assets by name, description, or semantic search across catalogs and projects.
                       Understand user's request about searching data assets and return list of retrieved assets.
                       This function takes a user's search prompt as input and may take container type: project or catalog. Default container type to catalog.
                       It then returns list of asset that has been found.
                       
                       IMPORTANT CONSTRAINTS:
                       - search_prompt cannot be empty
                       - container_type must be one of: "catalog", "project"
                       - Invalid values will result in errors
                       Return: A list of objects, each containing the asset's unique ID, name, container IDs (catalog or project), and URL.""",
)
@auto_context
async def search_asset(
    search_prompt: Annotated[str, Field(description="The search prompt from the user about data assets potentially with additional searching details")],
    container_type: Annotated[str, Field(description="The container type in which to search assets, defaults to catalog")] = "catalog",
    container_name: Annotated[str | None, Field(description="Optional container name to resolve to ID and filter results")] = None
) -> List[SearchAssetResponse]:
    """Wrapper that expands SearchAssetRequest object into individual parameters."""
    
    request = SearchAssetRequest(
        search_prompt=search_prompt,
        container_type=container_type,
        container_name=container_name
    )

    # Call the original search_asset function
    return await _search_asset(request)


def _construct_search_asset(row: Any):
    asset_id = row["artifact_id"]
    entity = row.get("entity", {})
    assets = entity.get("assets", {})
    catalog_id = assets.get("catalog_id", None)
    catalog_name = assets.get("catalog_name", None)
    project_id = assets.get("project_id", None)
    project_name = assets.get("project_name", None)
    base_url = (
        f"{tool_helper_service.ui_base_url}/data/catalogs/{catalog_id}/asset/{asset_id}"
        if catalog_id
        else f"{tool_helper_service.ui_base_url}/projects/{project_id}/data-assets/{asset_id}"
    )

    url = append_context_to_url(base_url)

    metadata = row.get("metadata", {})
    asset_name = metadata.get("name", "")

    return SearchAssetResponse(
        id=asset_id,
        name=asset_name,
        catalog_id=catalog_id,
        catalog_name=catalog_name,
        project_id=project_id,
        project_name=project_name,
        url=url,
    )
