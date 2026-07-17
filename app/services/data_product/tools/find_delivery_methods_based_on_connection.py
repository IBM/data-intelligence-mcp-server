# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Annotated
from pydantic import Field

from app.core.registry import service_registry
from app.services.data_product.models.find_delivery_methods_based_on_connection import (
    FindDeliveryMethodsBasedOnConnectionRequest,
    FindDeliveryMethodsBasedOnConnectionResponse,
    DeliveryMethod
)
from app.shared.exceptions.base import ServiceError
from app.services.data_product.utils.common_utils import add_catalog_id_suffix, get_dph_catalog_id_for_user, validate_inputs
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context


async def _find_delivery_methods_based_on_connection(
    request: FindDeliveryMethodsBasedOnConnectionRequest, 
) -> FindDeliveryMethodsBasedOnConnectionResponse:
    LOGGER.info(
        f"In the find_data_product_delivery_methods_based_on_connection tool, finding delivery methods for data asset {request.data_asset_id} in {request.container_type} (ID: {request.container_id})."
    )
    # validate_inputs(request, "data_asset_name")
    dph_catalog_id = await get_dph_catalog_id_for_user()

    if not request.container_id or not request.container_type:
        error_message = "Container ID and Container Type are required."
        LOGGER.error(f"Failed to run find_data_product_delivery_methods_based_on_connection tool. {error_message}")
        raise ServiceError(f"Failed to run find_data_product_delivery_methods_based_on_connection tool. {error_message}")
    
    if not request.data_asset_id:
        error_message = "Data asset ID is required. Find the data asset ID matching the data asset for which we are finding delivery methods. Data asset ID can be found in the response of `search_asset` tool."
        LOGGER.error(f"Failed to run find_data_product_delivery_methods_based_on_connection tool. {error_message}")
        raise ServiceError(f"Failed to run find_data_product_delivery_methods_based_on_connection tool. {error_message}")
   
    # step 1: get the connection ID from the data asset details
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/assets/{request.data_asset_id}?{request.container_type}_id={request.container_id}",
        tool_name="find_data_product_delivery_methods_based_on_connection",
    )

    connection_id = response.get("attachments", [{}])[0].get("connection_id")
    if not connection_id:
        error_message = "Connection detail could not be found for this data asset. Make sure the asset is a connection asset."
        LOGGER.error(f"Failed to run find_data_product_delivery_methods_based_on_connection tool. {error_message}")
        raise ServiceError(f"Failed to run find_data_product_delivery_methods_based_on_connection tool. {error_message}")

    LOGGER.info(f"Connection ID found: {connection_id}")

    # step 2: get the datasource type from the connection
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/connections/{connection_id}?decrypt_secrets=true&{request.container_type}_id={request.container_id}&userfs=false",
        tool_name="find_data_product_delivery_methods_based_on_connection",
    )
    datasource_type = response["entity"]["datasource_type"]
    
    LOGGER.info(f"Datasource type found: {datasource_type}")

    # step 3: find delivery methods based on the datasource type
    search_payload = {"query": "*:*", "sort": "asset.name", "include": "entity"}

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_delivery_method/search?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=search_payload,
        tool_name="find_data_product_delivery_methods_based_on_connection",
    )
    available_delivery_methods = get_available_delivery_methods(response, datasource_type)
    
    LOGGER.info(f"Available delivery methods: {available_delivery_methods}")
    return FindDeliveryMethodsBasedOnConnectionResponse(
        delivery_methods=available_delivery_methods
    )
    

def get_available_delivery_methods(response, datasource_type):
    # this function iterates and finds all available delivery methods for this connection.
    available_delivery_methods = []
    for result in response["results"]:
        ibm_data_product_delivery_method_entity = result["entity"][
            "ibm_data_product_delivery_method"
        ]
        if datasource_type in ibm_data_product_delivery_method_entity.get(
            "supported_data_sources", []
        ):
            available_delivery_methods.append(
                DeliveryMethod(
                    delivery_method_id=result["metadata"]["asset_id"],
                    delivery_method_name=result["metadata"]["name"],
                    delivery_method_description=result["metadata"].get("description", "")
                )
            )
    return available_delivery_methods


@service_registry.tool(
    name="find_data_product_delivery_methods_based_on_connection",
    description="""Use this tool when you need to finds delivery methods available for the connection type of the data asset.
    Finds delivery methods for data asset (data_asset_id) in container_type (ID: container_id).
    This is called before `add_delivery_methods_to_data_product()` to find the delivery methods available for the given data asset.
    Example: 'Find delivery methods for customer asset in the data product draft' - This gets the container type ('catalog' or 'project') where this asset is in, the ID of the container, and the data asset ID.
    If you are not sure about the container ID, use the `list_containers` tool to find it out.
    If you are not sure about the data asset ID of the requested data asset, use the `search_asset` tool to find it out.
    Prompt user to choose delivery methods from the list of available delivery methods.
    Return: A list of available delivery methods for the data asset, including their IDs, names, and descriptions.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
    annotations={
        "title": "Find Delivery Methods Based on Connection Type",
        "readOnlyHint": True
    }
)
@auto_context
async def find_data_product_delivery_methods_based_on_connection(
    container_id: Annotated[str, Field(description="The ID of the container (catalog or project) where the data asset is located.")],
    container_type: Annotated[str, Field(description="The type of the container (either 'catalog' or 'project').")],
    data_asset_id: Annotated[str, Field(description="The ID of the data asset for which delivery methods are being requested.")]
) -> FindDeliveryMethodsBasedOnConnectionResponse:
    """Wrapper version that expands FindDeliveryMethodsBasedOnConnectionRequest object into individual parameters."""

    request = FindDeliveryMethodsBasedOnConnectionRequest(
        container_id=container_id,
        container_type=container_type,
        data_asset_id=data_asset_id
    )

    # Call the original find_delivery_methods_based_on_connection function
    return await _find_delivery_methods_based_on_connection(request)
    