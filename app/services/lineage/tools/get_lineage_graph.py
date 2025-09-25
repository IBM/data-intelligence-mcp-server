# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from ..models.lineage_asset import LineageAsset
from .utils import call_get_lineage_graph

from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import LINEAGE_UI_BASE_ENDPOINT
from app.services.lineage.models.get_lineage_graph import (
    GetLineageGraphRequest,
    GetLineageGraphResponse,
)
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="lineage_get_lineage_graph",
    description="""This function returns upstream and downstream lineage graph of lineage asset accessible under the url""",
)
@auto_context
async def get_lineage_graph(request: GetLineageGraphRequest) -> GetLineageGraphResponse:

    LOGGER.info(f"Received request for get_lineage_graph with lineage_id {request.lineage_id}")

    get_lineage_graph_response = await call_get_lineage_graph(request.lineage_id)

    assets_in_view = get_lineage_graph_response.get("assets_in_view")
    lineage_assets = list(
        map(lambda asset: LineageAsset.model_validate(asset), assets_in_view)
    )
    url = f"{settings.ui_url}{LINEAGE_UI_BASE_ENDPOINT}/?assetsIds={request.lineage_id}&startingAssetDirection=upstreamDownstream&numberOfHops=3&assetTypes=deduced&featureFiltersScopeSettingsCloud=false&context=df"
    return GetLineageGraphResponse(lineage_assets=lineage_assets, url=url)
