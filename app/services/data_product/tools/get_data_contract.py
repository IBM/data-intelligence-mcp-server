# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.data_product.models.get_data_contract import GetDataContractRequest, GetDataContractResponse
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.utils_tools import format_dict_for_table
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user, extract_contract_terms_id

from typing import Any, Dict, Literal, Annotated
from pydantic import Field


async def _get_draft_contract(data_product_version_id: str) -> Dict[str, Any] | bytes:
    """Get data contract for a draft data product.
    
    Args:
        data_product_version_id: The ID of the draft data product version
        
    Returns:
        Dict[str, Any] | bytes: The contract document response
    """
    # Step 1: get data contract terms ID
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{data_product_version_id}",
    )
    contract_terms_id = extract_contract_terms_id(response, "data product draft")

    # Step 2: get contract document
    query_params = {
        "format": "odcs",
        "format_version": "3"
    }
    return await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{data_product_version_id}/contract_terms/{contract_terms_id}/format",
        params=query_params
    )


async def _get_published_contract(data_product_version_id: str) -> Dict[str, Any] | bytes:
    """Get data contract for a published data product.
    
    Args:
        data_product_version_id: The ID of the published data product version
        
    Returns:
        Dict[str, Any] | bytes: The contract document response
    """
    # Step 1: get data contract terms ID
    query_params = {
        "check_caller_approval": False
    }
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/releases/{data_product_version_id}",
        params=query_params
    )
    contract_terms_id = extract_contract_terms_id(response, "data product")

    # Step 2: get contract document
    query_params = {
        "include_contract_documents": True
    }
    return await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/releases/{data_product_version_id}/contract_terms/{contract_terms_id}",
        params=query_params
    )


async def _get_data_contract(request: GetDataContractRequest) -> GetDataContractResponse:
    data_product_version_id = request.data_product_version_id
    
    if "@" not in data_product_version_id:
        dph_catalog_id = await get_dph_catalog_id_for_user()
        data_product_version_id = f"{data_product_version_id}@{dph_catalog_id}"
    
    if request.data_product_state == "draft":
        response = await _get_draft_contract(data_product_version_id)
    else:
        response = await _get_published_contract(data_product_version_id)
    
    if isinstance(response, bytes):
        raise ServiceError("Expected dict response but got bytes for data contract.")
    
    formatted_data = format_dict_for_table(response)
    
    ui_message_context.add_table_ui_message(
        tool_name="get_data_product_contract",
        formatted_data=formatted_data,
        title="Data Contract"
    )
    
    return GetDataContractResponse(data_contract=str(response))


@service_registry.tool(
    name="get_data_product_contract",
    description="""Use this tool when you need to retrieve data contract for the specified data product, whether it's in draft or published (available) state.
    Example: 'Get me data contract for <data product name>'
    This tool should receive data product version ID of the specified data product as input from context. Ask for the data product state from the user.
    Returns: This tool returns the data contract of the data product.
    """,
    tags={"read", "data_product", "sample"},
    meta={"version": "1.0", "service": "data_product"},
    annotations={
        "title": "Get Data Contract for Draft and Published Data Products",
        "readOnlyHint": True
    }
)
@auto_context
async def get_data_product_contract(
    data_product_version_id: Annotated[str, Field(description="The ID of the data product version for which we need to get the data contract. Can be a draft or published data product.")],
    data_product_state: Annotated[Literal["draft", "available"], Field(description="The state of the data product - should be one of 'draft' or 'available'")]
) -> GetDataContractResponse:
    """Wrapper version that expands GetDataContractRequest object into individual parameters."""

    request = GetDataContractRequest(
        data_product_version_id=data_product_version_id,
        data_product_state=data_product_state,
    )

    return await _get_data_contract(request)
