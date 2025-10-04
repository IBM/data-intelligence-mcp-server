from app.core.registry import service_registry
from app.services.data_product.models.search_data_products import (
    SearchDataProductsRequest,
    SearchDataProductsResponse,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token, get_dph_catalog_id_for_user
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="data_product_search_data_products",
    description="""
    This tool searches all data products to return data products that match the given search_query.
    Example: 'Find all data products that match the name Environment.'
    In this case, product_search_query is 'Environment', and this tool returns all data products that have Environment in their name.
    Example: 'Find all data products in the Audit domain.'
    In this case, product_search_query is '*', search_filter_type is 'Domain' and search_filter_value is 'Audit'.
    """,
    tags={"search", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def search_data_products(
    request: SearchDataProductsRequest,
) -> SearchDataProductsResponse:
    LOGGER.info(
        f"In the data_product_search_data_products tool, searching data products with query {request.product_search_query}, filter type {request.search_filter_type} and filter value {request.search_filter_value}."
    )
    token = await get_access_token()
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user(token)

    if request.search_filter_type.lower() == "domain":
        should_query = [
            {
                "match": {
                    "entity.data_product_version.domain_name": {
                        "query": request.search_filter_value,
                        "operator": "and",
                        "fuzziness": "AUTO",
                        "prefix_length": 1,
                        "max_expansions": 50,
                    }
                }
            }
        ]
        sort = []
    else:
        search_fields = ["metadata.name", "metadata.description", "metadata.tags"]
        parts_out_search_fields = [
            "entity.data_product_version.parts_out.name",
            "entity.data_product_version.parts_out.description",
            "entity.data_product_version.parts_out.column_names",
            "entity.data_product_version.parts_out.terms",
            "entity.data_product_version.parts_out.column_terms",
        ]
        should_query = [
            {
                "gs_user_query": {
                    "search_string": request.product_search_query,
                    "search_fields": search_fields,
                    "nlq_analyzer_enabled": True,
                    "semantic_search_enabled": True,
                }
            },
            {
                "nested": {
                    "path": "custom_attributes",
                    "query": {
                        "gs_user_query": {
                            "search_string": request.product_search_query,
                            "nested": True,
                        }
                    },
                }
            },
            {
                "nested": {
                    "path": "entity.data_product_version.parts_out",
                    "query": {
                        "gs_user_query": {
                            "search_string": request.product_search_query,
                            "nested": True,
                            "search_fields": parts_out_search_fields,
                            "nlq_analyzer_enabled": True,
                            "semantic_search_enabled": True,
                        }
                    },
                }
            },
        ]
        sort = [{"last_updated_at": {"order": "desc", "unmapped_type": "date"}}]

    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    json = {
        "_source": [
            "artifact_id",
            "last_updated_at",
            "metadata.name",
            "metadata.description",
            "metadata.tags",
            "metadata.created_on",
            "entity.assets.catalog_id",
            "entity.data_product_version",
            "custom_attributes",
        ],
        "query": {
            "bool": {
                "should": should_query,
                "minimum_should_match": 1,
                "filter": [
                    {"terms": {"metadata.artifact_type": ["ibm_data_product_version"]}},
                    {"terms": {"entity.data_product_version.state": ["available"]}},
                    {"terms": {"entity.assets.catalog_id": [DPH_CATALOG_ID]}},
                ],
            }
        },
        "size": 20,
        "sort": sort,
        "aggregations": {
            "product_id": {
                "terms": {"field": "entity.data_product_version.product_id"}
            },
            "state": {"terms": {"field": "entity.data_product_version.state"}},
        },
    }

    client = get_http_client()

    try:
        response = await client.post(
            url=f"{settings.di_service_url}/v3/search?role=viewer&auth_scope=ibm_data_product_catalog",
            headers=headers,
            data=json,
        )

        number_of_responses = response["size"]
        if number_of_responses == 0:
            LOGGER.info(
                "In the data_product_search_data_products tool, no data products found."
            )
            return SearchDataProductsResponse(count=0, data_products=[])
        LOGGER.info(f"Found {number_of_responses} data products.")
        products = []
        for row in response["rows"]:
            products.append(
                {
                    "name": row.get("metadata", {}).get("name", ""),
                    "description": row.get("metadata", {}).get("description", ""),
                    "created_on": row.get("metadata", {}).get("created_on", ""),
                    "domain": row.get("entity", {}).get("data_product_version", {}).get("domain_name", ""),
                    "data_asset_items": [
                        {"name": parts_out.get("name", ""), "description": parts_out.get("description", "")}
                        for parts_out in row.get("entity", {}).get("data_product_version", {}).get("parts_out", [])
                    ]
                }
            )
    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_product_search_data_products tool. Error while searching data products: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_product_search_data_products tool. Error while searching data products: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_product_search_data_products tool. Error while searching data products: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_product_search_data_products tool. Error while searching data products: {str(e)}"
        )

    return SearchDataProductsResponse(count=number_of_responses, data_products=products)


@service_registry.tool(
    name="data_product_search_data_products",
    description="""
    This tool searches all data products to return data products that match the given search_query.
    Example: 'Find all data products that match the name Environment.'
    In this case, product_search_query is 'Environment', and this tool returns all data products that have Environment in their name.
    Example: 'Find all data products in the Sustainability domain.'
    In this case, product_search_query is '*', search_filter_type is 'Domain' and search_filter_value is 'Sustainability'.
    Args:
    product_search_query: str = The search query to search for data products. If the user wants to search for data products with a specific name, this is the name to search for. If user wants to search for all data products, this value should be "*".
    search_filter_type: str = Specify what to filter by. It can be one of the following: None, Domain. If the user wants to filter by domain, then this value should be Domain otherwise None.
    search_filter_value: str = The value to filter by. For example, if search_filter_type is Domain, then this is the domain name to filter by.
    """,
    tags={"search", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_search_data_products(
    product_search_query: str, search_filter_type: str, search_filter_value: str
) -> SearchDataProductsResponse:
    """Watsonx Orchestrator compatible version that expands SearchDataProductsRequest object into individual parameters."""

    request = SearchDataProductsRequest(
        product_search_query=product_search_query,
        search_filter_type=search_filter_type,
        search_filter_value=search_filter_value,
    )

    # Call the original search_data_products function
    return await search_data_products(request)
