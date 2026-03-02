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
from app.shared.utils.helpers import append_context_to_url, are_lineage_ids, verify_dates
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
    lineage_ids: List[str], hop_up: str, hop_down: str, ultimate: Optional[str], dates: Optional[List[str]]
) -> dict[str, Any]:
    """Retrieves upstream and downstream lineage graph using 64-character hexadecimal lineage IDs.
    Call this tool to get graph information and/or related assets.
    
    Args:
        lineage_ids (Union[str, List[str]]): One or more 64-character hexadecimal lineage IDs
            (MUST be obtained from search_lineage_assets results or convert_to_lineage_id results)
        hop_up (Optional[str]): Number of upstream levels to traverse ("0", "1", "3", or "50").
            Use "50" when user mentions "between", "ultimate source", or provides multiple lineage_ids. If only hop_down is specified use "0".
        hop_down (Optional[str]): Number of downstream levels to traverse ("0", "1", "3", or "50").
            Use "50" when user mentions "between", "ultimate target", or provides multiple lineage_ids. If only hop_up is specified use "0".
        ultimate (Optional[str]): Specifies ultimate endpoint search mode
            ("source", "target", "both", "", or None)
        dates (Optional[List[str]]): List of exactly 2 ISO 8601 dates for version comparison.
            When provided, retrieves lineage graph as it existed at those two points in time.
            Used for comparing how lineage changed between versions. If None, returns current lineage.
    
    Returns:
        UpstreamDownstreamLineage: Lineage graph containing:
            - lineage_assets: Complete list of assets in the lineage graph with metadata
            - edges_in_view: Connections between assets showing data flow in format - edge from: AssetA, to: AssetB, relation: RelationType
            - url: Direct link to visualize the lineage graph in the UI
    
    Raises:
        ExternalServiceError: When the API request fails (non-200 status code)
        ToolProcessFailedError: When the response is missing expected graph data
        ValidationError: When lineage_ids are not valid 64-character hexadecimal strings
    """

    payload = {
        "initial_asset_ids": lineage_ids,
        "allow_lineage_cache": "false",
        "visible_asset_ids": lineage_ids,
        "expansion": _get_expansion_settings(
            lineage_ids=lineage_ids, hop_up=hop_up, hop_down=hop_down, ultimate=ultimate
        ),
    }
    
    # Only add lineage_version_datetimes if dates are provided
    # Note: Parameter is named 'dates' in the function signature for clarity,
    # but the API expects 'lineage_version_datetimes'
    if dates:
        payload["lineage_version_datetimes"] = dates

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url)
        + LINEAGE_BASE_ENDPOINT
        + "/query_lineage",
        json=payload,
    )
    return response


@service_registry.tool(
    name="lineage_get_lineage_graph",
    description="""Retrieves upstream and downstream lineage graph using 64-character hexadecimal lineage IDs.
    Call this tool to get graph information and/or related assets.
    
    **CRITICAL REQUIREMENT**: This tool ONLY accepts 64-character hexadecimal lineage IDs.
    
    **DO NOT CALL THIS TOOL IF**:
    - You have asset names (e.g., "customer_table") → Call search_lineage_assets first
    - You have short IDs or UUIDs → Call convert_to_lineage_id first
    - The identifier is not exactly 64 hexadecimal characters → Call search_lineage_assets first
    
    **ONLY CALL THIS TOOL IF**:
    - You have 64-character hexadecimal strings like for example "aaaaaaaaaabbbbbbbbbbccccccccccddddddddddeeeeeeeeee11111111112222"
    - You obtained the lineage ID from search_lineage_assets results
    - You obtained the loneage ID from convert_to_lineage_id results
    
    Validation: Before calling this tool, verify each lineage_id:
    - Length is exactly 64 characters
    - Contains only hexadecimal characters (0-9, a-f)
    - If validation fails, call search_lineage_assets instead
    
    Args:
        lineage_ids (Union[str, List[str]]): One or more 64-character hexadecimal lineage IDs
            (MUST be obtained from search_lineage_assets results or convert_to_lineage_id results)
        hop_up (Optional[str]): Number of upstream levels to traverse ("0", "1", "3", or "50").
            Use "50" when user mentions "between", "ultimate source", or provides multiple lineage_ids. If only hop_down is specified use "0".
        hop_down (Optional[str]): Number of downstream levels to traverse ("0", "1", "3", or "50").
            Use "50" when user mentions "between", "ultimate target", or provides multiple lineage_ids. If only hop_up is specified use "0".
        ultimate (Optional[str]): Specifies ultimate endpoint search mode
            ("source", "target", "both", "", or None)
        dates (Optional[str]): Two ISO 8601 dates used when user wants to compare two versions of graph.
            Either a valid ISO 8601 dates or None.
    
    Returns:
        UpstreamDownstreamLineage: Lineage graph containing:
            - lineage_assets: Complete list of assets in the lineage graph with metadata
            - edges_in_view: Connections between assets showing data flow in format - edge from: AssetA, to: AssetB, relation: RelationType
            - url: Direct link to visualize the lineage graph in the UI
    
    Raises:
        ExternalServiceError: When the API request fails (non-200 status code)
        ToolProcessFailedError: When the response is missing expected graph data
        ValidationError: When lineage_ids are not valid 64-character hexadecimal strings
    
    Notes:
        - Always provide both hop_up and hop_down parameters. If user provides one of them, the other should be "0"
        - If neither is specified, both hops default to "3"
        - When asked about related assets the value of both hops should be "50"
        - When ultimate source/target matches the query asset ID, that asset is the answer
        - Always include the URL link in your response for user visualization
        - Return complete results without truncation
        - User can ask for ultimate target and/or source. The workflow is the same as asking for lineage graph.
        - Ultimate should be set to "both" only if user asks for ultimate source and target
        - If user is attempting to compare two versions, lineage_get_lineage_versions needs to be called first
        - If the lineage_get_lineage_versions is called first - pick first and last date from the list
    
    Example Workflow:
        User: "Show me the lineage for customer_table"
        1. Call search_lineage_assets(name_query="customer_table")
        2. Extract lineage ID from results: "75a06535eb329a6b..."
        3. Call get_lineage_graph(lineage_ids="75a06535eb329a6b...")
        User: "Show me the lineage for account_table"
        1. Call search_lineage_assets(name_query="account_table")
        2. Extract lineage ID from results: "75a06535eb329a6b...","85a06535eb329a6b...","95a06535eb329a6b..."
        3. Call get_lineage_graph(lineage_ids=["75a06535eb329a6b...", "85a06535eb329a6b...","95a06535eb329a6b...")
    Example Workflow 2:
        User: "What is the ultimate source and target asset from lineage of lineage asset LOAD_ACCOUNT_TYPES?"
        1. Call search_lineage_assets(name_query="LOAD_ACCOUNT_TYPES")
        2. Extract lineage ID from results: "75a06535eb329a6b..."
        3. Call get_lineage_graph(lineage_ids="75a06535eb329a6b...", ultimate="both")
    Example Workflow 3:
        User: "Find the lineage asset 'PRODUCTS_VIEW_BODY' and fetch the lineage path to 'PRODUCTS_VIEW' asset"
        1. Call search_lineage_assets(name_query="PRODUCTS_VIEW_BODY")
        2. Extract lineage ID from results: "75a06535eb329a6b..."
        3. Call search_lineage_assets(name_query="PRODUCTS_VIEW")
        4. Extract lineage ID from results: "85a06535eb329a6b..."
        5. Call get_lineage_graph(lineage_ids=["75a06535eb329a6b...", "85a06535eb329a6b..."], hop_up=50, hop_down=50, ultimate=None)
        6. Search for PRODUCTS_VIEW in response and return the path from PRODUCTS_VIEW_BODY to the user
    Example Workflow 4:
        User: "Get lineage for LOAD_ACCOUNT_TYPES. What changed between 2024 and 2025?"
        1. Call lineage_get_lineage_versions(since="2024Z",until="2025Z")
        2. Extract first and last value from the list
        3. Call search_lineage_assets(name_query="LOAD_ACCOUNT_TYPES")
        4. Extract lineage ID from results: "75a06535eb329a6b..."
        5. Call get_lineage_graph(lineage_ids=["75a06535eb329a6b..."], hop_up=50, hop_down=50, ultimate=None, dates=["2025-10-23T08:54:02.17Z","2025-09-12T06:35:27.115Z"])
    """,
)
@auto_context
async def get_lineage_graph(request: GetLineageGraphRequest) -> GetLineageGraphResponse:
    if len(request.lineage_ids) < 1:
        raise ServiceError("No assets were passed to the tool.")

    are_lineage_ids(request.lineage_ids)

    ultimate_verified: Optional[str] = None
    if request.ultimate != "between":
        ultimate_verified = request.ultimate

    dates_verified: Optional[List[str]] = None
    if request.dates:
        dates_verified = verify_dates(dates=request.dates)
        if dates_verified and len(dates_verified) != 2:
            raise ServiceError(
                f"dates parameter must contain exactly 2 ISO 8601 dates, got {len(dates_verified)} dates"
            )

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
        lineage_ids, request.hop_up, request.hop_down, ultimate_verified, dates_verified
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
    dates: Optional[str] = None
) -> GetLineageGraphResponse:
    """Watsonx Orchestrator compatible version of get_lineage_graph."""

    request = GetLineageGraphRequest(
        lineage_ids=lineage_ids, hop_up=hop_up, hop_down=hop_down, ultimate=ultimate, dates=dates
    )

    # Call the original get_lineage_graph function
    return await get_lineage_graph(request)
