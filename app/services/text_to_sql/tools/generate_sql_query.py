# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.constants import (
    GEN_AI_SETTINGS_BASE_ENDPOINT,
    TEXT_TO_SQL_BASE_ENDPOINT,
)
from app.services.text_to_sql.models.generate_sql_query import (
    GenerateSqlQueryRequest,
    GenerateSqlQueryResponse,
)
from app.services.tool_utils import find_connection_id, find_project_id
from app.shared.exceptions.base import ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import is_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


async def _check_if_project_is_enabled_for_text_to_sql(project_id) -> None:
    """
    Check if the project is enabled for text to sql.

    Args:
        project_id (str): The project id.
    """

    params = {
        "container_id": project_id,
        "container_type": "project",
    }

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + GEN_AI_SETTINGS_BASE_ENDPOINT,
        params=params,
    )

    if not (
        response.get("enable_gen_ai") and response.get("onboard_metadata_for_gen_ai")
    ):
        raise ServiceError(
            f"Project with id: {project_id} is not enabled for text2sql, please enable it first."
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

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + TEXT_TO_SQL_BASE_ENDPOINT,
        params=params,
        json=payload,
    )

    generated_sql_query = response.get("generated_sql_queries")[0].get("sql")
    connection_id = await find_connection_id(request.connection_name, project_id)
    is_uuid(connection_id)
    return GenerateSqlQueryResponse(
        project_id=project_id,
        connection_id=connection_id,
        generated_sql_query=generated_sql_query,
    )


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
