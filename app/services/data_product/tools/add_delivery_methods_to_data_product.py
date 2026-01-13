# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.data_product.models.add_delivery_methods_to_data_product import (
    AddDeliveryMethodsToDataProductRequest,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix, get_dph_catalog_id_for_user, validate_inputs
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import JSON_CONTENT_TYPE, JSON_PATCH_CONTENT_TYPE
from app.shared.logging import LOGGER, auto_context

from typing import List


@service_registry.tool(
    name="data_product_add_delivery_methods_to_data_product",
    description="""
    This tool adds delivery methods selected by user to a data product draft. DO NOT make up delivery methods, use the corresponding ID values for the delivery methods selected by the user.
    This is called after `find_delivery_methods_based_on_connection()` to add the delivery methods selected by the user to the data product draft.
    Example: Adding two delivery methods to an asset in the draft.
        'Add flight and download delivery methods to customer asset in the data product draft'- This gets the data product draft ID from context, data asset name (in this case, customer), the delivery method IDs from context matching the delivery methods selected by the user from the previous tool call.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix()
@auto_context
async def add_delivery_methods_to_data_product(
    request: AddDeliveryMethodsToDataProductRequest,
) -> str:
    LOGGER.info(
        f"In the data_product_add_delivery_methods_to_data_product tool, adding delivery methods {request.delivery_method_ids} to data product draft id: {request.data_product_draft_id}"
    )
    validate_inputs(request, "data_asset_name")
    dph_catalog_id = await get_dph_catalog_id_for_user()

    # step 1: get the index of parts out asset
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
        tool_name="data_product_add_delivery_methods_to_data_product",
    )
    query_params = {
        "catalog_id": dph_catalog_id,
        "exclude": "columns",
        "hide_deprecated_response_fields": False
    }
    parts_out_list = response.get("parts_out", [])
    index_list = []
    for index, parts_out in enumerate(parts_out_list):
        asset = parts_out.get("asset", {})
        if asset.get("type") == "data_asset":
            asset_response = await tool_helper_service.execute_get_request(
                url=f"{tool_helper_service.base_url}/v2/assets/{asset.get('id')}",
                params=query_params,
                tool_name="data_product_add_delivery_methods_to_data_product",
            )
            if asset_response.get("metadata", {}).get("name", "").lower() == request.data_asset_name.lower():
                index_list.append(index)
    if not index_list:
        LOGGER.error(f"Asset {request.data_asset_name} is not found in data product draft.")
        raise ServiceError(f"Asset {request.data_asset_name} is not found in data product draft.")
  
    # step 2: add delivery methods to the asset
    json = []
    for index in index_list:
        for delivery_method_id in request.delivery_method_ids:
            LOGGER.info(f"Adding delivery method id: {delivery_method_id} to data asset {index}")
            json.append(
                {
                    "op": "add",
                    "path": f"/parts_out/{index}/delivery_methods/-",
                    "value": {
                        "id": delivery_method_id,
                        "container": {"id": dph_catalog_id, "type": "catalog"},
                        "properties": {},
                    },
                }
            )

    await tool_helper_service.execute_patch_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
        json=json,
        tool_name="data_product_add_delivery_methods_to_data_product",
    )

    LOGGER.info(
        f"Delivery methods {request.delivery_method_ids} added to {request.data_asset_name} of the data product draft {request.data_product_draft_id} successfully."
    )
    if len(index_list) == 1:
        return f"Delivery methods {request.delivery_method_ids} added to {request.data_asset_name} asset item of the data product draft {request.data_product_draft_id} successfully."
    else:
        return f"There were multiple assets with the same name as {request.data_asset_name} in the data product draft. The given delivery methods {request.delivery_method_ids} are added to all those assets of the draft {request.data_product_draft_id}."


@service_registry.tool(
    name="data_product_add_delivery_methods_to_data_product",
    description="""
    This tool adds delivery methods selected by user to a data product draft. DO NOT make up delivery methods, use the corresponding ID values for the delivery methods selected by the user.
    This is called after `find_delivery_methods_based_on_connection()` to add the delivery methods selected by the user to the data product draft.
    Example: Adding two delivery methods to an asset in the draft.
        'Add flight and download delivery methods to customer asset in the data product draft'- This gets the data product draft ID from context, data asset name (in this case, customer), the delivery method IDs from context matching the delivery methods selected by the user from the previous tool call.
    
    Args:
        data_product_draft_id (str): The ID of the data product draft.
        data_asset_name (str): The name of the data asset in the data product draft for which we need to add delivery methods.
        delivery_method_ids (List[str]): The list of IDs of delivery methods selected by the user.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_add_delivery_methods_to_data_product(
    data_product_draft_id: str,
    data_asset_name: str,
    delivery_method_ids: List[str],
) -> str:
    """Watsonx Orchestrator compatible version that expands AddDeliveryMethodsToDataProductRequest object into individual parameters."""

    request = AddDeliveryMethodsToDataProductRequest(
        data_product_draft_id=data_product_draft_id,
        data_asset_name=data_asset_name,
        delivery_method_ids=delivery_method_ids,
    )

    # Call the original add_delivery_methods_to_data_product function
    return await add_delivery_methods_to_data_product(request)
    