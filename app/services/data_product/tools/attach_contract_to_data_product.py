# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.data_product.models.attach_contract_to_data_product import (
    AttachURLContractToDataProductRequest,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
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
        f"In the data_product.attach_url_contract_to_data_product tool, attaching URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."
    )
    # step 1: attach the URL contract to data product draft
    token = await get_access_token()
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    json = {
        "url": request.contract_url,
        "type": "terms_and_conditions",
        "name": request.contract_name,
    }
    client = get_http_client()
    try:
        await client.post(
            url=f"{settings.di_service_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}/contract_terms/{request.contract_terms_id}/documents",
            headers=headers,
            data=json,
        )
    except ExternalAPIError:
        raise
    except Exception as e:
        LOGGER.error(f"Failed to run data_product.attach_url_contract_to_data_product tool. Error while attaching URL contract to data product: {str(e)}")
        raise ServiceError(
            f"Failed to run data_product.attach_url_contract_to_data_product tool. Error while attaching URL contract to data product: {str(e)}"
        )

    LOGGER.info(
        f"In the data_product.attach_url_contract_to_data_product tool, attached URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."
    )
    return f"Attached URL contract {request.contract_url} with name {request.contract_name} to the data product draft {request.data_product_draft_id}."
