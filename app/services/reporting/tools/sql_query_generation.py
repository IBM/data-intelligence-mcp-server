# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.auth import get_bss_account_id
from app.core.registry import service_registry
from app.services.constants import (
    GEN_AI_SETTINGS_BASE_ENDPOINT,
    REPORTING_BASE_ENDPOINT,
    TEXT_TO_SQL_BASE_ENDPOINT,
)
from app.services.reporting.models.sql_query_generation import (
    SqlQueryGenerationRequest,
    SqlQueryGenerationResponse,
)
from app.services.tool_utils import find_project_id
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import is_uuid
from app.shared.utils.tool_helper_service import tool_helper_service

# Database type mapping for SQL dialects
DB_TYPE_MAPPING = {
    "postgresql": "postgresql",
    "mssql": "mssql",
    "oracle": "oracle",
    "db2": "db2",
}

# Placeholder constants for quote replacement
SINGLE_QUOTE_REPLACEMENT = "<!--__SPLACEHOLDER__-->"
DOUBLE_QUOTE_REPLACEMENT = "<!--__DPLACEHOLDER__-->"


def _escape_sql_quotes(sql_query: str) -> str:
    """
    Escape quotes in SQL strings by replacing them with placeholders.

    Args:
        sql_query (str): The SQL query with quotes.

    Returns:
        str: The SQL query with escaped quotes.
    """
    return sql_query.replace("'", SINGLE_QUOTE_REPLACEMENT).replace(
        '"', DOUBLE_QUOTE_REPLACEMENT
    )


async def _check_if_project_is_enabled_for_text_to_sql(project_id: str) -> None:
    """
    Check if the project is enabled for text to sql.

    Args:
        project_id (str): The project id.

    Raises:
        ServiceError: If the project is not enabled for text to sql.
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
    name="reporting_sql_query_generation",
    description="Generate a SQL query from a natural language input for a given project using a text-to-SQL service for reporting-related use cases. The tool verifies reporting service connectivity, resolves the project ID, and generates the SQL query based on the project context and SQL dialect.",
)
@auto_context
async def sql_query_generation(
    request: SqlQueryGenerationRequest,
) -> SqlQueryGenerationResponse:
    """
    Generate a SQL query from a natural language input for a given project.

    This tool is specifically designed for reporting database use cases. SQL generation
    is powered by the meta-llama/llama-3-3-70b-instruct model. The SQL dialect is
    determined based on the tenant's database, as returned by the handshake API.
    Supported dialects include: 'postgresql', 'mssql', 'oracle', and 'db2'.

    Args:
        request (SqlQueryGenerationRequest): The request containing project name, query,
            instructions, and raw_output flag.

    Returns:
        SqlQueryGenerationResponse: The result of the SQL query generation, containing either:
            - On success: status="success", project_id, generated_sql_query, and dialect
            - On failure: status="failed", message with error details

    Raises:
        ServiceError: If handshake fails, project is not enabled, or database type is unsupported.
        ExternalAPIError: If the API call to generate SQL fails.
    """
    LOGGER.info(
        f"Starting reporting_sql_query_generation for project_name={request.project_name}, "
        f"query={request.query}, instructions={request.instructions}, raw_output={request.raw_output}"
    )

    # Handshake API call to get database type
    tenant_id = await get_bss_account_id()
    handshake_url = f"{tool_helper_service.base_url}{REPORTING_BASE_ENDPOINT}/{tenant_id}/handshake"

    try:
        handshake_response = await tool_helper_service.execute_get_request(
            url=handshake_url
        )
    except Exception as e:
        LOGGER.error(f"Handshake API call failed: {e}")
        raise ExternalAPIError(
            f"Handshake API call failed: {str(e)}",
            service="reporting",
            tool="sql_query_generation",
        )

    if handshake_response.get("status") != "ACTIVE":
        LOGGER.error(
            f"Handshake failed or status not active: {handshake_response}"
        )
        raise ServiceError(
            f"Handshake failed or status not active: {handshake_response}"
        )

    db_type = handshake_response.get("db_type")
    if db_type is None:
        return SqlQueryGenerationResponse(
            status="failed",
            message="Database type not found in handshake response",
        )

    dialect = DB_TYPE_MAPPING.get(db_type)

    # Handle unmapped db_type
    if dialect is None:
        return SqlQueryGenerationResponse(
            status="failed",
            message=f"Unsupported db_type: {db_type}",
        )

    # Resolve project_id
    project_id = await find_project_id(request.project_name)
    is_uuid(project_id)

    # Check if project is enabled for text to sql
    await _check_if_project_is_enabled_for_text_to_sql(project_id)

    # SQL Generation API call
    text_to_sql_url = f"{tool_helper_service.base_url}{TEXT_TO_SQL_BASE_ENDPOINT}"

    params = {
        "container_id": project_id,
        "container_type": "project",
        "dialect": dialect,
        "model_id": "meta-llama/llama-3-3-70b-instruct",
    }

    json_payload = {
        "instructions": request.instructions,
        "query": request.query,
        "raw_output": request.raw_output,
    }

    try:
        response = await tool_helper_service.execute_post_request(
            url=text_to_sql_url,
            json=json_payload,
            params=params,
        )
    except Exception as e:
        LOGGER.error(f"SQL generation API call failed: {e}")
        raise ExternalAPIError(
            f"SQL generation API call failed: {str(e)}",
            service="reporting",
            tool="sql_query_generation",
        )

    if not response or "generated_sql_queries" not in response:
        LOGGER.error(f"SQL generation failed: {response}")
        return SqlQueryGenerationResponse(
            status="failed",
            message=f"SQL generation failed: {response}",
        )

    generated_sql_queries = response.get("generated_sql_queries")
    if not generated_sql_queries or len(generated_sql_queries) == 0:
        LOGGER.error("SQL generation failed: No SQL queries generated")
        return SqlQueryGenerationResponse(
            status="failed",
            message="SQL generation failed: No SQL queries generated",
        )

    generated_sql_query = _escape_sql_quotes(generated_sql_queries[0].get("sql"))

    LOGGER.info(
        f"Successfully generated SQL query via reporting_sql_query_generation for project {project_id}"
    )

    return SqlQueryGenerationResponse(
        status="success",
        project_id=project_id,
        generated_sql_query=generated_sql_query,
        dialect=dialect,
    )


@service_registry.tool(
    name="reporting_sql_query_generation",
    description="Generate a SQL query from a natural language input for a given project using a text-to-SQL service for reporting-related use cases. The tool verifies reporting service connectivity, resolves the project ID, and generates the SQL query based on the project context and SQL dialect.",
)
@auto_context
async def wxo_sql_query_generation(
    project_name: str,
    query: str,
    instructions: list | None = None,
    raw_output: bool = False,
) -> SqlQueryGenerationResponse:
    """
    Watsonx Orchestrator compatible version that expands SqlQueryGenerationRequest object into individual parameters.

    Args:
        project_name (str): Name of the project containing the data model for SQL generation.
        query (str): Natural language request to convert to SQL.
        instructions (list): Instructions for SQL generation. Defaults to empty list.
        raw_output (bool): Whether to return raw output from the model. Defaults to False.

    Returns:
        SqlQueryGenerationResponse: The result of the SQL query generation.
    """
    if instructions is None:
        instructions = []

    req = SqlQueryGenerationRequest(
        project_name=project_name,
        query=query,
        instructions=instructions,
        raw_output=raw_output,
    )

    # Call the original sql_query_generation function
    return await sql_query_generation(req)