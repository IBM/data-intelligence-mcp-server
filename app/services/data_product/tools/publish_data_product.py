# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.data_product.models.publish_data_product import (
    PublishDataProductRequest,
    PublishDataProductResponse,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix, get_dph_catalog_id_for_user, get_data_product_url
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_publish_data_product",
    description="""
    This tool publishes a data product draft.
    Make sure to call this tool after all the required fields are filled in the data product draft, like name, domain, contract URL, delivery methods, etc.
    Example: 'Publish data product draft' - Get the data product draft ID from context.
    This receives the data product draft ID to publish the data product draft.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix()
@auto_context
async def publish_data_product(
    request: PublishDataProductRequest,
) -> PublishDataProductResponse:
    LOGGER.info(
        f"In the data_product_publish_data_product tool, publishing data product draft {request.data_product_draft_id}."
    )

    # first get the data product draft to validate if it has all mandatory fields set.
    response = await tool_helper_service.execute_get_request(
        f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
    )
    _validate_if_draft_has_a_business_domain(response)
    await _validate_if_draft_has_a_contract(response)
    await _validate_if_draft_has_delivery_method_added_to_each_data_asset(response)

    await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}/publish",
        tool_name="data_product_publish_data_product",
    )

    LOGGER.info(
        f"In the data_product_publish_data_product tool, data product draft {request.data_product_draft_id} published successfully."
    )
    return PublishDataProductResponse(
        message=f"Data product draft {request.data_product_draft_id} published successfully.",
        url=get_data_product_url(request.data_product_draft_id, "available")
    )

def _validate_if_draft_has_a_business_domain(response: dict) -> None:
    """
    This function validates if the draft has a business domain attached to it.
    """
    if not response.get("domain"):
        LOGGER.error("The draft has no business domain attached.")
        raise ServiceError("The draft appears to have no business domain attached. " \
                                     "Please attach a business domain before publishing the draft.")


async def _validate_if_draft_has_a_contract(response: dict) -> None:
    """
    This function validates if the draft has a contract attached to it.
    """
    contract_documents = response.get("contract_terms", [{}])[0].get("documents")
    if not contract_documents or len(contract_documents) == 0:
        query_params = {
            "include_contract_documents": True,
            "autopopulate_server_information": False
        }
        response = await tool_helper_service.execute_get_request(
                url=f'{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{response.get("id")}/contract_terms/{response.get("contract_terms", [{}])[0].get("id")}',
                params=query_params
            )
        if not response.get("overview", {}).get("name"):
            LOGGER.error("The draft has no contract attached.")
            raise ServiceError("The draft appears to have no contract attached. " \
                                        "Please attach a contract before publishing the draft.")


async def _validate_if_draft_has_delivery_method_added_to_each_data_asset(response: dict) -> None:
    """
    This function validates if each data asset of the draft has at least one delivery method added.
    """
    for part_out in response.get("parts_out", []):
        if part_out.get("delivery_methods", []) == []:
            dph_catalog_id = await get_dph_catalog_id_for_user()
            
            query_params = {
                "catalog_id": dph_catalog_id,
                "exclude": "columns"
            }
            response = await tool_helper_service.execute_get_request(
                url=f'{tool_helper_service.base_url}/v2/assets/{part_out.get("asset", {}).get("id")}',
                params=query_params
            )
            data_asset_name = response.get("metadata", {}).get("name", "")
            LOGGER.error(
                f"The data asset {data_asset_name} has no delivery methods added to it."
            )
            raise ServiceError(
                f"The data asset '{data_asset_name}' has no delivery methods added to it. "
                "All data assets added to the draft should have at least one delivery method added. "
                f"Please add delivery methods to the data asset before publishing the draft."
            )


@service_registry.tool(
    name="data_product_publish_data_product",
    description="""
    This tool publishes a data product draft.
    Make sure to call this tool after all the required fields are filled in the data product draft, like name, domain, contract URL, delivery methods, etc.
    Example: 'Publish data product draft' - Get the data product draft ID from context.
    This receives the data product draft ID to publish the data product draft.
    
    Args:
        data_product_draft_id (str): The ID of the data product draft to publish.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_publish_data_product(
    data_product_draft_id: str,
) -> PublishDataProductResponse:
    """Watsonx Orchestrator compatible version that expands PublishDataProductRequest object into individual parameters."""

    request = PublishDataProductRequest(
        data_product_draft_id=data_product_draft_id
    )

    # Call the original publish_data_product function
    return await publish_data_product(request)
