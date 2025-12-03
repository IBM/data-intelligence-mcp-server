# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.data_product.models.attach_business_domain_to_data_product import (
    AttachBusinessDomainToDataProductRequest,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix, get_dph_catalog_id_for_user
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import JSON_CONTENT_TYPE, JSON_PATCH_CONTENT_TYPE
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
        f"In the data_product_attach_business_domain_to_data_product tool, attaching business domain {request.domain} to the data product draft {request.data_product_draft_id}."
    )
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user()

    # step 1: get the business domain id from cams
    search_payload = {"query": "*:*", "sort": "asset.name"}
    
    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_domain/search?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
        json=search_payload,
        tool_name="data_product_attach_business_domain_to_data_product",
    )
    
    domain_id = ""
    available_domains = []
    for result in response["results"]:
        if result["metadata"]["name"].lower() == request.domain.lower():
            domain_id = result["metadata"]["asset_id"]
        available_domains.append(result["metadata"]["name"])

    if not domain_id:
        error_message = f'Domain name "{request.domain}" is not found, so it is not attached to {request.data_product_draft_id}. Here are the available domains: {available_domains}'
        LOGGER.error(f"Failed to run data_product_attach_business_domain_to_data_product tool. {error_message}")
        raise ServiceError(f"Failed to run data_product_attach_business_domain_to_data_product tool. {error_message}")

    # step 2: attach the business domain to data product draft
    headers = {
        "Accept": JSON_CONTENT_TYPE,
        "Content-Type": JSON_PATCH_CONTENT_TYPE,
    }
    patch_payload = [
        {
            "op": "add",
            "path": "/domain",
            "value": {"id": domain_id, "name": request.domain},
        }
    ]
    
    await tool_helper_service.execute_patch_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
        headers=headers,
        json=patch_payload,
        tool_name="data_product_attach_business_domain_to_data_product",
    )

    LOGGER.info(
        f"In the data_product_attach_business_domain_to_data_product tool, business domain {request.domain} attached to the data product draft {request.data_product_draft_id}."
    )
    return f"Business domain {request.domain} is attached to the data product draft {request.data_product_draft_id}."


@service_registry.tool(
    name="data_product_attach_business_domain_to_data_product",
    description="""
    This tool attaches the given business domain to a data product draft.
    The business domain given should be a valid business domain in the system or else this returns the list of business domains available to choose from.
    Appropriate success message is sent if the business domain is attached to the data product draft.
    
    Args:
        domain (str): The business domain to be attached to the data product draft.
        data_product_draft_id (str): The ID of the data product draft to which the business domain is to be attached.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_attach_business_domain_to_data_product(
    domain: str,
    data_product_draft_id: str
) -> str:
    """Watsonx Orchestrator compatible version that expands AttachBusinessDomainToDataProductRequest object into individual parameters."""

    request = AttachBusinessDomainToDataProductRequest(
        domain=domain,
        data_product_draft_id=data_product_draft_id
    )

    # Call the original attach_business_domain_to_data_product function
    return await attach_business_domain_to_data_product(request)
