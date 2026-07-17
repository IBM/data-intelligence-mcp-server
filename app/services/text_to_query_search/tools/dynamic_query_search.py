# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json
import asyncio
from typing import Any, List, Optional, Annotated
from pydantic import Field

from aiocache import cached

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT, TEXT_TO_QUERY_BASE_ENDPOINT, PROJECTS_BASE_ENDPOINT, CATALOGS_BASE_ENDPOINT
from app.services.glossary.constants import ContainerType
from app.services.search.models.search_asset import SearchAssetRequest
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
from app.services.text_to_query_search.utils.request_validator import (
    validate_request,
)
from app.shared.utils.helpers import append_context_to_url
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.utils_tools import format_search_results_for_table

# Maximum number of retry attempts for query generation
MAX_QUERY_GENERATION_ATTEMPTS = 2


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
        query_data, validation_response = await _call_text_to_query_api_with_retry(
            request.search_prompt, request.artifact_types, container_details, resolved_names_mapping
        )
        LOGGER.info("Generated query from text2query: '%s'", query_data)
    except ExternalAPIError as e:
        LOGGER.error("External API failure calling text-to-query API: %s", e)
        return await _fallback_response(request)
    except Exception as e:
        LOGGER.error("Error calling text-to-query API: %s", e)
        return await _fallback_response(request)

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
        return await _fallback_response(request, query_data)
    except ExternalAPIError as e:
        LOGGER.error("External API failure executing search with generated query: %s", e)
        return await _fallback_response(request, query_data)
    except Exception as e:
        # Check for GraphInterrupt by name to avoid dependency on langgraph
        # Re‑raise GraphInterrupt so the agent pauses for user asset selection
        if type(e).__name__ == "GraphInterrupt": 
            raise
        LOGGER.error("Error executing search with generated query: %s", e)
        return await _fallback_response(request, query_data)


def _construct_search_asset(row: Any, source_fields: Optional[List[str]] = None):
    asset_id = row["artifact_id"]

    metadata = row.get("metadata", {})
    artifact_type = metadata.get("artifact_type", None)
    artifact_name = metadata.get("name", "")

    catalog_id = None
    catalog_name = None
    project_id = None
    project_name = None
    artifact_type = (
        "glossary_term" if artifact_type == "business_term" else artifact_type
    )
    if artifact_type not in ["category", "glossary_term", "reference_data", "classification", "data_class"]:
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

    return GlobalSearchAssetResponse(
        id=asset_id,
        name=artifact_name,
        asset_type=artifact_type,
        catalog_id=catalog_id,
        catalog_name=catalog_name,
        project_id=project_id,
        project_name=project_name,
        url=url,
        source_data=source_data,
    )

async def _call_text_to_query_api(
    search_prompt: str,
    artifact_types: List[str] | None,
    container_details: Container | None,
    resolved_names_mapping: List[dict] | None = None,
) -> dict:
    """Call text-to-query API and return query data."""
    instructions = [
        "When asked to search for assets by name, Look for assets that match filter metadata.name. Try to match against singular and plural forms of the name. E.g If the user asks about policies, search for assets with name matching policy or policies",
        "When asked to search for assets related to a keyword, search in: name, semantic name, description, and tags. Include keyword variations ONLY when word forms differ significantly (e.g., 'policy' → 'policies'). Examples: 'policy' → search for 'policy' AND 'policies'; 'analysis' → search for 'analysis' AND 'analyses'; 'investment' → search for 'investment' AND 'investing'. Do NOT add variations when wildcard would suffice. Do NOT use synonyms or unrelated meanings. Apply this to generic questions like 'find assets about X', 'get data related to X'",
        "Only if there is specific named container mentioned in the search prompt apply container id (project_id/catalog_id) filter. E.g find assets related to schools in projects. -> There is no specific project mentioned; Do not apply container filter. E.g find assets related to schools in project 'schools' -> Apply project ID filter",
        "If the user asks about glossary terms, use metadata.artifact_type=glossary_term",
        "When searching for tags, filter by metadata.tags",
        "When asked about abbreviations try to match by name or by entity.artifacts.abbreviation"
    ]
    if artifact_types:
        instructions.append(
            f"Apply filter to match searched data type ->  metadata.artifact_type: {', '.join(artifact_types)}"
        )
    names_to_ids = []
    if (
        container_details
        and container_details.id
        and container_details.type
        and container_details.name
    ):
        names_to_ids.append(
            {
                "name": container_details.name,
                "type": str(container_details.type),
                "id": container_details.id,
            }
        )
    
    # Add resolved names_mapping to names_to_ids
    if resolved_names_mapping:
        names_to_ids.extend(resolved_names_mapping)
        LOGGER.info("Added %d resolved entities to names_to_ids", len(resolved_names_mapping))
    
    text_to_query_payload = {
        "include_raw_model_input_output": False,
        "input_question": search_prompt,
        "parameters": {
            "type": "elastic_query",
            "names_to_ids": names_to_ids,
            "instructions": instructions,
        },
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + TEXT_TO_QUERY_BASE_ENDPOINT,
        json=text_to_query_payload,
    )

    query_data = response.get("results", {})[0].get("generated_query", {})

    query_data = _parse_and_enrich_query_data(query_data)
    
    # Ensure query has sort parameter
    if "sort" not in query_data:
        query_data["sort"] = [{"metadata.created_on": "desc"}]
    
    return query_data


async def _call_text_to_query_api_with_retry(
    search_prompt: str,
    artifact_types: List[str] | None,
    container_details: Container | None,
    resolved_names_mapping: List[dict] | None = None,
    max_attempts: int = MAX_QUERY_GENERATION_ATTEMPTS,
) -> tuple[dict, dict | None]:
    """Call text-to-query API with retry logic and query validation.
    
    Args:
        search_prompt: The user's search prompt
        artifact_types: List of artifact types to filter by
        container_details: Container information if specified
        resolved_names_mapping: List of resolved entity mappings with IDs
        max_attempts: Maximum number of retry attempts
        
    Returns:
        tuple: (query_data, validation_response) where validation_response contains
               the results from the validation call that can be reused
        
    Raises:
        Exception: If all retry attempts fail
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            LOGGER.info("Query generation attempt %d of %d", attempt + 1, max_attempts)
            query_data = await _call_text_to_query_api(
                search_prompt, artifact_types, container_details, resolved_names_mapping
            )
            
            # Validate query by executing with the default size to ensure:
            # 1. Query syntax is accepted by the external search API
            # 2. Query returns results (empty results trigger retry)
            # 3. API authentication and connectivity work
            # Validation results will be re-used if present
            user_requested_limit = query_data.get("size", MAX_SEARCH_RESULTS)
            validation_size = min(MAX_SEARCH_RESULTS, user_requested_limit)
            test_query = {**query_data, "size": validation_size}
            validation_response: dict[Any, Any] = await _fetch_search_page(query=test_query)
            
            LOGGER.info("Query validated successfully on attempt %d with size %d", attempt + 1, validation_size)
            return query_data, validation_response
            
        except (ExternalAPIError, ConnectionError, TimeoutError) as e:
            last_exception = e
            LOGGER.warning(
                "Query generation attempt %d failed: %s",
                attempt + 1,
                str(e)
            )
            if attempt == max_attempts - 1:
                LOGGER.error(
                    "All %d query generation attempts failed. Last error: %s",
                    max_attempts,
                    str(e)
                )
                raise
    
    # Should not reach here
    raise last_exception if last_exception else ServiceError("Query generation failed")


def _parse_and_enrich_query_data(query_data: dict | str) -> dict:
    """Parse query data from string if needed and ensure required _source fields are present."""
    if not isinstance(query_data, str):
        return query_data
    parsed: dict = json.loads(query_data)
    LOGGER.info("Parsed query string to object")
    if parsed.get("_source"):
        source = parsed["_source"]
        if isinstance(source, list):
            for required_field in ("metadata", "entity.assets", "artifact_id"):
                if required_field not in source:
                    source.append(required_field)
    return parsed


async def _fallback_response(
    request: TextToQuerySearchAssetRequest,
    query: dict | None = None,
) -> TextToQuerySearchAssetResponse:
    """Return a fallback response using the basic search_asset function."""
    response = await search_asset(search_prompt=request.search_prompt,
        container_type=request.container_type or "catalog",
        container_name=request.container_name)
    return TextToQuerySearchAssetResponse(
        generated_query=query or {}, response=response, message=None
    )


async def _fetch_search_page(query: dict) -> dict:
    """Execute a single search page request against the global search endpoint."""
    return await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json=query,
        params={"auth_cache": True, "tenant_scope": True}
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
        response = await _fetch_search_page(query=query_data)
    
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
            await _fetch_search_page(
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

@cached(ttl=1800)  # Cache for 30 minutes
async def _fetch_single_container_name(
    container_id: str,
    container_type: str,
    endpoint: str,
    params: Optional[dict] = None
) -> tuple[str, str | None]:
    """Fetch a single container name by ID and type.
    
    Cached for 30 minutes to reduce API calls for frequently accessed containers.
    
    Args:
        container_id: The ID of the container (project or catalog)
        container_type: Type of container ("project" or "catalog") for logging
        endpoint: API endpoint to use
        params: Optional query parameters
        
    Returns:
        Tuple of (container_id, name) where name may be None if fetch fails
    """
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{endpoint}/{container_id}",
            params=params,
            tool_name="dynamic_query_search"
        )
        name = response.get("entity", {}).get("name")
        if name:
            LOGGER.debug("Fetched %s name: %s -> %s", container_type, container_id, name)
        return (container_id, name)
    except Exception as e:
        LOGGER.warning("Failed to fetch %s name for %s: %s", container_type, container_id, str(e))
        return (container_id, None)


def _collect_container_ids(results: List[GlobalSearchAssetResponse]) -> tuple[set[str], set[str]]:
    """Collect unique project and catalog IDs from results.
    
    Args:
        results: List of GlobalSearchAssetResponse objects
        
    Returns:
        Tuple of (project_ids, catalog_ids) sets
    """
    project_ids = set()
    catalog_ids = set()
    
    for result in results:
        if result.project_id:
            project_ids.add(result.project_id)
        if result.catalog_id:
            catalog_ids.add(result.catalog_id)
    
    return project_ids, catalog_ids


def _process_fetch_results(results_tuples: list) -> dict[str, str]:
    """Process fetch results and build container names dictionary.
    
    Args:
        results_tuples: List of results from asyncio.gather
        
    Returns:
        Dictionary mapping container IDs to names
    """
    container_names = {}
    for result in results_tuples:
        if isinstance(result, Exception):
            LOGGER.warning("Exception during container name fetch: %s", str(result))
            continue
        container_id, name = result
        if name:
            container_names[container_id] = name
    return container_names


async def _fetch_container_names(results: List[GlobalSearchAssetResponse]) -> dict[str, str]:
    """
    Fetch project and catalog names for all unique container IDs in the results.
    
    Args:
        results: List of search results
        
    Returns:
        Dictionary mapping container IDs to their names (e.g., {"project-123": "My Project"})
    """
    project_ids, catalog_ids = _collect_container_ids(results)
    
    if not project_ids and not catalog_ids:
        return {}
    
    LOGGER.info(
        "Fetching names for %d projects and %d catalogs",
        len(project_ids),
        len(catalog_ids)
    )
    
    # Build tasks for parallel execution
    tasks = []
    tasks.extend([
        _fetch_single_container_name(pid, "project", PROJECTS_BASE_ENDPOINT)
        for pid in project_ids
    ])
    tasks.extend([
        _fetch_single_container_name(cid, "catalog", CATALOGS_BASE_ENDPOINT)
        for cid in catalog_ids
    ])
    
    results_tuples = await asyncio.gather(*tasks, return_exceptions=True)
    container_names = _process_fetch_results(results_tuples)
    
    LOGGER.info("Successfully fetched %d container names", len(container_names))
    return container_names




def _enrich_result_with_container_name(
    result: GlobalSearchAssetResponse,
    container_names: dict[str, str]
) -> None:
    """Enrich a single result with container names from the lookup dictionary.
    
    Args:
        result: The result to enrich (modified in place)
        container_names: Dictionary mapping container IDs to names
    """
    if result.project_id and result.project_id in container_names:
        result.project_name = container_names[result.project_id]
        LOGGER.debug(
            "Enriched project_name for %s: %s",
            result.project_id,
            result.project_name
        )
    
    if result.catalog_id and result.catalog_id in container_names:
        result.catalog_name = container_names[result.catalog_id]
        LOGGER.debug(
            "Enriched catalog_name for %s: %s",
            result.catalog_id,
            result.catalog_name
        )


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
            container_names = await _fetch_container_names(li)
            if container_names:
                for result in li:
                    _enrich_result_with_container_name(result, container_names)
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
