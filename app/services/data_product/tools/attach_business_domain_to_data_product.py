# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.data_product.models.attach_business_domain_to_data_product import (
    AttachBusinessDomainToDataProductRequest,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token, get_dph_catalog_id_for_user
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE, JSON_PATCH_CONTENT_TYPE
from app.core.settings import settings
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_attach_business_domain_to_data_product",
    description="""
    This tool attaches the given business domain to a data product draft.
    The business domain given should be a valid business domain in the system or else this returns the list of business domains available to choose from.
    Appropriate success message is sent if the business domain is attached to the data product draft.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix()
@auto_context
async def attach_business_domain_to_data_product(
    request: AttachBusinessDomainToDataProductRequest,
) -> str:
    LOGGER.info(
        f"In the data_product.attach_business_domain_to_data_product tool, attaching business domain {request.domain} to the data product draft {request.data_product_draft_id}."
    )
    token = await get_access_token()
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user(token)

    # step 1: get the business domain id from cams
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    json = {"query": "*:*", "sort": "asset.name"}
    client = get_http_client()
    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v2/asset_types/ibm_data_product_domain/search?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
            headers=headers,
            data=json,
        )
    except ExternalAPIError:
        raise
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product.attach_business_domain_to_data_product tool. Error while getting business domain information: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product.attach_business_domain_to_data_product tool. Error while getting business domain information: {str(e)}"
        )

    domain_id = ""
    available_domains = []
    for result in response["results"]:
        if result["metadata"]["name"].lower() == request.domain.lower():
            domain_id = result["metadata"]["asset_id"]
        available_domains.append(result["metadata"]["name"])

    if not domain_id:
        LOGGER.error(
            f'Failed to run data_product.attach_business_domain_to_data_product tool. Domain name "{request.domain}" is not found, so it is not attached to {request.data_product_draft_id}. Here are the available domains: {available_domains}'
        )
        raise ServiceError(
            f'Failed to run data_product.attach_business_domain_to_data_product tool. Domain name "{request.domain}" is not found, so it is not attached to {request.data_product_draft_id}. Here are the available domains: {available_domains}'
        )

    # step 2: attach the business domain to data product draft
    headers = {
        "Accept": JSON_CONTENT_TYPE,
        "Content-Type": JSON_PATCH_CONTENT_TYPE,
        "Authorization": token,
    }
    json = [
        {
            "op": "add",
            "path": "/domain",
            "value": {"id": domain_id, "name": request.domain},
        }
    ]
    try:
        response = await client.patch(
            url=f"{settings.di_service_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
            headers=headers,
            data=json,
        )
    except ExternalAPIError:
        raise
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product.attach_business_domain_to_data_product tool. Error while attaching business domain to data product: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product.attach_business_domain_to_data_product tool. Error while attaching business domain to data product: {str(e)}"
        )

    LOGGER.info(
        f"In the data_product.attach_business_domain_to_data_product tool, business domain {request.domain} attached to the data product draft {request.data_product_draft_id}."
    )
    return f"Business domain {request.domain} is attached to the data product draft {request.data_product_draft_id}."
