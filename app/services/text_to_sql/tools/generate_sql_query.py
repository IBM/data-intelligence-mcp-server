# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from ..models.generate_sql_query import (
    GenerateSqlQueryRequest,
    GenerateSqlQueryResponse,
)

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.services.constants import (
    CONNECTIONS_BASE_ENDPOINT,
    GEN_AI_SETTINGS_BASE_ENDPOINT,
    JSON_CONTENT_TYPE,
    PROJECTS_BASE_ENDPOINT,
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

    auth = await get_access_token()

    headers = {"Content-Type": JSON_CONTENT_TYPE, "Authorization": auth}

    params = {"limit": 100}

    client = get_http_client()

    try:
        response = await client.get(
            settings.di_service_url + PROJECTS_BASE_ENDPOINT,
            params=params,
            headers=headers,
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
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(
            f"find_project_id failed to find any projects with name '{project_name}': {str(e)}"
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

    auth = await get_access_token()

    headers = {"Content-Type": JSON_CONTENT_TYPE, "Authorization": auth}

    params = {"project_id": project_id}

    client = get_http_client()

    try:
        response = await client.get(
            settings.di_service_url + CONNECTIONS_BASE_ENDPOINT,
            headers=headers,
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
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(
            f"find_connection_id failed to find any connections with name '{connection_name}': {str(e)}"
        )

async def _check_if_project_is_enabled_for_text_to_sql(project_id) -> None:
    """
    Check if the project is enabled for text to sql.

    Args:
        project_id (str): The project id.
    """

    auth = await get_access_token()

    headers = {"Content-Type": JSON_CONTENT_TYPE, "Authorization": auth}

    params = {
        "container_id": project_id,
        "container_type": "project",
    }

    client = get_http_client()

    try:
        response = await client.get(
            settings.di_service_url + GEN_AI_SETTINGS_BASE_ENDPOINT,
            params=params,
            headers=headers,
        )

        if not (
            response.get("enable_gen_ai") and response.get("onboard_metadata_for_gen_ai")
        ):
            raise ServiceError(
                f"Project with id: {project_id} is not enabled for text2sql, please enable it first."
            )

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(
            f"_check_if_project_is_enabled_for_text_to_sql failed to find if project with id '{project_id}' is enabled for text2sql: {str(e)}"
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

    await _check_if_project_is_enabled_for_text_to_sql(project_id)

    payload = {"query": request.request, "raw_output": "true"}

    LOGGER.info(
        "Calling generate_sql_query, project_name: %s, connection_name: %s",
        request.project_name,
        request.connection_name,
    )

    params = {
        "container_id": project_id,
        "container_type": "project",
        "dialect": "presto",
        "model_id": "meta-llama/llama-3-3-70b-instruct",
    }

    auth = await get_access_token()

    headers = {"Content-Type": JSON_CONTENT_TYPE, "Authorization": auth}

    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + TEXT_TO_SQL_BASE_ENDPOINT,
            params=params,
            data=payload,
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


@service_registry.tool(
    name="text_to_sql_generate_sql_query",
    description="Generate the SQL query which addresses the request of the user and utilises the specified container.",
)
@auto_context
async def wxo_generate_sql_query(
    request: str, project_name: str, connection_name: str
) -> GenerateSqlQueryResponse:
    """Watsonx Orchestrator compatible version that expands GenerateSqlQueryRequest object into individual parameters."""

    req = GenerateSqlQueryRequest(
        request=request, project_name=project_name, connection_name=connection_name
    )

    # Call the original generate_sql_query function
    return await generate_sql_query(req)
