# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import uuid

from ..models.generate_sql_query import (
    GenerateSqlQueryRequest,
    GenerateSqlQueryResponse,
)

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.services.constants import (
    ASSISTANT_BASE_ENDPOINT,
    TEXT_TO_SQL_BASE_ENDPOINT,
)
from app.core.settings import settings
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.utils.helpers import get_closest_match, is_uuid
from app.shared.utils.http_client import get_http_client
from app.shared.logging import LOGGER, auto_context


async def find_project_id(project_name: str) -> str:
    """
    Find id of project based on project name.

    Args:
        project_name (str): The name of the project which is used to find a project id.

    Returns:
        uuid.UUID: Unique identifier of the project.
    """

    data = {"operation_type": "get_projects"}

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + ASSISTANT_BASE_ENDPOINT,
            data=data,
            headers=headers,
        )

        projects = response.get("projects")
        result_id = get_closest_match(projects, project_name)
        if result_id:
            return result_id
        else:
            raise ServiceError(
                f"find_project_id failed to find any projects with the name '{project_name}'"
            )
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(
            f"find_project_id failed to find any projects with name '{project_name}': {str(e)}"
        )


async def find_connection_id(connection_name: str, project_id: uuid) -> str:
    """
    Find id of connection based on connection name.

    Args:
        connection_name (str): The name of the connection which is used to find a connection id,
        project_id (uuid.UUID): The unique identifier of the project

    Returns:
        uuid.UUID: Unique identifier of the project.
    """

    data = {
        "operation_type": "get_connections",
        "get_connnections": {
            "asset_container": {
                "container_id": project_id,
                "container_type": "project",
            }
        },
    }

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + ASSISTANT_BASE_ENDPOINT,
            data=data,
            headers=headers,
        )

        connections = response.get("connections")
        result_id = get_closest_match(connections, connection_name)
        if result_id:
            return result_id
        else:
            raise ServiceError(
                f"find_connection_id failed to find any connections with the name '{connection_name}'"
            )
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(
            f"find_connection_id failed to find any connections with name '{connection_name}': {str(e)}"
        )


@service_registry.tool(
    name="text_to_sql_generate_sql_query",
    description="Generate the SQL query which addresses the request of the user and utilises the specified container.",
)
@auto_context
async def generate_sql_query(
    request: GenerateSqlQueryRequest,
) -> GenerateSqlQueryResponse:
    project_id = await find_project_id(request.project_name)
    is_uuid(project_id)

    data = {"query": request.request, "raw_output": "true"}

    LOGGER.info("Calling generate_sql_query, project_name: %s, connection_name: %s", request.project_name, request.connection_name)

    params = {
        "container_id": project_id,
        "container_type": "project",
        "dialect": "presto",
        "model_id": "meta-llama/llama-3-3-70b-instruct",
    }

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + TEXT_TO_SQL_BASE_ENDPOINT,
            params=params,
            data=data,
            headers=headers,
        )

        generated_sql_query = response.get("generated_sql_queries")[0].get("sql")
        connection_id = await find_connection_id(request.connection_name, project_id)
        is_uuid(connection_id)
        return GenerateSqlQueryResponse(
            project_id=project_id,
            connection_id=connection_id,
            generated_sql_query=generated_sql_query,
        )

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(f"Failed to run generate_sql_query tool: {str(e)}")
