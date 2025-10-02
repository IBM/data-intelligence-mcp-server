from app.core.registry import service_registry
from app.services.data_product.models.find_delivery_methods_based_on_connection import (
    FindDeliveryMethodsBasedOnConnectionRequest,
    FindDeliveryMethodsBasedOnConnectionResponse,
    DeliveryMethod
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.services.data_product.utils.common_utils import add_catalog_id_suffix
from app.core.auth import get_access_token, get_dph_catalog_id_for_user
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_find_delivery_methods_based_on_connection",
    description="""
    This tool finds delivery methods available in the catalog based on the connection.
    This is called before `add_delivery_methods_to_data_product()` to find the delivery methods available for the given connection type.
    Example: 'Find delivery methods based on connection for data product draft'
    Prompt user to choose delivery methods from the list of available delivery methods.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@add_catalog_id_suffix()
@auto_context
async def find_delivery_methods_based_on_connection(
    request: FindDeliveryMethodsBasedOnConnectionRequest,
) -> FindDeliveryMethodsBasedOnConnectionResponse:
    LOGGER.info(
        f"In the data_product_find_delivery_methods_based_on_connection tool, finding delivery methods for data product draft id: {request.data_product_draft_id}"
    )
    token = await get_access_token()
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user(token)

    # step 1: get the connection ID from the contract terms of the data product draft
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }

    client = get_http_client()

    try:
        response = await client.get(
            url=f"{settings.di_service_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}",
            headers=headers,
        )
        contract_terms = response["contract_terms"]
        connection_id = None
        if contract_terms and len(contract_terms) > 0:
            connection_schema = contract_terms[0]["schema"]
            if connection_schema and len(connection_schema) > 0:
                connection_id = connection_schema[0]["connection_id"]

        if not connection_id:
            LOGGER.error(
                "Failed to run data_product_find_delivery_methods_based_on_connection tool. Connection detail is not found."
            )
            raise ServiceError(
                "Failed to run data_product_find_delivery_methods_based_on_connection tool. Connection detail is not found."
            )

    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details from draft: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details from draft: {str(e)}"
        )
    except ServiceError:
        raise
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details from draft: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details from draft: {str(e)}"
        )

    LOGGER.info(f"Connection ID found: {connection_id}")

    # step 2: get the datasource type from the connection
    try:
        response = await client.get(
            url=f"{settings.di_service_url}/v2/connections/{connection_id}?decrypt_secrets=true&catalog_id={DPH_CATALOG_ID}&userfs=false",
            headers=headers,
        )
        datasource_type = response["entity"]["datasource_type"]
    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting connection details: {str(e)}"
        )
    
    LOGGER.info(f"Datasource type found: {datasource_type}")

    # step 3: find delivery methods based on the datasource type
    json = {"query": "*:*", "sort": "asset.name", "include": "entity"}

    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v2/asset_types/ibm_data_product_delivery_method/search?catalog_id={DPH_CATALOG_ID}&hide_deprecated_response_fields=false",
            headers=headers,
            data=json,
        )
        available_delivery_methods = get_available_delivery_methods(response, datasource_type)
        
        LOGGER.info(f"Available delivery methods: {available_delivery_methods}")
        return FindDeliveryMethodsBasedOnConnectionResponse(
            delivery_methods=available_delivery_methods
        )

    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting delivery methods: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting delivery methods: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting delivery methods: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_find_delivery_methods_based_on_connection tool. Error while getting delivery methods: {str(e)}"
        )

def get_available_delivery_methods(response, datasource_type):
    # this function iterates and finds all available delivery methods for this connection.
    available_delivery_methods = []
    for result in response["results"]:
        ibm_data_product_delivery_method_entity = result["entity"][
            "ibm_data_product_delivery_method"
        ]
        if datasource_type in ibm_data_product_delivery_method_entity.get(
            "supported_data_sources", []
        ):
            available_delivery_methods.append(
                DeliveryMethod(
                    delivery_method_id=result["metadata"]["asset_id"],
                    delivery_method_name=result["metadata"]["name"],
                )
            )
    return available_delivery_methods

@service_registry.tool(
    name="data_product_find_delivery_methods_based_on_connection",
    description="""
    This tool finds delivery methods available in the catalog based on the connection.
    This is called before `add_delivery_methods_to_data_product()` to find the delivery methods available for the given connection type.
    Example: 'Find delivery methods based on connection for data product draft'
    Prompt user to choose delivery methods from the list of available delivery methods.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_find_delivery_methods_based_on_connection(
    data_product_draft_id: str
) -> FindDeliveryMethodsBasedOnConnectionResponse:
    """Watsonx Orchestrator compatible version that expands CreateDataProductFromCatalogRequest object into individual parameters."""

    request = FindDeliveryMethodsBasedOnConnectionRequest(
        data_product_draft_id=data_product_draft_id,
    )

    # Call the original create_data_product_from_catalog function
    return await find_delivery_methods_based_on_connection(request)
    