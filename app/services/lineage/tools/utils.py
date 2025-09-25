# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from typing import Any

from app.core.auth import get_access_token
from app.core.settings import settings
from app.services.constants import LINEAGE_BASE_ENDPOINT
from app.shared.exceptions.base import ExternalAPIError
from app.shared.utils.http_client import get_http_client


async def call_get_lineage_graph(lineage_id: str) -> dict[str, Any]:
    """
    This function returns nodes in lineage graph of lineage asset.

    Args:
        lineage_id (str): lineage id of the starting asset for lineage graph

    Returns:
        dict[str, Any]: Response from the lineage service.
    Raises:
        ExternalAPIError: If the call finishes unsuccessfully
    """

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    client = get_http_client()

    data = {
        "initial_asset_ids": [lineage_id],
        "allow_lineage_cache": "false",
        "visible_asset_ids": [lineage_id],
        "expansion": {
            "starting_asset_ids": [lineage_id],
            "incoming_steps": "3",
            "outgoing_steps": "3",
        },
    }

    try:
        response = await client.post(
            settings.di_service_url + LINEAGE_BASE_ENDPOINT + "/query_lineage",
            data=data,
            headers=headers,
        )
        return response

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ExternalAPIError(f"Failed to get lineage graph: {str(e)}")


async def convert_to_lineage_id(container_id: str, asset_id: str) -> str:
    """
    This function takes container_id and asset_id as parameters and returns a unique lineage identifier.

    Args:
        container_id (str): The container id. This can be either catalog id or project id.
        asset_id (str): The asset id.

    Returns:
       str : Lineage id.
    Raises:
        ExternalAPIError: If the call finishes unsuccessfully
    """

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    client = get_http_client()

    params = {
        "container_id": container_id,
        "asset_id": asset_id,
        "validate_lineage_entity": False,
    }

    try:
        response = await client.get(
            url=settings.di_service_url + LINEAGE_BASE_ENDPOINT + "/entities",
            params=params,
            headers=headers,
        )
        return response.get("entities")[0].get("id")

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ExternalAPIError(f"Failed to get lineage_id: {str(e)}")
