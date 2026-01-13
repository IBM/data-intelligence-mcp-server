# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.data_product.models.get_data_contract import GetDataContractRequest, GetDataContractResponse
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context

from typing import Literal


def _extract_contract_terms_id(response: dict, context: str) -> str:
    """Extract and validate contract terms ID from response.
    
    Args:
        response: API response containing contract terms
        context: Context description for error messages (e.g., "data product draft")
        
    Returns:
        str: The contract terms ID
        
    Raises:
        ServiceError: If no contract terms ID is found
    """
    contract_terms = response.get("contract_terms", [])
    if not contract_terms:
        LOGGER.info(f"No contract terms found for {context}.")
        raise ServiceError(f"No contract terms found for {context}.")
    
    contract_terms_id = contract_terms[0].get("id")
    if not contract_terms_id:
        LOGGER.info(f"No contract terms found for {context}.")
        raise ServiceError(f"No contract terms found for {context}.")
    return contract_terms_id


async def _get_draft_contract(data_product_id: str) -> dict:
    """Get data contract for a draft data product.
    
    Args:
        data_product_id: The ID of the draft data product
        
    Returns:
        dict: The contract document response
    """
    # Step 1: get data contract terms ID
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{data_product_id}",
    )
    contract_terms_id = _extract_contract_terms_id(response, "data product draft")

    # Step 2: get contract document
    query_params = {
        "format": "odcs",
        "format_version": "3"
    }
    return await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{data_product_id}/contract_terms/{contract_terms_id}/format",
        params=query_params
    )


async def _get_published_contract(data_product_id: str) -> dict:
    """Get data contract for a published data product.
    
    Args:
        data_product_id: The ID of the published data product
        
    Returns:
        dict: The contract document response
    """
    # Step 1: get data product version ID
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/{data_product_id}"
    )
    release_id = response.get("latest_release", {}).get("id")

    # Step 2: get data contract terms ID
    query_params = {
        "check_caller_approval": False
    }
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/{data_product_id}/releases/{release_id}",
        params=query_params
    )
    contract_terms_id = _extract_contract_terms_id(response, "data product")

    # Step 3: get contract document
    query_params = {
        "include_contract_documents": True
    }
    return await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/{data_product_id}/releases/{release_id}/contract_terms/{contract_terms_id}",
        params=query_params
    )


@service_registry.tool(
    name="data_product_get_data_contract",
    description="""
    This tool is used to get data contract for the specified data product (draft/published (available)).
    Example: 'Get me data contract for <data product name>'
    This tool should receive data product ID of the specified data product as input from context. Ask for the data product state from the user.
    """,
    tags={"sample", "data_product"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def get_data_contract(request: GetDataContractRequest) -> GetDataContractResponse:
    if request.data_product_state == "draft":
        response = await _get_draft_contract(request.data_product_id)
    else:
        response = await _get_published_contract(request.data_product_id)
    
    return GetDataContractResponse(data_contract=str(response))


@service_registry.tool(
    name="data_product_get_data_contract",
    description="""
    This tool is used to get data contract for the specified data product (draft/published (available)).
    Example: 'Get me data contract for <data product name>'
    This tool should receive data product ID of the specified data product as input from context. Ask for the data product state from the user.
    
    Args:
        data_product_id: str = The ID of the data product for which we need to get the data contract. Can be a draft or published data product.
        data_product_state: str = The state of the data product - should be one of 'draft' or 'available'
    Returns:
        str = The data contract.
    """,
    tags={"read", "data_product"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def wxo_get_data_contract(data_product_id: str,
        data_product_state: Literal["draft", "available"]) -> GetDataContractResponse:
    """Watsonx Orchestrator compatible version that expands GetDataContractRequest object into individual parameters."""

    request = GetDataContractRequest(
        data_product_id=data_product_id,
        data_product_state=data_product_state,
    )

    return await get_data_contract(request)
