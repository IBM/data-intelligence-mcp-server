from app.core.registry import service_registry
from app.services.data_product.models.create_data_product_from_catalog import (
    CreateDataProductFromCatalogRequest,
    CreateDataProductFromCatalogResponse,
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
    name="data_product_create_data_product_from_catalog",
    description="""
    This tool creates a data product via add from catalog.
    Call this tool after calling `get_assets_from_catalog()`.
    This receives the asset ID selected by the user (from get_assets_from_catalog) and catalog id of the selected asset (from get_assets_from_catalog) along with other info from user.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def create_data_product_from_catalog(
    request: CreateDataProductFromCatalogRequest,
) -> CreateDataProductFromCatalogResponse:
    LOGGER.info(
        f"In the data_product_create_data_product_from_catalog tool, creating data product from catalog with name {request.name}, asset id {request.asset_id} and catalog id {request.catalog_id_of_asset_id}."
    )
    token = await get_access_token()
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user(token)

    target_asset_id = await create_assets_for_data_product_from_catalog(
        request.asset_id, request.catalog_id_of_asset_id, DPH_CATALOG_ID
    )

    # creating data product draft
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    json = {
        "drafts": [
            {
                "asset": {"container": {"id": DPH_CATALOG_ID}},
                "version": None,
                "data_product": None,
                "name": request.name,
                "description": None,
                "types": None,
                "dataview_enabled": False,
                "parts_out": [
                    {
                        "asset": {
                            "id": target_asset_id,
                            "container": {"id": DPH_CATALOG_ID},
                        }
                    }
                ],
            }
        ]
    }

    client = get_http_client()

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
        LOGGER.error(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while creating data product: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while creating data product: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while creating data product: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while creating data product: {str(e)}"
        )

    LOGGER.info(
        f"In the data_product_create_data_product_from_catalog tool, created data product draft - {data_product_draft_id}, contract terms id: {contract_terms_id}."
    )
    return CreateDataProductFromCatalogResponse(
        data_product_draft_id=data_product_draft_id,
        contract_terms_id=contract_terms_id,
        create_data_product_response=create_dp_response,
    )


@auto_context
async def create_assets_for_data_product_from_catalog(
    asset_id: str, catalog_id_of_asset_id: str, dph_catalog_id: str
) -> str:
    LOGGER.info(
        f"In the data_product_create_data_product_from_catalog tool, creating assets for data product from catalog with asset id {asset_id} and catalog id {catalog_id_of_asset_id}."
    )

    token = await get_access_token()

    # getting asset details
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }

    client = get_http_client()

    try:
        response = await client.get(
            url=f"{settings.di_service_url}/v2/assets/bulk?catalog_id={catalog_id_of_asset_id}&asset_ids={asset_id}&hide_deprecated_response_fields=false&include_relationship_count=true&include_source_columns=false",
            headers=headers,
        )
        asset_name = response["resources"][0]["asset"]["metadata"]["name"]
    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while getting asset details: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while getting asset details: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while getting asset details: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while getting asset details: {str(e)}"
        )

    LOGGER.info(
        f"In the data_product_create_data_product_from_catalog tool, asset name is {asset_name}."
    )

    # copying asset to dph catalog
    json = {
        "catalog_id": dph_catalog_id,
        "copy_configurations": [{"asset_id": asset_id}],
    }
    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v2/assets/bulk_copy?catalog_id={catalog_id_of_asset_id}",
            headers=headers,
            data=json,
        )
        _responses = response.get("responses", [])
        target_asset_id = None
        if _responses and len(_responses) > 0:
            _response = _responses[0]
            target_asset_id = _response.get("copied_assets", [{}])[0].get("target_asset_id")
        if not target_asset_id:
            LOGGER.error(f"Failed to run data_product_create_data_product_from_catalog tool. Could not copy assets due to target asset not found. {response}")
            raise ServiceError(
                f"Failed to run data_product_create_data_product_from_catalog tool. Could not copy assets due to target asset not found. {response}"
            )
    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while copying asset: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while copying asset: {str(e)}"
        )
    except ServiceError:
        raise
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while copying asset: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_create_data_product_from_catalog tool. Error while copying asset: {str(e)}"
        )

    LOGGER.info(
        f"In the data_product_create_data_product_from_catalog tool, target asset id is {target_asset_id}."
    )

    # creating asset revision
    json = {"commit_message": "copy asset to dpx"}

    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v2/assets/{target_asset_id}/revisions?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
            headers=headers,
            data=json,
        )
    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run create_data_product_from_catalog tool. Error while creating asset revision: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run create_data_product_from_catalog tool. Error while creating asset revision: {str(e)}"
        )

    # creating ibm_data_product_part asset and setting relationship
    await create_part_asset_and_set_relationship(
        asset_name, target_asset_id, dph_catalog_id, token
    )

    LOGGER.info(
        f"In the data_product_create_data_product_from_catalog tool, returning target asset id {target_asset_id}."
    )
    return target_asset_id


@service_registry.tool(
    name="data_product_create_data_product_from_catalog",
    description="""
    This tool creates a data product via add from catalog.
    Call this tool after calling `get_assets_from_catalog()`.
    This receives the asset ID selected by the user (from get_assets_from_catalog) and catalog id of the selected asset (from get_assets_from_catalog) along with other info from user.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_create_data_product_from_catalog(
    name: str,
    asset_id: str,
    catalog_id_of_asset_id: str
) -> CreateDataProductFromCatalogResponse:
    """Watsonx Orchestrator compatible version that expands CreateDataProductFromCatalogRequest object into individual parameters."""

    request = CreateDataProductFromCatalogRequest(
        name=name,
        asset_id=asset_id,
        catalog_id_of_asset_id=catalog_id_of_asset_id
    )

    # Call the original create_data_product_from_catalog function
    return await create_data_product_from_catalog(request)
