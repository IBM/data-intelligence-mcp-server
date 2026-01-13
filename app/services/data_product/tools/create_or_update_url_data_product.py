# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.data_product.models.create_or_update_url_data_product import (
    CreateOrUpdateUrlDataProductRequest,
    CreateOrUpdateUrlDataProductResponse,
)
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service

from app.services.data_product.utils.data_product_creation_utils import (
    is_data_product_draft_create,
    validate_inputs_for_draft_create,
    create_part_asset_and_set_relationship,
)
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user, get_data_product_url
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_create_or_update_url_data_product",
    description="""
    This tool creates a data product draft from a URL or updates an existing draft to add a URL asset to it.
    Example 1 - Create a URL data product draft:
        'Create a URL data product with <name>, <url>,.....'
    Example 2 - Add a URL asset to an existing data product draft:
        In this case, request.existing_data_product_draft_id is NOT null/None.
        Identifies the data product draft by request.existing_data_product_draft_id and adds the URL asset to the data product draft.
        'Add a URL asset to data product draft <url>,.....'
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def create_or_update_url_data_product(
    request: CreateOrUpdateUrlDataProductRequest,
) -> CreateOrUpdateUrlDataProductResponse:
    LOGGER.info(
        f"In the data_product_create_or_update_url_data_product tool, creating URL data product with name {request.name}, URL name {request.url_name} and URL value {request.url_value}."
    )
    if is_data_product_draft_create(request):
        LOGGER.info("This is a data product draft creation.")
        validate_inputs_for_draft_create(request, "url_value", "url_name")

    dph_catalog_id = await get_dph_catalog_id_for_user()

    # step 1: create a URL asset in cams
    url_asset_id = await create_url_asset_in_cams(request, dph_catalog_id)
    
    # step 2: get the delivery method id for Open URL
    delivery_method_id = await get_delivery_method_id_for_open_url(dph_catalog_id)

    # step 3: create ibm_data_product_part asset and set relationship between URL asset and ibm_data_product_part asset
    await create_part_asset_and_set_relationship(
        request.url_name, url_asset_id
    )

    # step 4: create a data product draft with the URL asset and delivery method
    # Note: The data product created here is a draft, user should attach business domain and contract to the draft
    # using attach_business_domain and attach_url_contract tools respectively
    # and then publish the draft using publish_data_product tool
    # until then the data product will remain in draft state
    if is_data_product_draft_create(request):
        # This is not adding data asset item operation, so creating data product draft.
        payload = get_data_product_draft_with_delivery_method_creation_payload(
            dph_catalog_id, request, url_asset_id, delivery_method_id
        )
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products",
            json=payload,
            tool_name="data_product_create_or_update_url_data_product"
        )
        LOGGER.info(
            "In the data_product_create_or_update_url_data_product tool, created URL data product draft"
        )
        message = "Created data product draft with the provided URL successfully."
        draft = response["drafts"][0]
    else:
        # Draft exists already. The task is to add a URL asset item to the existing draft.
        payload = get_patch_data_asset_items_with_delivery_method_to_draft_payload(
            dph_catalog_id, url_asset_id, delivery_method_id
        )
        response = await tool_helper_service.execute_patch_request(
            url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.existing_data_product_draft_id}",
            json=payload,
            tool_name="data_product_create_or_update_url_data_product",
        )
        LOGGER.info(
            "In the data_product_create_or_update_url_data_product tool, patched data product draft with the provided URL asset."
        )
        message = "Updated data product draft with the provided URL asset item successfully."
        draft = response

    data_product_draft_id = request.existing_data_product_draft_id if request.existing_data_product_draft_id else draft["id"]
    contract_terms_id = draft["contract_terms"][0]["id"]

    return CreateOrUpdateUrlDataProductResponse(
        message=message,
        data_product_draft_id=data_product_draft_id,
        contract_terms_id=contract_terms_id,
        url=get_data_product_url(data_product_draft_id, "draft")
    )


async def create_url_asset_in_cams(request: CreateOrUpdateUrlDataProductRequest, dph_catalog_id: str) -> str:
    """
    This function creates an asset in the catalog.
    """
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
        url=f"{tool_helper_service.base_url}/v2/assets?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=payload,
        tool_name="data_product_create_or_update_url_data_product"
    )
    url_asset_id = response["asset_id"]
    LOGGER.info(f"In the data_product_create_or_update_url_data_product tool, created URL Asset. {url_asset_id}")
    return url_asset_id


async def get_delivery_method_id_for_open_url(dph_catalog_id: str) -> str:
    """
    This function is used to get the delivery method id for the open url.
    """
    payload = {"query": "*:*", "sort": "asset.name", "include": "entity"}

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_delivery_method/search?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=payload,
        tool_name="data_product_create_or_update_url_data_product"
    )

    delivery_method_id = ""
    for result in response["results"]:
        if result["metadata"]["name"] == "Open URL":
            delivery_method_id = result["metadata"]["asset_id"]

    if not delivery_method_id:
        LOGGER.error('Failed to run data_product_create_or_update_url_data_product tool. Delivery method "Open URL" is not found.')
        raise ServiceError('Failed to run data_product_create_or_update_url_data_product tool. Delivery method "Open URL" is not found')

    LOGGER.info(f"In the data_product_create_or_update_url_data_product tool tool, Got delivery method id - {delivery_method_id}.")
    return delivery_method_id


def get_data_product_draft_with_delivery_method_creation_payload(
    dph_catalog_id: str, request: CreateOrUpdateUrlDataProductRequest, url_asset_id: str, delivery_method_id: str
) -> dict:
    return {
        "drafts": [
            {
                "asset": {"container": {"id": dph_catalog_id}},
                "version": None,
                "data_product": None,
                "name": request.name,
                "description": request.description,
                "types": None,
                "parts_out": [
                    {
                        "asset": {
                            "id": url_asset_id,
                            "container": {"id": dph_catalog_id},
                        },
                        "delivery_methods": [
                            {
                                "id": delivery_method_id,
                                "container": {"id": dph_catalog_id},
                            }
                        ],
                    }
                ],
            }
        ]
    }


def get_patch_data_asset_items_with_delivery_method_to_draft_payload(
    dph_catalog_id: str, data_asset_id: str, delivery_method_id: str
) -> list[dict]:
    return [
        {
            "op": "add",
            "path": "/parts_out/-",
            "value": {
                "asset": {
                    "id": data_asset_id,
                    "container": {
                        "id": dph_catalog_id,
                        "type": "catalog"
                    },
                    "type": "ibm_url_definition"
                },
                "delivery_methods": [
                    {
                        "id": delivery_method_id,
                        "container": {"id": dph_catalog_id},
                    }
                ]
            }
        }
    ]


@service_registry.tool(
    name="data_product_create_or_update_url_data_product",
    description="""
    This tool creates a data product draft from a URL or updates an existing draft to add a URL asset to it.
    Example 1 - Create a URL data product draft:
        'Create a URL data product with <name>, <url>,.....'
    Example 2 - Add a URL asset to an existing data product draft:
        In this case, request.existing_data_product_draft_id is NOT null/None.
        Identifies the data product draft by request.existing_data_product_draft_id and adds the URL asset to the data product draft.
        'Add a URL asset to data product draft <url>,.....'

    Args:
        name (str): The name of the data product. Read the value from user.
        description (str): The description of the data product. Read the value from user.
        url_value (str): The URL value of the data product. Read the value from user.
        url_name (str): The URL name of the data product. Read the value from user.
        existing_data_product_draft_id (str | None, optional): The ID of the existing data product draft. This field is populated only if we are adding a URL asset item to an existing draft, otherwise this field value is None.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_create_or_update_url_data_product(
    name: str,
    description: str,
    url_name: str,
    url_value: str,
    existing_data_product_draft_id: str
) -> CreateOrUpdateUrlDataProductResponse:
    """Watsonx Orchestrator compatible version that expands CreateOrUpdateUrlDataProductRequest object into individual parameters."""

    request = CreateOrUpdateUrlDataProductRequest(
        name=name,
        description=description,
        url_name=url_name,
        url_value=url_value,
        existing_data_product_draft_id=existing_data_product_draft_id
    )

    # Call the original create_or_update_url_data_product function
    return await create_or_update_url_data_product(request)

