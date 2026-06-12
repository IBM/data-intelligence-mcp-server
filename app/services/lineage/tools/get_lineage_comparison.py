# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Any, Dict, List, Optional, Union
from app.core.registry import service_registry
from app.services.constants import LINEAGE_BASE_ENDPOINT
from app.services.lineage.constants import SERVICE_UNAVAILABLE_MESSAGE
from app.services.lineage.utils import handle_500_error
from app.services.lineage.models.get_lineage_comparison import (
    GetLineageComparisonRequest,
    GetLineageComparisonResponse,
    LineageComparisonAsset,
    LineageComparisonEdge,
    LineageRequestBodyPart,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import parse_list_of_ids, verify_dates
from app.shared.utils.tool_helper_service import tool_helper_service

TOOLS_DESCRIPTION = """
    Performs a comparison of assets between two versions. It can be either for singular assets coming from search_lineage_assets
    or for graphs coming from get_lineage_graph. Returns a list of assets with their status and optionally a list of edges with statuses for graphs.
    
    **CRITICAL** - this tool should be used after user used either search_lineage_assets or get_lineage_graph on their own or
    should be called as a last tool when user's request requires usage of combination of tools. The dates for comparison should come from
    list_lineage_versions.

    Example Workflow:
        User: "Compare lineage graph for asset CUSTOMER_TABLE at September 24th 2025 and October 10th 2025"
        1. Call list_lineage_versions(since="2025-09-24Z", until="2025-10-24Z")
        2. Choose first and last versions from the list
        3. Call search_lineage_assets(name_query="customer_table")
        4. Extract lineage ID from results: "75a06535eb329a6b..."
        5. Call get_lineage_graph(lineage_ids="75a06535eb329a6b...", hop_up=50, hop_down=50, dates=["2025-09-24T04:10:12.828Z", "2025-10-23T08:54:02.17Z"])
        6. Extract lineage IDs from the results
        7. Call get_lineage_comparison(
            compared_lineage_assets=["75a06535eb329a6b...","12b06535eb329a6b..."],
            lineage={"initial_asset_ids": ["75a06535eb329a6b..."]},
            base_version="2025-09-24T04:10:12.828Z",
            compared_version="2025-10-23T08:54:02.17Z"
           )
        8. Return results

    Example Workflow2:
        User: "How did lineage asset CUSTOMER_TABLE change between September 24th 2025 and October 10th 2025"
        1. Call list_lineage_versions(since="2025-09-24Z", until="2025-10-24Z")
        2. Choose first and last versions from the list
        3. Call search_lineage_assets(name_query="customer_table", dates=["2025-09-24T04:10:12.828Z", "2025-10-23T08:54:02.17Z"])
        4. Extract lineage ID from results: "75a06535eb329a6b..."
        5. Call get_lineage_comparison(
            compared_lineage_assets=["75a06535eb329a6b..."],
            base_version="2025-09-24T04:10:12.828Z",
            compared_version="2025-10-23T08:54:02.17Z"
           )
        6. Return results

    Args:
        compared_lineage_assets (List[str]): List of asset IDs to be compared.
        lineage (Optional[LineageRequestBodyPart]): Nested object containing initial_asset_ids for graph comparison. Required for graph comparison, None for single asset comparison.
        base_version (str): Base version datetime in ISO-8601 format (earlier version). Example: "2025-11-12T10:00:00Z"
        compared_version (str): Compared version datetime in ISO-8601 format (later version). Example: "2025-11-12T12:00:00Z"

    Returns:
        GetLineageComparisonResponse: An object containing a list of lineage assets that are available between the two dates with their statuses.

    Raises:
        ExternalServiceError: If the API request fails (status code != 200)
        ToolProcessFailedError: If no entities are found for the given IDs
    """

def _transform_assets(asset_changes: List[Dict[str, Any]]) -> List[LineageComparisonAsset]:
    """
    Transforms asset changes from API response to LineageComparisonAsset objects.
    Filters out assets with no changes.
    
    Args:
        asset_changes: List of asset change objects from API response
        
    Returns:
        List of LineageComparisonAsset objects
    """
    LOGGER.info(f"Processing {len(asset_changes)} asset changes from API")
    
    # Filter assets with non-empty changes
    filtered_assets = [
        asset for asset in asset_changes
        if asset.get("changes") and len(asset.get("changes", [])) > 0
    ]
    
    LOGGER.info(f"Filtered to {len(filtered_assets)} assets with non-empty changes")
    
    lineage_assets_model = []
    for asset in filtered_assets:
        asset_data = asset.get("asset", {})
        changes = asset.get("changes", [])
        
        lineage_asset = LineageComparisonAsset(
            id=asset_data.get("id", ""),
            name=asset_data.get("name", ""),
            changes=list(changes),  # Convert set to list
            descendants_added=asset.get("number_of_added_descendants", 0),
            descendants_removed=asset.get("number_of_removed_descendants", 0),
        )
        lineage_assets_model.append(lineage_asset)
    
    return lineage_assets_model


def _transform_edges(edge_changes: List[Dict[str, Any]]) -> List[LineageComparisonEdge]:
    """
    Transforms edge changes from API response to LineageComparisonEdge objects.
    Filters out edges with no changes.
    
    Args:
        edge_changes: List of edge change objects from API response
        
    Returns:
        List of LineageComparisonEdge objects
    """
    LOGGER.info(f"Processing {len(edge_changes)} edge changes from API")
    
    # Filter edges with non-empty changes
    filtered_edges = [
        edge for edge in edge_changes
        if edge.get("changes") and len(edge.get("changes", [])) > 0
    ]
    
    LOGGER.info(f"Filtered to {len(filtered_edges)} edges with non-empty changes")
    
    lineage_edges_model = []
    for edge_change in filtered_edges:
        edge = edge_change.get("edge", {})
        changes = edge_change.get("changes", [])
        
        lineage_edge = LineageComparisonEdge(
            source=edge.get("source", ""),
            target=edge.get("target", ""),
            type=edge.get("type", "direct"),
            changes=list(changes),  # Convert set to list
        )
        lineage_edges_model.append(lineage_edge)
    
    return lineage_edges_model


async def _get_lineage_comparison(
    request: GetLineageComparisonRequest,
) -> GetLineageComparisonResponse:

    # Validate and parse dates
    dates_verified = verify_dates([request.base_version, request.compared_version])
    
    if not dates_verified or len(dates_verified) != 2:
        raise ServiceError(
            f"Invalid dates provided. Expected 2 valid ISO-8601 dates, got: base_version={request.base_version}, compared_version={request.compared_version}"
        )

    # Parse compared lineage IDs
    compared_lineage_ids = parse_list_of_ids(request.compared_lineage_assets)

    # Extract initial asset IDs from nested lineage object if present
    graph_initial_ids = []
    if request.lineage and request.lineage.initial_asset_ids:
        graph_initial_ids = request.lineage.initial_asset_ids

    LOGGER.info(
        f"get_lineage_comparison called with initial_assets={graph_initial_ids}, "
        f"compared_assets={compared_lineage_ids}, base_version={dates_verified[0]}, compared_version={dates_verified[1]}"
    )

    # Build payload according to API specification
    payload = {
        "compared_lineage_assets": compared_lineage_ids,
        "base_version": dates_verified[0],
        "compared_version": dates_verified[1]
    }

    # Add lineage graph context if initial assets are provided
    if graph_initial_ids:
        payload["lineage"] = {
            "initial_asset_ids": graph_initial_ids
        }

    try:
        response = await tool_helper_service.execute_post_request(
            url=str(tool_helper_service.base_url) + LINEAGE_BASE_ENDPOINT + "/compare_lineage",
            json=payload,
        )
    except ExternalAPIError as e:
        return handle_500_error(
            e,
            lambda: GetLineageComparisonResponse(
                lineage_assets=[],
                lineage_edges=[],
                success=False,
                error=SERVICE_UNAVAILABLE_MESSAGE
            )
        )

    LOGGER.info(
        f"payload={payload}, "
        f"response={response}"
    )

    # Transform assets and edges from API response
    asset_changes = response.get("asset_changes", [])
    edge_changes = response.get("edge_changes", [])

    lineage_assets_model = _transform_assets(asset_changes)
    lineage_edges_model = _transform_edges(edge_changes)
    
    return GetLineageComparisonResponse(
        lineage_assets=lineage_assets_model,
        lineage_edges=lineage_edges_model
    )

@service_registry.tool(
    name="get_lineage_comparison",
    annotations={
        "readOnlyHint": True,
        "title": "Get Compare Lineage Assets Between Two Versions"
    },
    description=TOOLS_DESCRIPTION,
)
@auto_context
async def get_lineage_comparison(
    compared_lineage_assets: str,
    base_version: str,
    compared_version: str,
    initial_lineage_assets: Optional[str] = None,
) -> GetLineageComparisonResponse:
    """
    Wrapper version that expands GetLineageComparisonRequest object into individual parameters.
    """
    
    # Parse compared assets
    compared_assets_list = [asset.strip() for asset in compared_lineage_assets.split(',') if asset.strip()]
    
    # Build lineage object if initial assets provided
    lineage_obj = None
    if initial_lineage_assets:
        initial_assets_list = [asset.strip() for asset in initial_lineage_assets.split(',') if asset.strip()]
        if initial_assets_list:
            lineage_obj = LineageRequestBodyPart(initial_asset_ids=initial_assets_list)
    
    request = GetLineageComparisonRequest(
        compared_lineage_assets=compared_assets_list,
        lineage=lineage_obj,
        base_version=base_version,
        compared_version=compared_version,
    )

    # Call the original get_lineage_comparison function
    return await _get_lineage_comparison(request)

# Made with Bob
