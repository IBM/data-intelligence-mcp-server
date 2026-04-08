# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.connections.models.copy_connection import CopyConnectionRequest, CopyConnectionResponse

from typing import Optional, Literal

from app.shared.logging import LOGGER, auto_context
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service

from app.services.constants import (
    JSON_PLUS_UTF8_ACCEPT_TYPE,
    CONNECTIONS_BASE_ENDPOINT,
)
from app.services.tool_utils import (
    retrieve_container_id,
    find_connection_id,
)

@service_registry.tool(
    name="copy_connection",
    description="""Understand user's request about creating a new connetion from an existing connection,
                    in other words, copying a connection, or using an existing connection in a different
                    container, and returning the details of the new connection.
                    Users are required to provide the identifier of the existing connection to be copied
                    and the identifier of the target container for the connection to be copied to. If the
                    users do not provide a source catalog, platform assets catalog is assumed as the
                    source catalog. If the users do not provide a target container type, project is assumed 
                    as the target container type.
                    Example: Create a new connection in AgentTest project from birddb connection in MCPTest.
                    In this case, connection_name is birddb, source_catalog is MCPTest, target_container is AgentTest, and target_container_type is project.
                    Example: Copy connection employee to WorkInfo.
                    In this case, connection_name is employee, target_container is WorkInfo, target_container_type is project, source_catalog is None.
                    Example: Create a connection from aws-jobs in workflows catalog.
                    In this case, connection_name is aws-jobs, target_container is workflows, target_container_type is catalog, source_catalog is None.
                    Example: Copy connection test-connection in Test catalog to AgentIssue project.
                    In this case, connection_name is test-connection, source_catalog is Test, target_container is AgentIssue, and target_container_type is project.
                    Example: I want to use the BirdDB connection in AgentTest project.
                    In this case, connection_name is BirdDB, target_container is AgentTest, target_container_type is project, source_catalog is None.

                    IMPORTANT CONSTRAINTS:
                    - connection_name must be provided
                    - target_container must be provided
                    - connection to be copied can only exist in a catalog
                    """,
    tags={"copy", "connection"},
    meta={"version": "1.0", "service": "connections"}
)
@auto_context
async def copy_connection(
    request: CopyConnectionRequest
) -> CopyConnectionResponse:

    # Analyze and fix the request parameters
    source_catalog = request.source_catalog or ""
    target_container_type = request.target_container_type or "project"

    LOGGER.info(
        "Starting copy connection with connection: '%s', source catalog: '%s', target container: '%s' and target container type: '%s'",
        request.connection_name,
        source_catalog,
        request.target_container,
        target_container_type
    )

    source_catalog_id = await retrieve_container_id(source_catalog, "catalog")
    target_container_id = await retrieve_container_id(request.target_container, target_container_type)

    connection_id = await find_connection_id(request.connection_name, source_catalog_id, "catalog")

    headers = {
        "accept": JSON_PLUS_UTF8_ACCEPT_TYPE,
        "Skip-Enforcement" : "false",
        "Content-Type": JSON_PLUS_UTF8_ACCEPT_TYPE
    }
    params = {
        "test": True,
        "persist": True,
        target_container_type + "_id": target_container_id,
        "userfs": False
    }
    payload = {
        "ref_catalog_id": source_catalog_id,
        "ref_asset_id": connection_id
    }

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}{CONNECTIONS_BASE_ENDPOINT}",
        headers=headers,
        params=params,
        json=payload,
        tool_name="copy_connection"
    )

    output = None
    metadata = response.get("metadata", {})
    if metadata:
        connection_name = response.get("entity", {}).get("name", "")
        output = CopyConnectionResponse(
            id=metadata["asset_id"],
            name=connection_name,
            create_time=metadata["create_time"],
            creator_id=metadata["creator_id"]
        )
    else:
        raise ServiceError(
            f"Could not copy connection {request.connection_name} from {source_catalog_id} catalog to {target_container_id} {target_container_type}"
        )

    return output

@service_registry.tool(
    name="copy_connection",
    description="""Understand user's request about creating a new connetion from an existing connection,
                    in other words, copying a connection, or using an existing connection in a different
                    container, and returning the details of the new connection.
                    Users are required to provide the identifier of the existing connection to be copied
                    and the identifier of the target container for the connection to be copied to. If the
                    users do not provide a source catalog, platform assets catalog is assumed as the
                    source catalog. If the users do not provide a target container type, project is assumed 
                    as the target container type.
                    Example: Create a new connection in AgentTest project from birddb connection in MCPTest.
                    In this case, connection_name is birddb, source_catalog is MCPTest, target_container is AgentTest, and target_container_type is project.
                    Example: Copy connection employee to WorkInfo.
                    In this case, connection_name is employee, target_container is WorkInfo, target_container_type is project, source_catalog is None.
                    Example: Create a connection from aws-jobs in workflows catalog.
                    In this case, connection_name is aws-jobs, target_container is workflows, target_container_type is catalog, source_catalog is None.
                    Example: Copy connection test-connection in Test catalog to AgentIssue project.
                    In this case, connection_name is test-connection, source_catalog is Test, target_container is AgentIssue, and target_container_type is project.
                    Example: I want to use the BirdDB connection in AgentTest project.
                    In this case, connection_name is BirdDB, target_container is AgentTest, target_container_type is project, source_catalog is None.

                    IMPORTANT CONSTRAINTS:
                    - connection_name must be provided
                    - target_container must be provided
                    - connection to be copied can only exist in a catalog
                    """,
    tags={"copy", "connection"},
    meta={"version": "1.0", "service": "connections"}
)
@auto_context
async def wxo_copy_connection(
    connection_name: str,
    target_container: str,
    source_catalog: Optional[str] = None,
    target_container_type: Optional[Literal["catalog", "project"]] = None,
) -> CopyConnectionResponse:
    """Watsonx Orchestrator compatible version that expands CopyConnectionRequest object into individual parameters."""

    request = CopyConnectionRequest(
        connection_name=connection_name,
        source_catalog=source_catalog,
        target_container=target_container,
        target_container_type=target_container_type,
    )

    # Call the original copy_connection function
    return await copy_connection(request)
