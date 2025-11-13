# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import time
from typing import Dict, Any

from app.core.registry import service_registry
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.services.text_to_sql.models.create_asset_from_sql_query import (
    CreateAssetFromSqlQueryRequest,
    CreateAssetFromSqlQueryResponse,
)
from app.shared.utils.helpers import append_context_to_url
from app.shared.logging import auto_context
from app.shared.utils.tool_helper_service import tool_helper_service


def _build_asset_payload(request: CreateAssetFromSqlQueryRequest) -> Dict[str, Any]:
    """Build the complete asset payload from the request."""
    asset_name = f"agent_generated_{time.strftime('%Y-%m-%d %H-%M-%S')}"
    return {
        "metadata": {
            "project_id": request.project_id,
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
                "properties": [
                    {"name": "select_statement", "value": request.sql_query}
                ],
                "query_properties": [],
            },
            "discovered_asset": {
                "properties": {},
                "connection_id": request.connection_id,
                "connection_path": "",
                "extended_metadata": [{"name": "table_type", "value": "SQL_QUERY"}],
            },
        },
        "attachments": [
            {
                "connection_id": request.connection_id,
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
        request: The request containing project_id, connection_id, and sql_query.

    Returns:
        A response containing the URL of the newly created asset.

    Raises:
        ExternalAPIError: If the API request fails.
        ServiceError: If any other error occurs.
    """

    payload = _build_asset_payload(request)
    params = {"project_id": request.project_id}

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + CAMS_ASSETS_BASE_ENDPOINT,
        params=params,
        json=payload,
    )

    asset_id = response.get("asset_id")

    asset_url = append_context_to_url(
        f"{tool_helper_service.ui_base_url}/projects/{request.project_id}/data-assets/{asset_id}"
    )

    return CreateAssetFromSqlQueryResponse(asset_url=asset_url)


@service_registry.tool(
    name="text_to_sql_create_asset_from_sql_query",
    description="Create a new asset in the specified project and connection if provided based on the provided SQL query if creation of new asset was made explicitly.",
)
@auto_context
async def wxo_create_asset_from_sql_query(
    sql_query: str, project_id: str, connection_id: str
) -> CreateAssetFromSqlQueryResponse:
    """Watsonx Orchestrator compatible version that expands CreateAssetFromSqlQueryRequest object into individual parameters."""

    request = CreateAssetFromSqlQueryRequest(
        sql_query=sql_query, project_id=project_id, connection_id=connection_id
    )

    # Call the original create_asset_from_sql_query function
    return await create_asset_from_sql_query(request)
