# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from ..models.create_asset_from_sql_query import (
    CreateAssetFromSqlQueryRequest,
    CreateAssetFromSqlQueryResponse,
)

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import ASSISTANT_BASE_ENDPOINT
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.utils.helpers import is_none
from app.shared.utils.http_client import get_http_client
from app.shared.logging import auto_context


@service_registry.tool(
    name="text_to_sql_create_asset_from_sql_query",
    description="Create a new asset in the specified project and connection if provided based on the provided SQL query if creation of new asset was made explicitly..",
)
@auto_context
async def create_asset_from_sql_query(
    request: CreateAssetFromSqlQueryRequest,
) -> CreateAssetFromSqlQueryResponse:
    data = {
        "operation_type": "create_sql_asset",
        "create_sql_query_asset": {
            "sql_query": request.sql_query,
            "asset_container": {
                "container_id": request.project_id,
                "container_type": "project",
            },
            "connection_id": (
                None if is_none(request.connection_id) else request.connection_id
            ),
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

        asset_url = str(response.get("summary"))
        if "<ui_base_url>" in asset_url:
            asset_url = asset_url.replace("<ui_base_url>", f"{settings.ui_url}")

        return CreateAssetFromSqlQueryResponse(asset_url=asset_url)
    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ServiceError(f"Failed to run create_asset_from_sql_query tool: {str(e)}")
