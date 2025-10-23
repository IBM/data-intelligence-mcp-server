# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import time
from typing import Dict, Any

from ..models.create_asset_from_sql_query import (
    CreateAssetFromSqlQueryRequest,
    CreateAssetFromSqlQueryResponse,
)

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.utils.http_client import get_http_client
from app.shared.utils.helpers import append_context_to_url
from app.shared.logging import auto_context


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
    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}
    params = {"project_id": request.project_id}
    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + CAMS_ASSETS_BASE_ENDPOINT,
            params=params,
            data=payload,
            headers=headers,
        )

        asset_id = response.get("asset_id")

        asset_url = append_context_to_url(
            f"{settings.ui_url}/projects/{request.project_id}/data-assets/{asset_id}"
        )

        return CreateAssetFromSqlQueryResponse(asset_url=asset_url)
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(f"Failed to run create_asset_from_sql_query tool: {str(e)}")


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
