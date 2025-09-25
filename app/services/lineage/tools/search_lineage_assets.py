# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
# Removed unused import: re
from app.services.lineage.models.lineage_asset import LineageAsset
from app.services.lineage.models.search_lineage_assets import (
    SearchLineageAssetsRequest,
    SearchLineageAssetsResponse,
)

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import LINEAGE_BASE_ENDPOINT
from app.shared.exceptions.base import ExternalAPIError
from app.shared.utils.http_client import get_http_client

# Removed unused import: json
from typing import Any
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="lineage_search_lineage_assets",
    description="""This tool searches assets in Lineage system based on users query
                   and two optional filters: technology_name and asset_type.
                   It returns the lineage history of asset.""",
)
@auto_context
async def search_lineage_assets(
    request: SearchLineageAssetsRequest,
) -> SearchLineageAssetsResponse:

    LOGGER.info(
        f"Received request for search_lineage_assets with name_query {request.name_query}"
    )

    technology_names = [request.technology_name] if request.technology_name else None
    asset_types = [request.asset_type] if request.asset_type else None

    if technology_names is not None:
        LOGGER.info(f"technology_names: {technology_names}")

    if asset_types is not None:
        LOGGER.info(f"asset_types: {asset_types}")

    try:
        response = await call_search_lineage_assets(
            request.name_query, technology_names, asset_types
        )

        response_assets = response.get("lineage_assets")
        lineage_assets = [
            LineageAsset.model_validate(asset) for asset in response_assets
        ]
        response_is_complete = "next" not in response
        return SearchLineageAssetsResponse(
            lineage_assets=lineage_assets, response_is_complete=response_is_complete
        )

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ExternalAPIError(f"Failed to asset search lineage history: {str(e)}")


async def call_search_lineage_assets(
    name_query: str, technology_names: list[str], asset_types: list[str]
) -> dict[str, Any]:
    """
    Call the lineage service to search lineage assets.

    Args:
        name_query (str): The name of the asset to search for.
        technology_names (list[str]): List of technology names to filter by.
        asset_types (list[str]): List of asset types to filter by.

    Returns:
        dict[str, Any]: Response from the lineage service.
    """
    client = get_http_client()

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    filters = []
    if technology_names:
        filters.append(_create_asset_filter("technology_name", technology_names))
    if asset_types:
        filters.append(_create_asset_filter("asset_type", asset_types))
    payload = {
        "query": name_query,
        "filters": filters,
    }

    return await client.post(
        settings.di_service_url + LINEAGE_BASE_ENDPOINT + "/search_lineage_assets",
        data=payload,
        headers=headers,
    )


def _create_asset_filter(name: str, values: list[str]):
    return {"type": name, "values": values}
