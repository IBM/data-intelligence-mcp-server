# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.data_product.models.create_url_data_product import (
    CreateUrlDataProductRequest,
    CreateUrlDataProductResponse,
)
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service

from app.services.data_product.utils.data_product_creation_utils import (
    create_part_asset_and_set_relationship,
)
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user, get_data_product_url
from app.shared.logging import LOGGER, auto_context

@service_registry.tool(
    name="data_product_create_url_data_product",
    description="""
    This tool creates a URL data product. Example: 'Create a URL data product with <name>, <url>,.....'
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def create_url_data_product(
    request: CreateUrlDataProductRequest,
) -> CreateUrlDataProductResponse:
    LOGGER.info(
        f"In the data_product_create_url_data_product tool, creating URL data product with name {request.name}, URL name {request.url_name} and URL value {request.url_value}."
    )
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user()

    # step 1: create a URL asset in cams
    payload = {
        "metadata": {
            "name": request.url_name,
            "asset_type": "ibm_url_definition",
            "origin_country": None,
            "rov": {"mode": 0},
        },
        "entity": {
            "ibm_url_definition": {"url": request.url_value, "is_embeddable": False}
        },
    }

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/assets?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
        json=payload,
        tool_name="data_product_create_url_data_product"
    )
    url_asset_id = response["asset_id"]
    

    LOGGER.info(f"In the data_product_create_url_data_product tool, created URL Asset. {url_asset_id}")

    # step 2: get the delivery method id
    payload = {"query": "*:*", "sort": "asset.name", "include": "entity"}

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_delivery_method/search?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
        json=payload,
        tool_name="data_product_create_url_data_product"
    )

    delivery_method_id = ""
    for result in response["results"]:
        if result["metadata"]["name"] == "Open URL":
            delivery_method_id = result["metadata"]["asset_id"]

    if not delivery_method_id:
        LOGGER.error('Failed to run data_product_create_url_data_product tool. Delivery method "Open URL" is not found.')
        raise ServiceError('Failed to run data_product_create_url_data_product tool. Delivery method "Open URL" is not found')

    LOGGER.info(f"In the data_product_create_url_data_product tool tool, Got delivery method id - {delivery_method_id}.")

    # step 3: create ibm_data_product_part asset and set relationship between URL asset and ibm_data_product_part asset
    await create_part_asset_and_set_relationship(
        request.url_name, url_asset_id
    )

    # step 4: create a data product draft with the URL asset and delivery method
    # Note: The data product created here is a draft, user should attach business domain and contract to the draft
    # using attach_business_domain and attach_url_contract tools respectively
    # and then publish the draft using publish_data_product tool
    # until then the data product will remain in draft state
    payload = {
        "drafts": [
            {
                "asset": {"container": {"id": DPH_CATALOG_ID}},
                "version": None,
                "data_product": None,
                "name": request.name,
                "description": None,
                "types": None,
                "parts_out": [
                    {
                        "asset": {
                            "id": url_asset_id,
                            "container": {"id": DPH_CATALOG_ID},
                        },
                        "delivery_methods": [
                            {
                                "id": delivery_method_id,
                                "container": {"id": DPH_CATALOG_ID},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products",
        json=payload,
        tool_name="data_product_create_url_data_product"
    )
    create_dp_response = response
    draft = create_dp_response["drafts"][0]
    data_product_draft_id = draft["id"]
    contract_terms_id = draft["contract_terms"][0]["id"]

    LOGGER.info(
        f"In the data_product_create_url_data_product tool, created URL data product draft - {data_product_draft_id}, contract terms id: {contract_terms_id}."
    )

    return CreateUrlDataProductResponse(
        data_product_draft_id=data_product_draft_id,
        contract_terms_id=contract_terms_id,
        url=get_data_product_url(data_product_draft_id, "draft")
    )


@service_registry.tool(
    name="data_product_create_url_data_product",
    description="""
    This tool creates a URL data product. Example: 'Create a URL data product with <name>, <url>,.....'
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_create_url_data_product(
    name: str,
    url_name: str,
    url_value: str
) -> CreateUrlDataProductResponse:
    """Watsonx Orchestrator compatible version that expands CreateUrlDataProductRequest object into individual parameters."""

    request = CreateUrlDataProductRequest(
        name=name,
        url_name=url_name,
        url_value=url_value
    )

    # Call the original create_url_data_product function
    return await create_url_data_product(request)

