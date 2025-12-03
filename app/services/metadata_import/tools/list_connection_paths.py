# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from typing import Optional, List
from app.shared.logging import LOGGER, auto_context
from app.core.registry import service_registry
from app.services.tool_utils import find_project_id, find_connection_id
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.metadata_import.models.list_connection_paths import (
    ListConnectionPathsRequest,
    ListConnectionPathsResponse,
)


@service_registry.tool(
    name="list_connection_paths",
    description="""
    List available schema/table paths for a connection.
    
    ⚠️ CALL THIS TOOL FIRST when:
    - User mentions "first N schemas" (e.g., "first 7 schemas")
    - User does NOT explicitly provide schema names
    - You need to discover what schemas/tables are available
    
    Use the 'limit' parameter to control how many schemas to retrieve:
    - For "first 7 schemas", set limit=7
    - For "first 10 schemas", set limit=10
    - Default is 10 if not specified
    
    After calling this tool, use the returned schema list as the 'scope' parameter
    when calling create_metadata_import.
    
    Returns:
        ListConnectionPathsResponse: Response containing list of schema/table paths and count.
    """,
    tags={"list_connection", "metadata_import"},
    meta={"version": "1.0", "service": "metadata_import"},
)
@auto_context
async def list_connection_paths(
    request: ListConnectionPathsRequest,
) -> ListConnectionPathsResponse:
    
    project_id = await find_project_id(request.project_name)
    connection_id = await find_connection_id(request.connection_name, project_id)

    LOGGER.info(
        "Calling tool 'list_connection_paths' to get connection schemas for connection %s in project %s",
        connection_id,
        project_id,
    )

    url = f"{tool_helper_service.base_url}/v2/connections/{connection_id}/assets"

    limit = request.limit
    # If a filter is provided, request full set from service so we can apply local filtering
    if request.filter_text is not None and str(request.filter_text).strip() != "":
        limit = -1

    params = {"project_id": project_id, "path": "/", "limit": limit, "offset": request.offset}

    response = await tool_helper_service.execute_get_request(
        url=url, params=params, tool_name="list_connection_paths"
    )
    assets = response.get("assets", [])

    paths = [a["path"] for a in assets if isinstance(a, dict) and "path" in a]

    if request.filter_text:
        paths = [p for p in paths if request.filter_text.lower() in p.lower()]

    LOGGER.info("Found schemas (first 10): %s", paths[:10])
    # Return up to `limit` items to respect pagination (limit may be -1 meaning all)
    final_paths = paths[:10] if (request.limit is None or request.limit == -1) else paths[: request.limit]
    return ListConnectionPathsResponse(paths=final_paths, count=len(final_paths))


@service_registry.tool(
    name="list_connection_paths",
    description="""
    List available schema/table paths for a connection.
    
    ⚠️ CALL THIS TOOL FIRST when:
    - User mentions "first N schemas" (e.g., "first 7 schemas")
    - User does NOT explicitly provide schema names
    - You need to discover what schemas/tables are available
    
    Use the 'limit' parameter to control how many schemas to retrieve:
    - For "first 7 schemas", set limit=7
    - For "first 10 schemas", set limit=10
    - Default is 10 if not specified
    
    After calling this tool, use the returned schema list as the 'scope' parameter
    when calling create_metadata_import.
    
    Returns:
        ListConnectionPathsResponse: Response containing list of schema/table paths and count.
    """,
    tags={"metadata-import", "wxo"},
    meta={"version": "1.0", "service": "metadata-import"},
)
@auto_context
async def wxo_list_connection_paths(
    project_name: str, connection_name: str, offset: Optional[int] = 1, limit: Optional[int] = 10, filter_text: Optional[str] = None
) -> ListConnectionPathsResponse:
    """Watsonx Orchestrator compatible wrapper that expands params into a `ListConnectionPathsRequest` and calls the tool."""

    request = ListConnectionPathsRequest(
        project_name=project_name,
        connection_name=connection_name,
        offset=offset,
        limit=limit,
        filter_text=filter_text,
    )

    return await list_connection_paths(request)
