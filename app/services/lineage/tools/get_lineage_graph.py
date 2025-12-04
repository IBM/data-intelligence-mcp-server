# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

from app.core.registry import service_registry
from app.services.constants import LINEAGE_BASE_ENDPOINT, LINEAGE_UI_BASE_ENDPOINT
from app.services.lineage.models.get_lineage_graph import (
    GetLineageGraphRequest,
    GetLineageGraphResponse,
)
from app.services.lineage.tools.search_lineage_assets import _transform_lineage_assets
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url, are_lineage_ids
from app.shared.utils.tool_helper_service import tool_helper_service


class StreamDirection(Enum):
    """Enum for lineage asset directions."""

    UPSTREAM = "onlyUpstream"
    DOWNSTREAM = "onlyDownstream"
    BOTH = "upstreamDownstream"


class ExpansionType(Enum):
    """Enum for lineage expansion types."""

    TARGETS = "only_targets"
    SOURCES = "only_sources"
    BOTH = "sources_and_targets"


def _calculate_starting_asset_direction(hop_up, hop_down, ultimate) -> StreamDirection:
    """
    Calculate asset direction based on hops and ultimate data. Used for lineage url generation

    Args:
        hop_up: Number of elements to find upstream. Default is "3".
        hop_down: Number of elements to find downstream. Default is "3".
        ultimate: Expansion type specifier. Can be "source", "target", or a value
                 indicating both sources and targets. Default is None.

    Returns:
        String containing information about lineage asset direction.
    """
    hop_up_int = int(hop_up) if hop_up is not None else 0
    hop_down_int = int(hop_down) if hop_down is not None else 0
    if (hop_up_int > 0 and hop_down_int == 0) or ultimate == "source":
        return StreamDirection.UPSTREAM
    elif (hop_up_int == 0 and hop_down_int > 0) or ultimate == "target":
        return StreamDirection.DOWNSTREAM
    else:
        return StreamDirection.BOTH


def _calculate_number_of_hops(hop_up, hop_down) -> str:
    """
    calculate the number of steps to be present in url

    Args:
        hop_up: Number of elements to find upstream. Default is "3".
        hop_down: Number of elements to find downstream. Default is "3".

    Returns:
        String: number of hops to be added to url.
    """
    hop_up_int = int(hop_up) if hop_up is not None else 0
    hop_down_int = int(hop_down) if hop_down is not None else 0
    return str(max(hop_up_int, hop_down_int))


def _construct_get_lineage_graph_response(
    lineage_ids: List[str],
    lineage_graph_response: Dict[str, Any],
    hop_up: str,
    hop_down: str,
    ultimate: Optional[str],
):
    """
    Create an url and GetLineageGraphResponse object to be returned in the lineage process

    Args:
        lineage_ids: The lineage IDs of starting assets.
        lineage_graph_response: a response from lineage API call
        hop_up: Number of elements to find upstream. Default is "3".
        hop_down: Number of elements to find downstream. Default is "3".
        ultimate: Expansion type specifier. Can be "source", "target", or a value
                 indicating both sources and targets. Default is None.

    Returns:
        Object containing all lineage data to be returned to user.
    """
    lineage_assets = lineage_graph_response.get("assets_in_view", [])
    lineage_assets_model = _transform_lineage_assets(lineage_assets=lineage_assets)
    
    id_to_name = {asset["id"]: asset["name"] for asset in lineage_assets}
    
    edges = lineage_graph_response.get("edges_in_view", [])
    connections = [
        f"edge from: {id_to_name.get(edge.get('source'), 'None')}, "
        f"to: {id_to_name.get(edge.get('target'), 'None')}, "
        f"relation: {edge.get('type', 'direct')}"
        for edge in edges
    ]
    query_params = {
        "assetsIds": lineage_ids[0] if len(lineage_ids) == 1 else ",".join(lineage_ids),
        "startingAssetDirection": _calculate_starting_asset_direction(
            hop_up=hop_up, hop_down=hop_down, ultimate=ultimate
        ).value,
        "featureFiltersScopeSettingsCloud": "false",
    }

    if not ultimate:
        number_of_hops = _calculate_number_of_hops(hop_up=hop_up, hop_down=hop_down)
        query_params.update(
            {
                "numberOfHops": number_of_hops,
            }
        )
    else:
        query_params.update({"scopeRange": "ultimateRange"})

    url = append_context_to_url(
        f"{tool_helper_service.ui_base_url}{LINEAGE_UI_BASE_ENDPOINT}?{urlencode(query_params)}"
    )
    return GetLineageGraphResponse(
        lineage_assets=lineage_assets_model, edges_in_view=connections, url=url
    )


def _get_expansion_settings(
    lineage_ids: List[str],
    hop_up: Optional[str] = "3",
    hop_down: Optional[str] = "3",
    ultimate: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate expansion settings for lineage graph queries.

    Args:
        lineage_ids: The list of lineage IDs of starting assets.
        hop_up: Number of elements to find upstream. Default is "3".
        hop_down: Number of elements to find downstream. Default is "3".
        ultimate: Expansion type specifier. Can be "source", "target", or a value
                 indicating both sources and targets. Default is None.

    Returns:
        Dictionary containing the expansion settings configuration.
    """
    # Always include starting assets IDs
    exp_settings = {"starting_asset_ids": lineage_ids}

    # Determine expansion configuration based on ultimate parameter
    if not ultimate:
        # Standard hop-based expansion
        exp_settings.update(
            {
                "incoming_steps": hop_up,
                "outgoing_steps": hop_down,
            }
        )
    else:
        if ultimate == "target":
            exp_settings["expansion_type"] = ExpansionType.TARGETS.value
        elif ultimate == "source":
            exp_settings["expansion_type"] = ExpansionType.SOURCES.value
        else:
            exp_settings["expansion_type"] = ExpansionType.BOTH.value

    return exp_settings


async def _call_get_lineage_graph(
    lineage_ids: List[str], hop_up: str, hop_down: str, ultimate: Optional[str]
) -> dict[str, Any]:
    """
    This function returns nodes in lineage graph of lineage asset.

    Args:
        lineage_ids (list[str]): The list of lineage identifiers. Example: ["75a06535eb329a6b69d9f2b448e24e5561a5ca0a96417307e73698b2d4fb0c87", "75a06535eb329a6b69d9f2b448e24e5561a5ca0a96417307e73698b2d4fb0c88"]
        hop_up (Optional[str]): Number of upstream levels to include in the graph:
            - "1" shows immediate upstream connections only. Use if user uses word immidiate or ultimate.
            - "50" shows path between two assets or mentions word 'between'
            - "50" shows complete path to source
            - "50" if more than one asset is on the lineage_ids list
            - "0" if user mentions only word downstream but not upstream
            - Default is "3" for balanced view
        hop_down (Optional[str]): Number of downstream levels to include in the graph:
            - "1" shows immediate downstream connections only. Use if user uses word immidiate or ultimate.
            - "50" shows complete path to target
            - "50" shows path between two assets or mentions word 'between'
            - "50" if more than one asset is on the lineage_ids list
            - "0" if user mentions only word upstream but not downstream
            - Default is "3" for balanced view
        ultimate (Optional[str]): This optional field should get value:
            - If user mentions target the value should be target
            - If user mentions source the value should be source
            - If both are mentioned the value should be both
            - if user mentioned word between the value should ''

    Returns:
        dict[str, Any]: Response from the lineage service.
    
    Raises:
        ExternalAPIError: If the call finishes unsuccessfully
    """

    payload = {
        "initial_asset_ids": lineage_ids,
        "allow_lineage_cache": "false",
        "visible_asset_ids": lineage_ids,
        "expansion": _get_expansion_settings(
            lineage_ids=lineage_ids, hop_up=hop_up, hop_down=hop_down, ultimate=ultimate
        ),
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url)
        + LINEAGE_BASE_ENDPOINT
        + "/query_lineage",
        json=payload,
    )
    return response


@service_registry.tool(
    name="lineage_get_lineage_graph",
    description="""Retrieves the upstream and downstream data lineage graph for specific assets.
    
    This tool generates a data lineage graph showing data flow relationships both upstream
    (data sources) and downstream (data consumers) from the specified assets. The graph depth
    in each direction is controlled by the hop parameters.

    If user asks for ultimate target or source or both and the returned asset's id is the same as in query - it is the answer.
    Always return full answer.""",
)
@auto_context
async def get_lineage_graph(request: GetLineageGraphRequest) -> GetLineageGraphResponse:
    if len(request.lineage_ids) < 1:
        raise ServiceError("No assets were passed to the tool.")

    are_lineage_ids(request.lineage_ids)

    ultimate_verified: Optional[str] = None
    if request.ultimate != "between":
        ultimate_verified = request.ultimate

    LOGGER.info(
        f"get_lineage_graph called with lineage_ids={request.lineage_ids}, hop_up={request.hop_up}, hop_down={request.hop_down}, ultimate={ultimate_verified}"
    )

    if isinstance(request.lineage_ids, str):
        lineage_ids = "".join(
            char for char in request.lineage_ids if char.isalnum() or char == ","
        )
        try:
            lineage_ids = json.loads(lineage_ids)
        except Exception:
            lineage_ids = [s.strip() for s in lineage_ids.split(",")]
    else:
        lineage_ids = request.lineage_ids

    lineage_graph_response = await _call_get_lineage_graph(
        lineage_ids, request.hop_up, request.hop_down, ultimate_verified
    )
    if not (lineage_graph_response.get("assets_in_view")):
        raise ServiceError(
            "call_get_lineage_graph finished successfully but no assets_in_view or/and edges_in_view were found."
        )
    return _construct_get_lineage_graph_response(
        lineage_ids,
        lineage_graph_response,
        request.hop_up,
        request.hop_down,
        ultimate_verified,
    )


@service_registry.tool(
    name="lineage_get_lineage_graph",
    description="""Retrieves the upstream and downstream data lineage graph for specific assets.
    
    This tool generates a data lineage graph showing data flow relationships both upstream
    (data sources) and downstream (data consumers) from the specified assets. The graph depth
    in each direction is controlled by the hop parameters.

    If user asks for ultimate target or source or both and the returned asset's id is the same as in query - it is the answer.
    Always return full answer.""",
)
@auto_context
async def wxo_get_lineage_graph(
    lineage_ids: Union[str, List[str]],
    hop_up: str = "3",
    hop_down: str = "3",
    ultimate: Optional[str] = None,
) -> GetLineageGraphResponse:
    """Watsonx Orchestrator compatible version of get_lineage_graph."""

    request = GetLineageGraphRequest(
        lineage_ids=lineage_ids, hop_up=hop_up, hop_down=hop_down, ultimate=ultimate
    )

    # Call the original get_lineage_graph function
    return await get_lineage_graph(request)
