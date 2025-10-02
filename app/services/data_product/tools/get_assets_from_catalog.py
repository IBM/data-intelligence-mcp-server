from app.core.registry import service_registry
from app.services.data_product.models.get_assets_from_catalog import (
    AssetFromCatalog,
    GetAssetsFromCatalogResponse,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token, get_bss_account_id
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_get_assets_from_catalog",
    description="""
    This tool gets assets from catalog and is called as the first step to create a data product from catalog.
    Example: 'Create a data product with <name>, <domain>,..... from catalog' - will call this tool first before calling `create_data_product_from_catalog()`
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def get_assets_from_catalog() -> GetAssetsFromCatalogResponse:
    # step 1: get assets from catalog
    LOGGER.info("In the data_product_get_assets_from_catalog tool, getting assets from catalog.")

    token = await get_access_token()
    account_id = await get_bss_account_id()

    LOGGER.info(f"In the data_product_get_assets_from_catalog tool, account id: {account_id}")

    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    json = {
        "query": {
            "bool": {
                "must": [
                    {
                        "gs_user_query": {
                            "search_string": "*",
                            "search_fields": [
                                "metadata.name",
                                "metadata.description",
                                "metadata.tags",
                            ],
                            "nlq_analyzer_enabled": True,
                            "semantic_expansion_enabled": True,
                        }
                    },
                    {"term": {"metadata.artifact_type": "data_asset"}},
                    {"exists": {"field": "entity.assets.catalog_id"}},
                ],
                "must_not": [
                    {"exists": {"field": "entity.assets.project_id"}},
                    {"term": {"entity.assets.rov.privacy": "private"}},
                ],
                "filter": [
                    {"terms": {"metadata.artifact_type": ["data_asset"]}},
                    {"terms": {"tenant_id": [account_id]}},
                ],
            }
        },
        "size": 100,
        "aggregations": {
            "owners": {"terms": {"field": "entity.assets.rov.owners"}},
            "catalogs": {"terms": {"field": "entity.assets.catalog_id"}},
        },
    }

    client = get_http_client()

    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v3/search", headers=headers, data=json
        )
        number_of_responses = response["size"]
        if number_of_responses == 0:
            LOGGER.info("In the data_product_get_assets_from_catalog tool, no assets found in the catalog.")
            return GetAssetsFromCatalogResponse(
                message="There are 0 assets found in the catalog.", assets=[]
            )
        assets = []
        for row in response["rows"]:
            assets.append(
                AssetFromCatalog(
                    name=row["metadata"]["name"],
                    asset_id=row["artifact_id"],
                    catalog_id_of_asset_id=row["entity"]["assets"]["catalog_id"],
                )
            )

        LOGGER.info(f"In the data_product_get_assets_from_catalog tool, assets found in the catalog: {assets}.")
        return GetAssetsFromCatalogResponse(
            message=f"There are {number_of_responses} assets found in the catalog.",
            assets=assets,
        )
    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_get_assets_from_catalog tool. Error while fetching assets from catalog: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_get_assets_from_catalog tool. Error while fetching assets from catalog: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_get_assets_from_catalog tool. Error while fetching assets from catalog: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_get_assets_from_catalog tool. Error while fetching assets from catalog: {str(e)}"
        )


@service_registry.tool(
    name="data_product_get_assets_from_catalog",
    description="""
    This tool gets assets from catalog and is called as the first step to create a data product from catalog.
    Example: 'Create a data product with <name>, <domain>,..... from catalog' - will call this tool first before calling `create_data_product_from_catalog()`
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_get_assets_from_catalog() -> GetAssetsFromCatalogResponse:

    # Call the original get_assets_from_catalog function
    return await get_assets_from_catalog()
    
