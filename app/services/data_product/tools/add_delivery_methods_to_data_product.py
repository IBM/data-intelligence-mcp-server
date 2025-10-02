from app.core.registry import service_registry
from app.services.data_product.models.add_delivery_methods_to_data_product import (
    AddDeliveryMethodsToDataProductRequest,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.services.data_product.utils.common_utils import add_catalog_id_suffix
from app.core.auth import get_access_token, get_dph_catalog_id_for_user
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE, JSON_PATCH_CONTENT_TYPE
from app.core.settings import settings
from app.shared.logging import LOGGER, auto_context

from typing import List


@service_registry.tool(
    name="data_product_add_delivery_methods_to_data_product",
    description="""
    This tool adds delivery methods selected by user to a data product draft. DO NOT make up delivery methods, use the corresponding ID values for the delivery methods selected by the user.
    This is called after `find_delivery_methods_based_on_connection()` to add the delivery methods selected by the user to the data product draft.
    Example: 'Add delivery methods to data product draft' - Get the data product draft ID from context and the delivery method IDs from context matching the delivery methods selected by the user from the previous tool call.
    This receives the data product draft ID and the list of delivery method IDs selected by the user.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix()
@auto_context
async def add_delivery_methods_to_data_product(
    request: AddDeliveryMethodsToDataProductRequest,
) -> str:
    LOGGER.info(
        f"In the data_product_add_delivery_methods_to_data_product tool, adding delivery methods {request.delivery_method_ids} to data product draft id: {request.data_product_draft_id}"
    )
    token = await get_access_token()
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user(token)

    headers = {
        "Accept": JSON_CONTENT_TYPE,
        "Content-Type": JSON_PATCH_CONTENT_TYPE,
        "Authorization": token,
    }

    client = get_http_client()

    try:
        json = []
        for delivery_method_id in request.delivery_method_ids:
            LOGGER.info(f"Adding delivery method id: {delivery_method_id}")
            json.append(
                {
                    "op": "add",
                    "path": "/parts_out/0/delivery_methods/-",
                    "value": {
                        "id": delivery_method_id,
                        "container": {"id": DPH_CATALOG_ID, "type": "catalog"},
                        "properties": {},
                    },
                }
            )

        await client.patch(
            url=f"{settings.di_service_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
            headers=headers,
            data=json,
        )

        LOGGER.info(
            f"Delivery methods {request.delivery_method_ids} added to data product draft {request.data_product_draft_id} successfully."
        )
        return f"Delivery methods {request.delivery_method_ids} added to data product draft {request.data_product_draft_id} successfully."

    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_add_delivery_methods_to_data_product tool. Error while adding delivery methods to data product: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_add_delivery_methods_to_data_product tool. Error while adding delivery methods to data product: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_add_delivery_methods_to_data_product tool. Error while adding delivery methods to data product: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_add_delivery_methods_to_data_product tool. Error while adding delivery methods to data product: {str(e)}"
        )


@service_registry.tool(
    name="data_product_add_delivery_methods_to_data_product",
    description="""
    This tool adds delivery methods selected by user to a data product draft. DO NOT make up delivery methods, use the corresponding ID values for the delivery methods selected by the user.
    This is called after `find_delivery_methods_based_on_connection()` to add the delivery methods selected by the user to the data product draft.
    Example: 'Add delivery methods to data product draft' - Get the data product draft ID from context and the delivery method IDs from context matching the delivery methods selected by the user from the previous tool call.
    This receives the data product draft ID and the list of delivery method IDs selected by the user.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_add_delivery_methods_to_data_product(
    data_product_draft_id: str,
    delivery_method_ids: List[str]
) -> str:
    """Watsonx Orchestrator compatible version that expands AddDeliveryMethodsToDataProductRequest object into individual parameters."""

    request = AddDeliveryMethodsToDataProductRequest(
        data_product_draft_id=data_product_draft_id,
        delivery_method_ids=delivery_method_ids,
    )

    # Call the original add_delivery_methods_to_data_product function
    return await add_delivery_methods_to_data_product(request)
    