# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool


from app.core.registry import service_registry
from app.services.search.models.container import (
    FindContainerRequest,
    FindContainerResponse,
    Container,
    ContainerType,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.helpers import is_uuid_bool
from app.shared.exceptions.base import ServiceError
from app.services.tool_utils import find_asset_container_by_id, find_asset_container_by_name
from app.shared.utils.utils_tools import format_containers_for_table


async def _find_container(
    request: FindContainerRequest
) -> FindContainerResponse:
    """
    Find a container by ID or name.
    
    Args:
        request: FindContainerRequest containing container_id_or_name and container_type
        
    Returns:
        FindContainerResponse with the found container or None if not found
        
    Raises:
        ServiceError: If invalid parameters provided
    """
    if not request.container_id_or_name or request.container_id_or_name.strip() == "":
        error_msg = "container_id_or_name cannot be empty"
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)

    LOGGER.info(
        "Starting find_container with container_id_or_name: '%s' and container_type: '%s'",
        request.container_id_or_name,
        request.container_type,
    )

    # Check if the input is a UUID
    passed_uuid = is_uuid_bool(request.container_id_or_name)

    try:
        if passed_uuid:
            container = await find_asset_container_by_id(
                request.container_id_or_name, request.container_type.value
            )
        else:
            container = await find_asset_container_by_name(
                request.container_id_or_name, request.container_type.value
            )

        LOGGER.info(
            "Found container: id='%s', name='%s', type='%s'",
            container.id,
            container.name,
            container.type,
        )

        ui_message_context.add_table_ui_message("find_container", format_containers_for_table([container]), title="Containers")
        return FindContainerResponse(container=container)
    
    except ServiceError as e:
        # If container not found, return response with None container instead of raising error
        if "Couldn't find any" in str(e):
            LOGGER.info(
                "No %s found with identifier '%s'",
                request.container_type.value,
                request.container_id_or_name
            )
            return FindContainerResponse(container=None)
        # Re-raise other ServiceErrors
        raise


@service_registry.tool(
    name="find_container",
    description="""Finds a specific container (catalog, project or space) by ID or name.
    
    This tool searches for a container using either its UUID or name.
    
    IMPORTANT CONSTRAINTS:
    - container_id_or_name is required and cannot be empty
    - Automatically detects if input is a UUID or name
    - For UUID: performs direct lookup
    - For name: uses fuzzy matching to find closest match
    - container_type must be one of: "catalog", "project", "space"
    - Returns container details including ID, name, type, and URL""",
)
@auto_context
async def find_container(
    container_id_or_name: str,
    container_type: str = "catalog"
) -> FindContainerResponse:
    """Wrapper that expands FindContainerRequest object into individual parameters."""
    
    # Convert string to ContainerType enum
    container_type_enum = ContainerType(container_type)
    request = FindContainerRequest(
        container_id_or_name=container_id_or_name,
        container_type=container_type_enum
    )
    
    # Call the original find_container function
    return await _find_container(request)
