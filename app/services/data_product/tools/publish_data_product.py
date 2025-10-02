from app.core.registry import service_registry
from app.services.data_product.models.publish_data_product import (
    PublishDataProductRequest,
)
from app.services.data_product.utils.common_utils import add_catalog_id_suffix
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
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
) -> str:
    LOGGER.info(
        f"In the data_product_publish_data_product tool, publishing data product draft {request.data_product_draft_id}."
    )
    token = await get_access_token()

    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }

    client = get_http_client()

    try:
        await client.post(
            url=f"{settings.di_service_url}/data_product_exchange/v1/data_products/-/drafts/{request.data_product_draft_id}/publish",
            headers=headers,
        )
    except ExternalAPIError:
        raise
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_publish_data_product tool. Error while publishing data product draft: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_publish_data_product tool. Error while publishing data product draft: {str(e)}"
        )

    LOGGER.info(
        f"In the data_product_publish_data_product tool, data product draft {request.data_product_draft_id} published successfully."
    )
    return f"Data product draft {request.data_product_draft_id} published successfully."

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
@auto_context
async def wxo_publish_data_product(
    data_product_draft_id: str,
) -> str:
    """Watsonx Orchestrator compatible version that expands SearchAssetRequest object into individual parameters."""

    request = PublishDataProductRequest(
        data_product_draft_id=data_product_draft_id
    )

    # Call the original search_asset function
    return await publish_data_product(request)
