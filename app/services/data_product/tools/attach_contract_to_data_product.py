# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.data_product.models.attach_contract_to_data_product import (
    AttachURLContractToDataProductRequest,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_attach_url_contract_to_data_product",
    description="""
    This tool attaches the given URL contract to a data product draft.
    Appropriate success message is sent if the URL contract is attached to the data product draft.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix(field_name="data_product_draft_id")
@add_catalog_id_suffix(field_name="contract_terms_id")
@auto_context
async def attach_url_contract_to_data_product(
    request: AttachURLContractToDataProductRequest,
) -> str:
    LOGGER.info(
        f"In the data_product_attach_url_contract_to_data_product tool, attaching URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."
    )
    
    # step 1: attach the URL contract to data product draft
    payload = {
        "url": request.contract_url,
        "type": "terms_and_conditions",
        "name": request.contract_name,
    }
    
    await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}/contract_terms/{request.contract_terms_id}/documents",
        json=payload,
        tool_name="data_product_attach_url_contract_to_data_product",
    )
    
    LOGGER.info(
        f"In the data_product_attach_url_contract_to_data_product tool, attached URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."
    )
    return f"Attached URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."


@service_registry.tool(
    name="data_product_attach_url_contract_to_data_product",
    description="""
    This tool attaches the given URL contract to a data product draft.
    Appropriate success message is sent if the URL contract is attached to the data product draft.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_attach_url_contract_to_data_product(
    contract_url: str,
    contract_name: str,
    contract_terms_id: str,
    data_product_draft_id: str
) -> str:
    """Watsonx Orchestrator compatible version that expands AttachURLContractToDataProductRequest object into individual parameters."""

    request = AttachURLContractToDataProductRequest(
        contract_url=contract_url,
        contract_name=contract_name,
        contract_terms_id=contract_terms_id,
        data_product_draft_id=data_product_draft_id
    )

    # Call the original attach_url_contract_to_data_product function
    return await attach_url_contract_to_data_product(request)
