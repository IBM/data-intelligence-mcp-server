# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import re
from typing import List, Set

from app.core.registry import service_registry
from app.core.auth import get_bss_account_id
from app.services.constants import (
    PROJECTS_BASE_ENDPOINT,
    CATALOGS_BASE_ENDPOINT,
    SPACES_BASE_ENDPOINT,
)
from app.services.search.models.container import (
    ListContainersRequest,
    ListContainersResponse,
    Container,
    ContainerType,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.helpers import get_project_or_space_type_based_on_context
from app.core.settings import settings
from app.services.tool_utils import _build_container_from_response


def _parse_container_types(container_type_str: str) -> Set[str]:
    """
    Parse container type string and return a set of normalized container types.
    Handles various formats like "catalog,project", "projects and catalogs", etc.
    
    Args:
        container_type_str: The container type string to parse
        
    Returns:
        Set[str]: Set of normalized container types ("catalog", "project", "space")
    """
    # Normalize the string: lowercase, remove extra spaces
    normalized = container_type_str.lower().strip()
    
    # Handle "all" case
    if normalized == "all":
        return {"catalog", "project", "space"}
    
    # Split by common delimiters: comma, "and", spaces
    # Using a safe regex pattern to avoid ReDoS vulnerability
    parts = re.split(r'[,\s]+', normalized.replace(' and ', ' '))
    
    container_types = set()
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Remove trailing 's' to handle plurals (catalogs -> catalog, projects -> project)
        if part.endswith('s') and len(part) > 1:
            part = part[:-1]
        
        # Map to valid container types
        if part in ["catalog", "project", "space"]:
            container_types.add(part)
    
    return container_types if container_types else {"catalog", "project", "space"}


async def _list_single_container_type(container_type: str) -> List[Container]:
    """
    List all containers of a single given type.
    
    Args:
        container_type: The type of the container - "project", "catalog", or "space"
        
    Returns:
        List[Container]: List of container objects of given type
    """
    params = {"limit": 100}
    
    if container_type == "project":
        params["bss_account_id"] = await get_bss_account_id()
        project_type = get_project_or_space_type_based_on_context()
        if project_type:
            params["type"] = project_type
            
        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.base_url) + PROJECTS_BASE_ENDPOINT,
            params=params,
        )
        
        return [
            _build_container_from_response(resource, "project", "guid")
            for resource in response.get("resources", [])
        ]
        
    elif container_type == "space":
        params["bss_account_id"] = await get_bss_account_id()
        space_type = get_project_or_space_type_based_on_context()
        if space_type:
            params["type"] = space_type
            
        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.base_url) + SPACES_BASE_ENDPOINT,
            params=params,
        )
        
        return [
            _build_container_from_response(resource, "space", "id")
            for resource in response.get("resources", [])
        ]
        
    else:  # "catalog"
        params["bss_account_id"] = await get_bss_account_id()
        
        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.base_url) + CATALOGS_BASE_ENDPOINT,
            params=params,
        )
        
        return [
            _build_container_from_response(catalog, "catalog", "guid")
            for catalog in response.get("catalogs", [])
        ]


async def _list_asset_containers(container_type: ContainerType) -> List[Container]:
    """
    List all containers of given type(s).
    
    Args:
        container_type: The type of the container - supports various formats
        
    Returns:
        List[Container]: List of container objects of given type
    """
    # Parse the container type string to get normalized types
    container_types = _parse_container_types(str(container_type))
    
    # Fetch containers for each type
    all_containers = []
    
    if "catalog" in container_types:
        catalogs = await _list_single_container_type("catalog")
        all_containers.extend(catalogs)
    
    if "project" in container_types:
        projects = await _list_single_container_type("project")
        all_containers.extend(projects)
    
    if "space" in container_types:
        spaces = await _list_single_container_type("space")
        all_containers.extend(spaces)
    
    return all_containers


@service_registry.tool(
    name="list_containers",
    description="""Lists all available containers - catalogs, projects or spaces.
    
    This tool finds all containers (catalogs, projects or spaces) that are available to the current user.
    
    IMPORTANT CONSTRAINTS:
    - container_type supports flexible formats: "catalog", "project", "space", "all"
    - Also supports combinations: "catalog,project", "projects and catalogs", "catalogs, projects", etc.
    - Handles both singular and plural forms
    - Defaults to "all" if not specified
    - Returns list of containers with their IDs, names, types, and URLs""",
)
@auto_context
async def list_containers(
    request: ListContainersRequest
) -> ListContainersResponse:
    """
    Lists all available containers based on the specified type.
    
    Args:
        request: ListContainersRequest containing container_type
        
    Returns:
        ListContainersResponse with list of containers and metadata
    """
    LOGGER.info(
        "Starting list_containers with container_type: '%s'",
        request.container_type,
    )

    containers = await _list_asset_containers(request.container_type)

    LOGGER.info(
        "Found %d containers of type '%s'",
        len(containers),
        request.container_type,
    )

    return ListContainersResponse(
        containers=containers,
        total_count=len(containers),
        container_type=request.container_type,
    )


@service_registry.tool(
    name="list_containers",
    description="""Lists all available containers - catalogs, projects or spaces.
    
    This tool finds all containers (catalogs, projects or spaces) that are available to the current user.
    
    IMPORTANT CONSTRAINTS:
    - container_type supports flexible formats: "catalog", "project", "space", "all"
    - Also supports combinations: "catalog,project", "projects and catalogs", "catalogs, projects", etc.
    - Handles both singular and plural forms
    - Defaults to "all" if not specified
    - Returns list of containers with their IDs, names, types, and URLs""",
)
@auto_context
async def wxo_list_containers(
    container_type: str = "all"
) -> ListContainersResponse:
    """Watsonx Orchestrator compatible version that expands ListContainersRequest object into individual parameters."""
    
    # Convert string to ContainerType enum
    container_type_enum = ContainerType(container_type)
    request = ListContainersRequest(container_type=container_type_enum)
    
    # Call the original list_containers function
    return await list_containers(request)
