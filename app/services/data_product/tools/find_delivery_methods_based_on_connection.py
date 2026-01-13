# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

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


@service_registry.tool(
    name="data_product_find_delivery_methods_based_on_connection",
    description="""
    This tool finds delivery methods available for the connection type of the data asset.
    This is called before `add_delivery_methods_to_data_product()` to find the delivery methods available for the given connection type.
    Example: 'Find delivery methods for customer asset in the data product draft' - This gets the data product draft ID from context and data asset name (in this case, customer).
    Prompt user to choose delivery methods from the list of available delivery methods.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix()
@auto_context
async def find_delivery_methods_based_on_connection(
    request: FindDeliveryMethodsBasedOnConnectionRequest, 
) -> FindDeliveryMethodsBasedOnConnectionResponse:
    LOGGER.info(
        f"In the data_product_find_delivery_methods_based_on_connection tool, finding delivery methods for data product draft id: {request.data_product_draft_id}"
    )
    validate_inputs(request, "data_asset_name")
    dph_catalog_id = await get_dph_catalog_id_for_user()

    # step 1: get the connection ID from the contract terms of the data product draft
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
        tool_name="data_product_find_delivery_methods_based_on_connection",
    )
    
    contract_terms = response["contract_terms"]
    connection_id = None
    if contract_terms and len(contract_terms) > 0:
        connection_schema_list = contract_terms[0]["schema"]
        for connection_schema in connection_schema_list:
            if connection_schema.get("name", "").lower() == request.data_asset_name.lower():
                connection_id = connection_schema.get("connection_id")

    if not connection_id:
        error_message = "Asset name is not valid or connection detail is not found for the asset."
        LOGGER.error(f"Failed to run data_product_find_delivery_methods_based_on_connection tool. {error_message}")
        raise ServiceError(f"Failed to run data_product_find_delivery_methods_based_on_connection tool. {error_message}")

    LOGGER.info(f"Connection ID found: {connection_id}")

    # step 2: get the datasource type from the connection
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/connections/{connection_id}?decrypt_secrets=true&catalog_id={dph_catalog_id}&userfs=false",
        tool_name="data_product_find_delivery_methods_based_on_connection",
    )
    datasource_type = response["entity"]["datasource_type"]
    
    LOGGER.info(f"Datasource type found: {datasource_type}")

    # step 3: find delivery methods based on the datasource type
    search_payload = {"query": "*:*", "sort": "asset.name", "include": "entity"}

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_delivery_method/search?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=search_payload,
        tool_name="data_product_find_delivery_methods_based_on_connection",
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
                )
            )
    return available_delivery_methods

@service_registry.tool(
    name="data_product_find_delivery_methods_based_on_connection",
    description="""
    This tool finds delivery methods available for the connection type of the data asset.
    This is called before `add_delivery_methods_to_data_product()` to find the delivery methods available for the given connection type.
    Example: 'Find delivery methods for customer asset in the data product draft' - This gets the data product draft ID from context and data asset name (in this case, customer).
    Prompt user to choose delivery methods from the list of available delivery methods.
    
    Args:
        data_product_draft_id (str): The ID of the data product draft.
        data_asset_name (str): The name of the data asset for which we need to find the delivery method options.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_find_delivery_methods_based_on_connection(
    data_product_draft_id: str,
    data_asset_name: str,
) -> FindDeliveryMethodsBasedOnConnectionResponse:
    """Watsonx Orchestrator compatible version that expands FindDeliveryMethodsBasedOnConnectionRequest object into individual parameters."""

    request = FindDeliveryMethodsBasedOnConnectionRequest(
        data_product_draft_id=data_product_draft_id,
        data_asset_name=data_asset_name,
    )

    # Call the original find_delivery_methods_based_on_connection function
    return await find_delivery_methods_based_on_connection(request)
    