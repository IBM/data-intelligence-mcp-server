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

from app.core.registry import service_registry
from app.services.data_product.models.get_data_product_subscription_details import (
    GetDataProductSubscriptionDetailsRequest,
    GetDataProductSubscriptionDetailsResponse,
    SubscriptionItem,
)
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context
from app.shared.exceptions.base import ServiceError


@service_registry.tool(
    name="data_product_get_data_product_subscription_details",
    description="""
    Retrieve the actual content (items) being delivered in a specific data product subscription.
    
    **IMPORTANT**: This tool requires a subscription ID. To find subscription IDs, first use
    the data_product_search_data_product_subscriptions tool.
    
    This tool retrieves all items from a specific subscription (asset list) by its ID.
    Each item represents a subscribed data product with detailed delivery information:
    - Asset IDs and catalog information
    - Delivery method details (e.g., Arrow Flight)
    - Data product delivery state (e.g., succeeded, failed, in_progress)
    - Output assets (flight descriptors for accessing data)
    - Copy text for accessing the data
    
    Use this tool when you have a subscription ID and want to see:
    - What data products are being delivered
    - The delivery status of each item
    - How to access the delivered data (flight descriptors)
    
    Features:
    - Retrieve all items from a subscription
    - Detailed delivery state for each item
    - Access information (flight descriptors, copy text)
    
    Returns:
    - List of items in the subscription with delivery details
    - Total count of items
    
    **Workflow**: 
    1. Use data_product_search_data_product_subscriptions to find subscriptions
    2. Use this tool with the subscription ID to get the delivered items
    
    **Example Use Case**:
    After finding a subscription with ID "abc-123-def", use this tool to see:
    - Which data assets are being delivered
    - The delivery state of each asset
    - Flight descriptors or URLs to access the data
    """,
    tags={"read", "data_product", "subscriptions"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def get_data_product_subscription_details(
    request: GetDataProductSubscriptionDetailsRequest,
) -> GetDataProductSubscriptionDetailsResponse:
    """
    Retrieve the content (items) of a specific data product subscription.
    
    Fetches all items being delivered in a subscription, including delivery
    states and access information.
    """
    LOGGER.info(
        f"In data_product_get_data_product_subscription_details tool, "
        f"subscription_id={request.subscription_id}"
    )
    
    if not request.subscription_id or not request.subscription_id.strip():
        raise ServiceError(
            "Missing required subscription_id. "
            "Please provide a valid subscription ID obtained from data_product_search_data_product_subscriptions."
        )
    
    try:
        # Build the subscription items URL
        items_url = f"{tool_helper_service.base_url}/v2/asset_lists/{request.subscription_id}/items"
        
        LOGGER.info(f"Fetching subscription items from: {items_url}")
        
        # Execute the request
        response_data = await tool_helper_service.execute_get_request(
            url=items_url,
            tool_name="data_product_get_data_product_subscription_details"
        )
        
        # Extract key information
        items = response_data.get("items", [])
        total_count = response_data.get("total_count", 0)
        
        LOGGER.info(f"Retrieved {len(items)} items from subscription (total: {total_count})")
        
        # Convert items to SubscriptionItem objects
        subscription_items = []
        for item in items:
            subscription_item = SubscriptionItem(
                id=item.get("id"),
                asset=item.get("asset"),
                properties=item.get("properties"),
                state=item.get("state"),
                created_at=item.get("created_at"),
                last_updated_at=item.get("last_updated_at")
            )
            subscription_items.append(subscription_item)
        
        # Return the response
        return GetDataProductSubscriptionDetailsResponse(
            items=subscription_items,
            total_count=total_count,
            subscription_id=request.subscription_id
        )
        
    except ServiceError:
        raise
    except Exception as e:
        error_message = f"Exception when getting subscription details: {e!s}"
        LOGGER.error(error_message)
        raise ServiceError(
            f"Failed to retrieve subscription details. {error_message}"
        )


@service_registry.tool(
    name="data_product_get_data_product_subscription_details",
    description="""
    Retrieve the actual content (items) being delivered in a specific data product subscription.
    
    **IMPORTANT**: This tool requires a subscription ID from data_product_search_data_product_subscriptions.
    
    Returns detailed information about each item in the subscription including:
    - Asset IDs and types
    - Delivery states (succeeded, failed, in_progress)
    - Access information (flight descriptors, URLs)
    - Delivery method details
    
    Args:
        subscription_id: The ID of the subscription (asset list) to retrieve items from.
                        This is a UUID obtained from data_product_search_data_product_subscriptions.
    
    Returns:
        GetDataProductSubscriptionDetailsResponse: Object containing items list, total_count, and subscription_id
    """,
    tags={"read", "data_product", "subscriptions"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def wxo_get_data_product_subscription_details(
    subscription_id: str
) -> GetDataProductSubscriptionDetailsResponse:
    """Watsonx Orchestrator compatible version that expands GetDataProductSubscriptionDetailsRequest object into individual parameters."""
    
    request = GetDataProductSubscriptionDetailsRequest(
        subscription_id=subscription_id
    )
    
    return await get_data_product_subscription_details(request)

# Made with Bob
