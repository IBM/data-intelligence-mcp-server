# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.data_product.models.create_url_data_product import (
    CreateUrlDataProductRequest,
    CreateUrlDataProductResponse,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token, get_dph_catalog_id_for_user
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE

from app.services.data_product.utils.data_product_creation_utils import (
    create_part_asset_and_set_relationship,
)
from app.core.settings import settings
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
    token = await get_access_token()
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user(token)

    # step 1: create a URL asset in cams
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    json = {
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

    client = get_http_client()

    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v2/assets?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
            headers=headers,
            data=json,
        )
    except ExternalAPIError as e:
        LOGGER.error(f"Failed to run data_product_create_url_data_product tool. Error while creating URL asset in CAMS: {str(e)}")
        raise ExternalAPIError(
            f"Failed to run data_product_create_url_data_product tool. Error while creating URL asset in CAMS: {str(e)}"
        )
    
    url_asset_id = response["asset_id"]

    LOGGER.info(f"In the data_product_create_url_data_product tool, created URL Asset. {url_asset_id}")

    # step 2: get the delivery method id
    json = {"query": "*:*", "sort": "asset.name", "include": "entity"}

    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v2/asset_types/ibm_data_product_delivery_method/search?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
            headers=headers,
            data=json,
        )

        delivery_method_id = ""
        for result in response["results"]:
            if result["metadata"]["name"] == "Open URL":
                delivery_method_id = result["metadata"]["asset_id"]

        if not delivery_method_id:
            LOGGER.error('Failed to run data_product_create_url_data_product tool. Delivery method "Open URL" is not found.')
            raise ServiceError('Failed to run data_product_create_url_data_product tool. Delivery method "Open URL" is not found')

    except ExternalAPIError as e:
        LOGGER.error(f"Failed to run data_product_create_url_data_product tool. Error while getting delivery method ID: {str(e)}")
        raise ExternalAPIError(
            f"Failed to run data_product_create_url_data_product tool. Error while getting delivery method ID: {str(e)}"
        )
    except ServiceError:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to run data_product_create_url_data_product tool. Error while getting delivery method ID: {str(e)}")
        raise ServiceError(
            f"Failed to run data_product_create_url_data_product tool. Error while getting delivery method ID: {str(e)}"
        )
    
    LOGGER.info(f"In the data_product_create_url_data_product tool tool, Got delivery method id - {delivery_method_id}.")

    # step 3: create ibm_data_product_part asset and set relationship between URL asset and ibm_data_product_part asset
    await create_part_asset_and_set_relationship(
        request.url_name, url_asset_id, DPH_CATALOG_ID, token
    )

    # step 4: create a data product draft with the URL asset and delivery method
    # Note: The data product created here is a draft, user should attach business domain and contract to the draft
    # using attach_business_domain and attach_url_contract tools respectively
    # and then publish the draft using publish_data_product tool (not implemented yet)
    # until then the data product will remain in draft state
    json = {
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
    try:
        response = await client.post(
            url=f"{settings.di_service_url}/data_product_exchange/v1/data_products",
            headers=headers,
            data=json,
        )
        create_dp_response = response
        draft = create_dp_response["drafts"][0]
        data_product_draft_id = draft["id"]
        contract_terms_id = draft["contract_terms"][0]["id"]
    except ExternalAPIError as e:
        LOGGER.error(f"Failed to run data_product_create_url_data_product tool. Error while creating data product draft: {str(e)}")
        raise ExternalAPIError(
            f"Failed to run data_product_create_url_data_product tool. Error while creating data product draft: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(f"Failed to run data_product_create_url_data_product tool. Error while creating data product draft: {str(e)}")
        raise ServiceError(
            f"Failed to run data_product_create_url_data_product tool. Error while creating data product draft: {str(e)}"
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
        create_data_product_response=create_dp_response,
    )
