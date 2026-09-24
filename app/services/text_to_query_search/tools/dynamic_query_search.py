# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Any, List, Optional, Annotated
from pydantic import Field

from app.core.registry import service_registry
from app.services.glossary.constants import ContainerType
from app.services.search.utils.container_name_enrichment import (
    fetch_container_names,
    enrich_with_container_names,
)
from app.services.search.tools.search_asset import search_asset
from app.services.text_to_query_search.constants import (
    MAX_SEARCH_RESULTS,
    TOOL_DESCRIPTION,
    CONTAINER_TYPE_PROJECT_AND_CATALOG
)

from app.services.text_to_query_search.models.text2query_search_asset import (
    Container,
    TextToQuerySearchAssetRequest,
    GlobalSearchAssetResponse,
    TextToQuerySearchAssetResponse,
)
from app.services.text_to_query_search.utils.entity_resolver import (
    resolve_names_mapping_to_ids,
    find_container_id,
)
from app.services.text_to_query_search.utils.url_builder import (
    build_artifact_url,
)
from app.services.text_to_query_search.utils.source_data_extractor import (
    extract_source_data,
)
from app.services.text_to_query_search.utils.query_generator import (
    generate_gs_query,
    fetch_search_page,
)
from app.services.text_to_query_search.utils.request_validator import (
    validate_request,
)
from app.shared.utils.helpers import append_context_to_url
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.utils_tools import format_search_results_for_table

def _create_response_with_ui(
    results: List[GlobalSearchAssetResponse],
    query_data: dict,
    response: dict,
    show_table_selection: bool
) -> TextToQuerySearchAssetResponse:
    """Create response with appropriate UI based on selection mode."""
    message = response.get("message", "") if response.get("too_many_results", False) else None
    formatted_results = format_search_results_for_table(results)
    
    if show_table_selection:
        selected_assets = ui_message_context.send_table_selector_msg(
            tool_name="dynamic_query_search",
            data=results,
            formatted_data=formatted_results,
            title="Assets",
            description="Please select the asset(s) you'd like to use.",
            unique_keys=["Name", "Artifact Type"]
        )
        return TextToQuerySearchAssetResponse(
            generated_query=query_data,
            response=selected_assets or [],
            message=None if selected_assets else "No assets were selected.",
        )
    
    ui_message_context.add_table_ui_message(
        tool_name="dynamic_query_search",
        formatted_data=formatted_results,
        title="Search Results"
    )
    return TextToQuerySearchAssetResponse(
        generated_query=query_data, response=results, message=message
    )


async def _search(
    request: TextToQuerySearchAssetRequest,
    show_table_selection: bool = False
) -> TextToQuerySearchAssetResponse:
    """
    Internal search function that supports both display-only and selection modes for agentic UI contexts.
    
    Args:
        request: The search request
        show_table_selection: If True, shows a selection table UI and returns selected assets.
                            If False, shows display-only table UI and returns search results.
    """
    validate_request(request)
    container_id = ""
    container_details = None
    if request.container_name is not None and request.container_type is not None:
        container_id = await find_container_id(
            request.container_name, request.container_type
        )
        # Only create Container object for specific container types (not "project_and_catalog")
        # since ContainerType enum doesn't have "project_and_catalog" value
        if request.container_type != CONTAINER_TYPE_PROJECT_AND_CATALOG:
            container_details = Container(
                type=ContainerType(request.container_type),
                id=container_id,
                name=request.container_name,
            )
    
    # Resolve names_mapping to IDs if provided
    resolved_names_mapping = await resolve_names_mapping_to_ids(
        request.names_mapping,
        container_id if container_id else None,
        request.container_type if request.container_type != CONTAINER_TYPE_PROJECT_AND_CATALOG else None,
    )
    
    LOGGER.info(
        "Starting dynamic query search with prompt: '%s' and container_type: '%s' and container_id: '%s' and artifact_types: '%s' and resolved_names_mapping: '%s'",
        request.search_prompt,
        request.container_type,
        container_id,
        request.artifact_types,
        resolved_names_mapping,
    )

    try:
        query_data, validation_response = await generate_gs_query(
            request.search_prompt, request.artifact_types, container_details, resolved_names_mapping
        )
        LOGGER.info("Generated query from text2query: '%s'", query_data)
    except ExternalAPIError as e:
        LOGGER.error("External API failure calling text-to-query API: %s", e)
        return await _fallback_response(request, show_table_selection=show_table_selection)
    except Exception as e:
        LOGGER.error("Error calling text-to-query API: %s", e)
        return await _fallback_response(request, show_table_selection=show_table_selection)

    try:
        response = await _execute_search_with_query(query_data, validation_response)
        # Extract _source fields from query to pass to processing
        source_fields = query_data.get("_source", [])
        results = await _process_search_results(response, source_fields)

        if results:
            ui_message_context.create_markdown_code_snippet(
                code=str(query_data),
                language="json"
            )
            return _create_response_with_ui(results, query_data, response, show_table_selection)
        return await _fallback_response(request, query_data, show_table_selection=show_table_selection)
    except ExternalAPIError as e:
        LOGGER.error("External API failure executing search with generated query: %s", e)
        return await _fallback_response(request, query_data, show_table_selection=show_table_selection)
    except Exception as e:
        # Check for GraphInterrupt by name to avoid dependency on langgraph
        # Re‑raise GraphInterrupt so the agent pauses for user asset selection
        if type(e).__name__ == "GraphInterrupt":
            raise
        LOGGER.error("Error executing search with generated query: %s", e)
        return await _fallback_response(request, query_data, show_table_selection=show_table_selection)


def _construct_search_asset(row: Any, source_fields: Optional[List[str]] = None):
    asset_id = row["artifact_id"]

    metadata = row.get("metadata", {})
    artifact_type = metadata.get("artifact_type", None)
    artifact_name = metadata.get("name", "")
    description = metadata.get("description", None)

    catalog_id = None
    catalog_name = None
    project_id = None
    project_name = None
    artifact_type = (
        "glossary_term" if artifact_type == "business_term" else artifact_type
    )
    if artifact_type not in ["category", "glossary_term", "reference_data", "classification", "data_class", "policy", "rule"]:
        entity = row.get("entity", {})
        assets = entity.get("assets", {})
        catalog_id = assets.get("catalog_id", None)
        catalog_name = assets.get("catalog_name", None)
        project_id = assets.get("project_id", None)
        project_name = assets.get("project_name", None)

    # Build URL based on artifact type and container
    url = build_artifact_url(
        artifact_type, asset_id, project_id, catalog_id, artifact_name
    )

    url = append_context_to_url(url)

    # Extract source data based on requested _source fields
    source_data = extract_source_data(row, source_fields) if source_fields else None

    _EXCLUDED_METADATA_KEYS = {"name", "description", "artifact_type", "artifact_id"}
    additional_metadata = {
        k: v for k, v in metadata.items() if k not in _EXCLUDED_METADATA_KEYS and v is not None
    } or None

    return GlobalSearchAssetResponse(
        id=asset_id,
        name=artifact_name,
        description=description,
        asset_type=artifact_type,
        catalog_id=catalog_id,
        catalog_name=catalog_name,
        project_id=project_id,
        project_name=project_name,
        url=url,
        source_data=source_data,
        additional_metadata=additional_metadata,
    )

async def _fallback_response(
    request: TextToQuerySearchAssetRequest,
    query: dict | None = None,
    show_table_selection: bool = False,
) -> TextToQuerySearchAssetResponse:
    """Return a fallback response using the basic search_asset function."""
    response = await search_asset(search_prompt=request.search_prompt,
        container_type=request.container_type or "catalog",
        container_name=request.container_name,
        show_table_selection=show_table_selection,
    )

    if not response and show_table_selection:
        message = "No assets were selected."
    else:
        message = None
    return TextToQuerySearchAssetResponse(
        generated_query=query or {},
        response=response or [],
        message=message,
    )


def _annotate_and_cap_results(
    response: dict, all_rows: list, total_count: int, limit: int = 100
) -> list:
    """Cap results at limit and mutate *response* in-place with overflow metadata.

    Side effect: when total_count exceeds limit, the keys ``too_many_results``
    and ``message`` are added directly to *response* so that callers can inspect
    them after this function returns.
    """
    if total_count > limit:
        response["too_many_results"] = True
        response["message"] = (
            f"There is more than {limit} search results ({total_count} results) matching your question. "
            "You can narrow your question to find data you are looking for."
        )
        LOGGER.info("Limited results to %d out of %d total", limit, total_count)
        return all_rows[:limit]
    return all_rows


async def _execute_search_with_query(query_data: dict, validation_response: dict | None = None) -> dict:
    """Execute search with generated query and handle pagination.
    
    Args:
        query_data: The query to execute
        validation_response: Optional response from validation call to reuse
    """
    user_requested_limit = query_data.get("size", MAX_SEARCH_RESULTS)
    pagination_size = min(MAX_SEARCH_RESULTS, user_requested_limit)
    query_data = {**query_data, "size": pagination_size}

    if validation_response is not None:
        LOGGER.info("Reusing validation response, skipping initial search call")
        response = validation_response
    else:
        response = await fetch_search_page(query=query_data)
    
    total_count = response.get("size", 0)
    all_rows = response.get("rows", [])
    returned_rows_count = len(all_rows)

    LOGGER.info(
        "Initial search returned %d rows (pagination size: %d, user limit: %d, total count: %d)",
        returned_rows_count,
        pagination_size,
        user_requested_limit,
        total_count,
    )

    current_from = returned_rows_count
    while (
        returned_rows_count == pagination_size
        and len(all_rows) < total_count
        and len(all_rows) < user_requested_limit
    ):
        remaining = user_requested_limit - len(all_rows)
        next_page_size = min(pagination_size, remaining)

        LOGGER.info(
            "Fetching next page: from=%d, size=%d, remaining=%d",
            current_from,
            next_page_size,
            remaining,
        )

        paginated_rows = (
            await fetch_search_page(
                {**query_data, "from": current_from, "size": next_page_size}
            )
        ).get("rows", [])
        returned_rows_count = len(paginated_rows)

        if returned_rows_count == 0:
            LOGGER.info("No more rows returned, stopping pagination")
            break

        all_rows.extend(paginated_rows)
        current_from += returned_rows_count

        LOGGER.info(
            "Retrieved %d rows, total collected: %d", returned_rows_count, len(all_rows)
        )

    response["rows"] = _annotate_and_cap_results(response, all_rows, total_count)
    LOGGER.info("Pagination complete. Total rows collected: %d", len(response["rows"]))

    return response

async def _process_search_results(response: dict, source_fields: Optional[List[str]] = None) -> List[GlobalSearchAssetResponse]:
    """Process search response and construct asset list.
    
    Args:
        response: The search API response
        source_fields: Optional list of field paths requested in the query's _source parameter.
                      These fields are extracted and included in the source_data of each asset.
                      If None, no source data extraction is performed.
    """
    search_response = response.get("rows", [])
    search_response_all_results = response.get("size", 0)
    LOGGER.info("Search results: %s", search_response)

    li: list[GlobalSearchAssetResponse] = (
        [_construct_search_asset(row, source_fields) for row in search_response]
        if search_response
        else []
    )

    if li == [] and search_response_all_results > 0:
        LOGGER.warning(
            "Search returned %d results but none could be parsed into GlobalSearchAssetResponse",
            search_response_all_results,
        )
        return []

    # Fetch container names and enrich results
    if li:
        try:
            container_names = await fetch_container_names(li)
            if container_names:
                enrich_with_container_names(li, container_names)
        except Exception as e:
            LOGGER.warning("Failed to enrich results with container names: %s", str(e))

    return li


@service_registry.tool(
    name="dynamic_query_search",
    description=TOOL_DESCRIPTION,
    annotations={
        "readOnlyHint": True,
        "title": "Natural Language Asset Search with Query Generation"
    },
    tags={"generative_ai"},
)
@auto_context
async def search(
    search_prompt: Annotated[str, Field(description="The search prompt from the user about data potentially with additional searching details")],
    container_type: Annotated[Optional[str], Field(description="The container type in which to search assets, defaults to project_and_catalog")],
    container_name: Annotated[Optional[str], Field(description="Name of the container in which the asset resides. It can be either project or catalog. It allows the tool for searching assets in a specific container")],
    artifact_types: Annotated[Optional[list[str]], Field(description="The type of artifacts to search for, defaults to data_asset")],
    names_mapping: Annotated[Optional[list[dict]], Field(description="List of named entities with their types to be resolved to IDs. Each dict should contain 'name' and 'type' keys. Supported types: 'connection', 'metadata_import'. Example: [{'name': 'testConnName', 'type': 'connection'}, {'name': 'testMDIName', 'type': 'metadata_import'}]")] = None,
    show_table_selection: Annotated[bool, Field(description="If True, shows a selection table UI and returns selected assets. If False, shows display-only table UI and returns search results.")] = False,
) -> TextToQuerySearchAssetResponse:
    """Wrapper version of dynamic_query_search."""

    request = TextToQuerySearchAssetRequest(
        search_prompt=search_prompt,
        container_type=container_type,
        container_name=container_name,
        artifact_types=artifact_types,
        names_mapping=names_mapping,
    )

    # Call the original search function
    return await _search(request, show_table_selection=show_table_selection)

#Made with Bob
