# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional, Dict, Any

from app.core.registry import service_registry
from app.services.data_product.models.search_data_product_subscriptions import (
    SearchDataProductSubscriptionsRequest,
    SearchDataProductSubscriptionsResponse,
    Subscription,
)
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context
from app.shared.exceptions.base import ServiceError


def _build_query_params(request: SearchDataProductSubscriptionsRequest) -> Dict[str, Any]:
    """Build query parameters for the asset lists API request."""
    params: Dict[str, Any] = {}
    base_filter = 'type=="order"'
    
    # Handle query parameter
    if request.query and request.query.strip():
        params["query"] = f'{base_filter}&&({request.query})'
    else:
        params["query"] = base_filter
    
    # Handle limit parameter
    if request.limit is not None:
        if request.limit == 0:
            params["limit"] = 0
        elif request.limit > 0:
            params["limit"] = min(max(1, request.limit), 200)
    
    # Handle start parameter for pagination
    if request.start and request.start.strip():
        params["start"] = request.start
    
    # Handle sort parameter
    if request.sort and request.sort.strip():
        params["sort"] = request.sort
    
    return params


def _extract_href_value(value: Any) -> Optional[str]:
    """Extract href from a value that might be a dict or string."""
    if isinstance(value, dict):
        return value.get("href")
    return value


def _build_response(response_data: Dict[str, Any] | bytes) -> SearchDataProductSubscriptionsResponse:
    """Build the response object from API response data."""
    if isinstance(response_data, bytes):
        raise ServiceError("Unexpected bytes response from API")
    
    items = response_data.get("asset_lists", [])
    total_count = response_data.get("total_count", 0)
    
    LOGGER.info(f"Retrieved {len(items)} subscriptions (total: {total_count})")
    
    # Convert items to Subscription objects
    subscriptions = [
        Subscription(
            id=item.get("id", ""),
            name=item.get("name"),
            description=item.get("description"),
            state=item.get("state"),
            created_at=item.get("created_at"),
            last_updated_at=item.get("last_updated_at"),
            asset=item.get("asset"),
            access_control=item.get("access_control")
        )
        for item in items
    ]
    
    return SearchDataProductSubscriptionsResponse(
        subscriptions=subscriptions,
        total_count=total_count,
        limit=response_data.get("limit"),
        next=_extract_href_value(response_data.get("next")),
        first=_extract_href_value(response_data.get("first"))
    )


@service_registry.tool(
    name="data_product_search_data_product_subscriptions",
    description="""
    Search and filter data product subscriptions (asset lists) from IBM Cloud Data Product Hub.
    
    This tool searches asset lists of type "order" which represent data product subscriptions.
    Returns subscription METADATA including ID, state, name, and owner information.
    
    **IMPORTANT**: This tool returns subscription metadata only. To see the actual items/content
    being delivered in a subscription, you would need to make additional API calls with the subscription ID.
    
    Each subscription contains:
    - Subscription ID (required for getting subscription content)
    - Subscription state (e.g., succeeded, delivered, failed)
    - Name and description
    - Access control information
    
    The filter type=="order" is automatically appended to all queries to ensure only
    data product subscriptions are returned (not other asset list types).
    
    **CRITICAL: Finding Subscriptions for a Specific Data Product**
    
    When data_product_get_data_product_details returns data product information, it includes multiple IDs:
    - `id` (top-level): The DATA PRODUCT VERSION ID
      Example: "6d80d7d4-ca55-4fb0-8b70-bb799a2881dd@b34d014d-82d1-4374-9de2-4478e350a5f6"
      The part BEFORE the @ symbol is the asset ID: "6d80d7d4-ca55-4fb0-8b70-bb799a2881dd"
    - `asset.id`: The asset ID (same as the part before @ in the top-level id)
      Example: "6d80d7d4-ca55-4fb0-8b70-bb799a2881dd"
    - `asset.container.id`: The CATALOG ID - DO NOT USE THIS for subscriptions!
      Example: "b34d014d-82d1-4374-9de2-4478e350a5f6"
    
    To find subscriptions for a data product:
    1. Extract the asset ID from data_product_get_data_product_details response:
       - Use `asset.id` field directly, OR
       - Take the part BEFORE the @ symbol from the top-level `id` field
    2. Query subscriptions with: asset.id=="<asset_id_here>"
    
    **CORRECT Example:**
    - Data product details shows: `"asset": {"id": "6d80d7d4-ca55-4fb0-8b70-bb799a2881dd"}`
    - Query to use: `asset.id=="6d80d7d4-ca55-4fb0-8b70-bb799a2881dd"`
    
    **WRONG Example (DO NOT DO THIS):**
    - Using catalog ID: `asset.id=="b34d014d-82d1-4374-9de2-4478e350a5f6"` ❌
    - This will return NO results because catalog ID is not the asset ID!
    
    Features:
    - Query and filter asset lists using CEL (Common Expression Language)
    - Pagination support
    - Sort by various fields (created_at, last_updated_at)
    
    CEL Query Examples:
    - name=="My data product name" - Find subscriptions by name
    - asset.id=="6d80d7d4-ca55-4fb0-8b70-bb799a2881dd" - Find subscriptions for a specific data product
    - asset.id=="6d80d7d4-ca55-4fb0-8b70-bb799a2881dd"&&created_at>="2025-10-08T23:00:00Z" - Filter by product and date
    - state=="succeeded" - Find successfully delivered subscriptions
    - created_at>="2024-01-01"&&state=="delivered" - Combine multiple conditions
    - access_control.owner=="IBMid-123456" - Filter by owner
    
    Returns:
    - List of subscriptions with metadata (ID, state, name, owner)
    - Pagination information (next, first links)
    - Total count of results
    """,
    tags={"read", "data_product", "subscriptions"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def search_data_product_subscriptions(
    request: SearchDataProductSubscriptionsRequest,
) -> SearchDataProductSubscriptionsResponse:
    """
    Search and filter data product subscriptions (asset lists).
    
    Fetches asset lists of type "order" which represent data product subscriptions,
    with optional filtering, sorting, and pagination.
    """
    LOGGER.info(
        f"In data_product_search_data_product_subscriptions tool, "
        f"query={request.query}, limit={request.limit}, start={request.start}, sort={request.sort}"
    )
    
    try:
        asset_lists_url = f"{tool_helper_service.base_url}/v2/asset_lists"
        params = _build_query_params(request)
        
        LOGGER.info(f"Fetching asset lists from: {asset_lists_url}")
        LOGGER.debug(f"Query parameters: {params}")
        
        response_data = await tool_helper_service.execute_get_request(
            url=asset_lists_url,
            params=params,
            tool_name="data_product_search_data_product_subscriptions"
        )
        
        return _build_response(response_data)
        
    except ServiceError:
        raise
    except Exception as e:
        error_message = f"Exception when searching data product subscriptions: {e!s}"
        LOGGER.error(error_message)
        raise ServiceError(
            f"Failed to search data product subscriptions. {error_message}"
        )


@service_registry.tool(
    name="data_product_search_data_product_subscriptions",
    description="""
    Search and filter data product subscriptions (asset lists) from IBM Cloud Data Product Hub.
    
    This tool searches asset lists of type "order" which represent data product subscriptions.
    Returns subscription METADATA including ID, state, name, and owner information.
    
    **IMPORTANT**: To find subscriptions for a specific data product, use the asset.id from 
    data_product_get_data_product_details (NOT the catalog ID!).
    
    Args:
        query: Optional CEL query to filter subscriptions. Examples:
               - asset.id=="6d80d7d4-ca55-4fb0-8b70-bb799a2881dd" (find subscriptions for a data product)
               - name=="My data product" (find by name)
               - state=="succeeded" (find successful subscriptions)
        limit: Maximum number of results to return (1-200). Use None for no limit, 0 for count only.
        start: Pagination start token from previous response.
        sort: Comma-separated sort fields (e.g., 'created_at,-last_updated_at'). Prefix with '-' for descending.
    
    Returns:
        SearchDataProductSubscriptionsResponse: Object containing subscriptions list, total_count, and pagination info
    """,
    tags={"read", "data_product", "subscriptions"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def wxo_search_data_product_subscriptions(
    query: Optional[str] = None,
    limit: Optional[int] = None,
    start: Optional[str] = None,
    sort: Optional[str] = None
) -> SearchDataProductSubscriptionsResponse:
    """Watsonx Orchestrator compatible version that expands SearchDataProductSubscriptionsRequest object into individual parameters."""
    
    request = SearchDataProductSubscriptionsRequest(
        query=query,
        limit=limit,
        start=start,
        sort=sort
    )
    
    return await search_data_product_subscriptions(request)

# Made with Bob
