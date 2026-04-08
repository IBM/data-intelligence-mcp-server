# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.constants import (
    TEXT_TO_SQL_BASE_ENDPOINT,
)
from app.services.text_to_sql.models.generate_sql_query import (
    GenerateSqlQueryRequest,
    GenerateSqlQueryResponse,
)
from app.services.tool_utils import (
    check_if_container_is_enabled_for_text_to_sql,
    find_catalog_id,
    find_project_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


@service_registry.tool(
    name="text_to_sql_generate_sql_query",
    description="Generate the SQL query which addresses the request of the user and utilises the specified container.",
)
@auto_context
async def generate_sql_query(
    request: GenerateSqlQueryRequest,
) -> GenerateSqlQueryResponse:
    container_id = await confirm_uuid(
        request.container_id_or_name,
        find_catalog_id if request.container_type == "catalog" else find_project_id,
    )

    await check_if_container_is_enabled_for_text_to_sql(
        container_id, request.container_type
    )

    payload = {"query": request.request, "raw_output": "true", "add_sql_safety_check": "false"}

    LOGGER.info(
        "Calling generate_sql_query, container_id_or_name: %s, container_type: %s, request: %s",
        request.container_id_or_name,
        request.container_type,
        request.request,
    )

    params = {
        "container_id": container_id,
        "container_type": request.container_type,
        "dialect": "presto",
        "model_id": "meta-llama/llama-3-3-70b-instruct",
    }

    try:
        response = await tool_helper_service.execute_post_request(
            url=str(tool_helper_service.base_url) + TEXT_TO_SQL_BASE_ENDPOINT,
            params=params,
            json=payload,
        )

        generated_sql_query = response.get("generated_sql_queries", [])[0].get(
            "sql", ""
        )

    except Exception as e:
        if "422" in str(e):
            error_str = str(e)
            if "SAL0249E" in error_str:
                raise ServiceError(
                    f"SQL query generation failed for '{request.container_id_or_name}'. "
                    f"Please check if your question can be answered using {request.container_id_or_name}'s assets."
                )
            elif "SAL0248E" in error_str:
                raise ServiceError(
                    f"SQL query generation failed for '{request.container_id_or_name}'. "
                    f"DDL/DML operations detected in the question are not supported. Please try rephrasing your question."
                )
            elif "SAL0298E" in error_str:
                raise ServiceError(
                    f"SQL query generation failed for '{request.container_id_or_name}'. "
                    f"Invalid query was generated. Please try rephrasing your question."
                )
            else:
                # Generic 422 error message
                raise ServiceError(
                    f"SQL query generation failed for '{request.container_id_or_name}'. "
                )
        raise

    return GenerateSqlQueryResponse(
        generated_sql_query=generated_sql_query,
    )


@service_registry.tool(
    name="text_to_sql_generate_sql_query",
    description="Generate the SQL query which addresses the request of the user and utilises the specified container.",
)
@auto_context
async def wxo_generate_sql_query(
    request: str, container_id_or_name: str, container_type: str
) -> GenerateSqlQueryResponse:
    """Watsonx Orchestrator compatible version that expands GenerateSqlQueryRequest object into individual parameters."""

    req = GenerateSqlQueryRequest(
        request=request,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
    )

    # Call the original generate_sql_query function
    return await generate_sql_query(req)
