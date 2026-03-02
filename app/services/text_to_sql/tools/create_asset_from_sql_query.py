# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from functools import partial
import re
import time
from typing import Dict, Any

from app.core.registry import service_registry
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.services.text_to_sql.models.create_asset_from_sql_query import (
    CreateAssetFromSqlQueryRequest,
    CreateAssetFromSqlQueryResponse,
)
from app.services.tool_utils import find_catalog_id, find_connection_id, find_project_id
from app.shared.exceptions.base import ServiceError
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import append_context_to_url, confirm_uuid
from app.shared.logging import auto_context
from app.shared.utils.tool_helper_service import tool_helper_service


def _validate_sql_query(sql_query: str) -> None:
    """
    Validate SQL query to prevent SQL injection and dangerous operations.
    
    This function checks for:
    1. Multiple statements (semicolon-separated)
    2. Dangerous SQL keywords (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, etc.)
    3. SQL comments that could hide malicious code
    
    Args:
        sql_query: The SQL query to validate
        
    Raises:
        ServiceError: If the query contains dangerous patterns
    """
    if not sql_query or not sql_query.strip():
        raise ServiceError("SQL query cannot be empty")
    
    # Remove leading/trailing whitespace
    query = sql_query.strip()
    
    # Check for multiple statements (SQL injection attempt)
    # Split by semicolon but ignore semicolons in strings
    statements = re.split(r';(?=(?:[^\'"]|[\'"][^\'"]*[\'"])*$)', query)
    # Filter out empty statements (trailing semicolons are ok)
    non_empty_statements = [s.strip() for s in statements if s.strip()]
    
    if len(non_empty_statements) > 1:
        raise ServiceError(
            "SQL injection attempt detected: Multiple SQL statements are not allowed. "
            "Only single SELECT queries are permitted."
        )
    
    # Check for dangerous SQL keywords (case-insensitive)
    # These operations should not be allowed in a query asset
    dangerous_keywords = [
        r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', r'\bINSERT\b',
        r'\bALTER\b', r'\bTRUNCATE\b', r'\bCREATE\b', r'\bREPLACE\b',
        r'\bEXEC\b', r'\bEXECUTE\b', r'\bGRANT\b', r'\bREVOKE\b',
        r'\bMERGE\b', r'\bCALL\b', r'\bRENAME\b'
    ]
    
    query_upper = query.upper()
    for keyword_pattern in dangerous_keywords:
        if re.search(keyword_pattern, query_upper):
            keyword = keyword_pattern.replace(r'\b', '').replace('\\', '')
            raise ServiceError(
                f"Dangerous SQL operation detected: {keyword} statements are not allowed. "
                f"Only SELECT queries are permitted for creating query assets."
            )
    
    # Check for SQL comments that could hide malicious code
    comment_patterns = [
        r'--',  # Single-line comment
        r'/\*',  # Multi-line comment start
        r'\*/',  # Multi-line comment end
    ]
    
    for pattern in comment_patterns:
        if re.search(pattern, query):
            raise ServiceError(
                "SQL comments are not allowed in query assets as they could hide malicious code."
            )
    
    # Ensure the query starts with SELECT (case-insensitive)
    if not re.match(r'^\s*SELECT\b', query, re.IGNORECASE):
        raise ServiceError(
            "Only SELECT queries are allowed for creating query assets. "
            "The query must start with SELECT."
        )


def _build_asset_payload(
    container_id, container_type, connection_id, sql_query, asset_name=None
) -> Dict[str, Any]:
    """
    Build the complete asset payload from the request.
    
    Note: SQL query validation should be done before calling this function.
    """
    asset_name = (
        asset_name
        if asset_name
        else f"agent_generated_{time.strftime('%Y-%m-%d %H-%M-%S')}"
    )
    return {
        "metadata": {
            f"{container_type}_id": container_id,
            "name": asset_name,
            "asset_type": "data_asset",
            "asset_attributes": ["data_asset", "discovered_asset"],
            "tags": ["connected-data"],
            "description": "",
        },
        "entity": {
            "data_asset": {
                "mime_type": "application/x-ibm-rel-table",
                "dataset": True,
                "properties": [{"name": "select_statement", "value": sql_query}],
                "query_properties": [],
            },
            "discovered_asset": {
                "properties": {},
                "connection_id": connection_id,
                "connection_path": "",
                "extended_metadata": [{"name": "table_type", "value": "SQL_QUERY"}],
            },
        },
        "attachments": [
            {
                "connection_id": connection_id,
                "mime": "application/x-ibm-rel-table",
                "asset_type": "data_asset",
                "name": asset_name,
                "description": "",
                "private_url": False,
                "connection_path": "/",
                "data_partitions": 1,
            }
        ],
    }


@service_registry.tool(
    name="text_to_sql_create_asset_from_sql_query",
    description="Create a new asset in the specified project and connection if provided based on the provided SQL query if creation of new asset was made explicitly.",
)
@auto_context
async def create_asset_from_sql_query(
    request: CreateAssetFromSqlQueryRequest,
) -> CreateAssetFromSqlQueryResponse:
    """
    Create a new asset in the specified project based on the provided SQL query.

    Args:
        request: The request containing container_id_or_name, container_type, connection_id_or_name, asset_name, and sql_query.

    Returns:
        A response containing the URL of the newly created asset.

    Raises:
        ExternalAPIError: If the API request fails.
        ServiceError: If any other error occurs.
    """
    LOGGER.info(
        "Calling create_asset_from_sql_query, container_id_or_name: %s, connection_id_or_name: %s, asset_name: %s",
        request.container_id_or_name,
        request.connection_id_or_name,
        request.asset_name,
    )
    
    # Validate SQL query for security before processing
    _validate_sql_query(request.sql_query)

    container_id = await confirm_uuid(
        request.container_id_or_name,
        find_catalog_id if request.container_type == "catalog" else find_project_id,
    )
    connection_id = await confirm_uuid(
        request.connection_id_or_name,
        partial(
            find_connection_id,
            container_id=container_id,
            container_type=request.container_type,
        ),
    )

    payload = _build_asset_payload(
        container_id,
        request.container_type,
        connection_id,
        request.sql_query,
        request.asset_name,
    )
    params = {f"{request.container_type}_id": container_id}

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + CAMS_ASSETS_BASE_ENDPOINT,
        params=params,
        json=payload,
    )

    asset_id = response.get("asset_id")

    asset_url = append_context_to_url(
        f"{tool_helper_service.ui_base_url}/data/catalogs/{container_id}/asset/{asset_id}"
        if request.container_type == "catalog"
        else f"{tool_helper_service.ui_base_url}/projects/{container_id}/data-assets/{asset_id}"
    )

    return CreateAssetFromSqlQueryResponse(asset_url=asset_url)


@service_registry.tool(
    name="text_to_sql_create_asset_from_sql_query",
    description="Create a new asset in the specified project and connection if provided based on the provided SQL query if creation of new asset was made explicitly.",
)
@auto_context
async def wxo_create_asset_from_sql_query(
    sql_query: str,
    container_id_or_name: str,
    container_type: str,
    connection_id_or_name: str,
    asset_name: str | None = None,
) -> CreateAssetFromSqlQueryResponse:
    """Watsonx Orchestrator compatible version that expands CreateAssetFromSqlQueryRequest object into individual parameters."""

    request = CreateAssetFromSqlQueryRequest(
        sql_query=sql_query,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
        connection_id_or_name=connection_id_or_name,
        asset_name=asset_name,
    )

    # Call the original create_asset_from_sql_query function
    return await create_asset_from_sql_query(request)
