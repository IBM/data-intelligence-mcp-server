# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.services.constants import CONNECTIONS_BASE_ENDPOINT, PROJECTS_BASE_ENDPOINT
from app.shared.exceptions.base import ServiceError
from app.shared.utils.helpers import get_closest_match
from app.shared.utils.tool_helper_service import tool_helper_service


async def find_project_id(project_name: str) -> str:
    """
    Find id of project based on project name.

    Args:
        project_name (str): The name of the project which is used to find a project id.

    Returns:
        uuid.UUID: Unique identifier of the project.
    """

    params = {"limit": 100}

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + PROJECTS_BASE_ENDPOINT,
        params=params,
    )

    projects = [
        {"name": project["entity"]["name"], "id": project["metadata"]["guid"]}
        for project in response.get("resources", {})
    ]
    result_id = get_closest_match(projects, project_name)
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"find_project_id failed to find any projects with the name '{project_name}'"
        )


async def find_connection_id(connection_name: str, project_id: str) -> str:
    """
    Find id of connection based on connection name.

    Args:
        connection_name (str): The name of the connection which is used to find a connection id,
        project_id (uuid.UUID): The unique identifier of the project

    Returns:
        uuid.UUID: Unique identifier of the project.
    """

    params = {"project_id": project_id}

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + CONNECTIONS_BASE_ENDPOINT,
        params=params,
    )

    connections = [
        {
            "name": connection["entity"]["name"],
            "id": connection["metadata"]["asset_id"],
        }
        for connection in response.get("resources", {})
    ]
    result_id = get_closest_match(connections, connection_name)
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"find_connection_id failed to find any connections with the name '{connection_name}'"
        )
