# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from datetime import datetime, timezone
from typing import Optional, Union, Literal

from app.core.registry import service_registry
from app.services.data_product.models.search_data_products import (
    SearchDataProductsRequest,
    SearchDataProductsResponse,
    DataProduct,
)
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user, get_data_product_url, calculate_date_one_year_before, validate_date_range
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context
TABLE_TITLE_DATA_PRODUCTS = "Data products"

def _format_data_products_for_table(data_products: list[dict]) -> list:
    data_products_table = []
    for item in data_products:
        metadata = item["metadata"]
        entity = item["entity"]

        item_row = {
            "Name": ui_message_context.create_markdown_link(
                get_data_product_url(item.get("artifact_id", ""), "available"),
                metadata.get("name", "")
            ),
            "Description": metadata.get("description", ""),
            "Created On": metadata.get("created_on", ""),
            "Version": entity.get("data_product_version", {}).get("version", ""),
        }
        data_products_table.append(item_row)
    return data_products_table


@service_registry.tool(
    name="data_product_search_data_products",
    description="""
    Search for data products in the Data Product Hub with flexible filtering by name, domain, state, and creation date.
    Please note that the date filter is only for creation date. If the query is about a different date not related to product creation, please do not provide creation dates.

    This tool searches the Data Product Hub catalog and returns matching data products. Multiple filters can be
    applied simultaneously to refine results (e.g., find products in a specific domain created within a date range).
    
    State Filter:
    - "draft": Returns only unpublished/draft data products
    - "published": Returns only published data products
    - None (default): Returns both draft and published data products
    
    Date filters are inclusive and can be used independently or together. When only one date is provided,
    it creates an open-ended filter (e.g., only created_date_after finds all products from that date onwards).

    CRITICAL - Natural Language Date Parsing (only for creation date filters):
    This tool ONLY accepts dates in YYYY-MM-DD format. When users provide natural language dates,
    convert them to YYYY-MM-DD before calling this tool using these rules:
    
    Temporal Logic (assume current date: February 11, 2026):
    1. NEVER return future dates - always use most recent PAST occurrence
    2. "today" → 2026-02-11, "yesterday" → 2026-02-10
    3. "last week" → created_date_after="2026-02-04", created_date_before="2026-02-11" (7 days)
    4. "past month" → created_date_after="2026-01-12", created_date_before="2026-02-11" (30 days)
    5. "this year" → created_date_after="2026-01-01", created_date_before="2026-02-11"
    6. Day only: "5th" → 2026-02-05 (current month if not passed), "15th" → 2026-01-15 (previous month if passed)
    7. Month+Day: "Dec 15th" → 2025-12-15 (December 2026 would be future, use 2025)
    8. Month only: "December" or "in December" → 2025-12-01 to 2025-12-31 (December 2026 would be future, use 2025)
    9. Month only (already passed this year): "January" → 2026-01-01 to 2026-01-31 (January 2026 is in the past)
    10. Explicit year: "March 5th 2025" → 2025-03-05
    11. Leap years: "Feb 29th" → use most recent leap year (2024-02-29)

    Examples:
        # Basic search
        search_data_products(product_search_query="Customer")
        search_data_products()  # All products (default "*")
        
        # Domain filtering
        search_data_products(domain="Finance")
        
        # State filtering
        search_data_products(state_filter="draft")  # Only drafts
        search_data_products(state_filter="published")  # Only published
        
        # Date filtering (ISO format)
        search_data_products(created_date_after="2026-01-01", created_date_before="2026-01-31")
        
        # Natural language conversions (convert before calling):
        # User: "products from yesterday" →
        search_data_products(created_date_after="2026-02-10", created_date_before="2026-02-10")
        
        # User: "products from last week" →
        search_data_products(created_date_after="2026-02-04", created_date_before="2026-02-11")
        
        # User: "products created in December" (Dec 2026 would be future, use Dec 2025) →
        search_data_products(created_date_after="2025-12-01", created_date_before="2025-12-31")
        
        # User: "products created in January" (Jan 2026 already passed, use Jan 2026) →
        search_data_products(created_date_after="2026-01-01", created_date_before="2026-01-31")
        
        # User: "products from 15th December" →
        search_data_products(created_date_after="2025-12-15", created_date_before="2025-12-15")
        
        # Combined filters
        search_data_products(product_search_query="Sales", domain="Finance", created_date_after="2026-01-01", state_filter="published")
    """,
    tags={"search", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def search_data_products(
    request: SearchDataProductsRequest,
) -> SearchDataProductsResponse:
    LOGGER.info(
        f"In the data_product_search_data_products tool, Searching data products with query '{request.product_search_query}', domain='{request.domain}', "
        f"state_filter='{request.state_filter}', created_date_after='{request.created_date_after}', created_date_before='{request.created_date_before}'"
    )
    DPH_CATALOG_ID = await get_dph_catalog_id_for_user()

    payload = get_dph_search_payload(
        product_search_query=request.product_search_query,
        dph_catalog_id=DPH_CATALOG_ID,
        domain=request.domain,
        created_date_after=request.created_date_after,
        created_date_before=request.created_date_before,
        state_filter=request.state_filter,
    )

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v3/search?role=viewer&auth_scope=ibm_data_product_catalog",
        json=payload,
        tool_name="data_product_search_data_products",
    )

    number_of_responses = response.get("size", len(response.get("rows", [])))
    if number_of_responses == 0:
        LOGGER.info(
            "In the data_product_search_data_products tool, no data products found."
        )
        return SearchDataProductsResponse(count=0, data_products=[])
    
    LOGGER.info(f"Found {number_of_responses} data products.")
    
    ui_message_context.add_table_ui_message(
        tool_name="search_data_products",
        formatted_data=_format_data_products_for_table(response.get("rows", [])),
        title=TABLE_TITLE_DATA_PRODUCTS
    )

    products = [_extract_product_info(row) for row in response.get("rows", [])]

    return SearchDataProductsResponse(count=number_of_responses, data_products=products)


def _extract_product_info(row: dict) -> DataProduct:
    """
    Extract and structure data product information from a search result row.
    
    Args:
        row: A single row from the search results containing product metadata and entity data
        
    Returns:
        DataProduct: Structured product information including ID, URL, metadata, and assets
    """
    metadata = row.get("metadata", {})
    entity = row.get("entity", {})
    data_product_version = entity.get("data_product_version", {})
    
    # Determine product state and construct appropriate URL
    state = data_product_version.get("state", "available")
    artifact_id = row.get("artifact_id", "")
    url = get_data_product_url(artifact_id, state)
    
    # Extract asset information with proper handling of missing data
    parts_out = data_product_version.get("parts_out", [])
    data_asset_items = [
        {
            "name": asset.get("name", ""),
            "description": asset.get("description", "")
        }
        for asset in parts_out
    ]
    
    return DataProduct(
        data_product_id=data_product_version.get("product_id", ""),
        data_product_version_id=artifact_id,
        url=url,
        name=metadata.get("name", ""),
        description=metadata.get("description", ""),
        created_on=metadata.get("created_on", ""),
        domain=data_product_version.get("domain_name", ""),
        state=state,
        version=data_product_version.get("version", ""),
        data_asset_items=data_asset_items,
        tags=metadata.get("tags", [])
    )

def get_dph_search_payload(product_search_query: str,
    dph_catalog_id: str,
    domain: Optional[str] = None,
    created_date_after: Optional[str] = None,
    created_date_before: Optional[str] = None,
    state_filter: Optional[str] = None,
) -> dict:
    should_query = []
    
    # Add name search query if not searching all products
    if product_search_query != "*":
        search_fields = [
            "metadata.name",  # NOSONAR
            "metadata.description",  # NOSONAR
        ]
        should_query.append({
            "gs_user_query": {
                "search_string": product_search_query,
                "search_fields": search_fields,
                "semantic_search_enabled": True,
                "nlq_analyzer_enabled": True,
                "keyword_search_enabled": True
            }
        })
    
    # Add domain filter if provided
    if domain:
        should_query.append({
            "match": {
                "entity.data_product_version.domain_name": {
                    "query": domain,
                    "operator": "and",
                    "fuzziness": "AUTO",
                    "prefix_length": 1,
                    "max_expansions": 50,
                }
            }
        })
    
    # If no specific queries, search all products
    if not should_query:
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
                    "search_string": product_search_query,
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
                            "search_string": product_search_query,
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
                            "search_string": product_search_query,
                            "nested": True,
                            "search_fields": parts_out_search_fields,
                            "nlq_analyzer_enabled": True,
                            "semantic_search_enabled": True,
                        }
                    },
                }
            },
        ]

    # Determine state filter values
    state_values = _get_state_filter_values(state_filter)

    payload = {
        "_source": [
            "artifact_id",
            "last_updated_at",
            "metadata.name",  # NOSONAR
            "metadata.description",  # NOSONAR
            "metadata.tags",  # NOSONAR
            "metadata.created_on",  # NOSONAR
            "entity.assets.catalog_id",  # NOSONAR
            "entity.data_product_version",
            "custom_attributes",
        ],
        "query": {
            "bool": {
                "should": should_query,
                "minimum_should_match": 1,
                "filter": [
                    {
                        "terms": {
                            "metadata.artifact_type": [  # NOSONAR
                                "ibm_data_product_version"
                            ]
                        }
                    },
                    {"terms": {"entity.data_product_version.state": state_values}},
                    {"terms": {"entity.assets.catalog_id": [dph_catalog_id]}},
                ],
            }
        },
        "size": 50,
        "aggregations": {
            "product_id": {
                "terms": {"field": "entity.data_product_version.product_id"}
            },
            "state": {"terms": {"field": "entity.data_product_version.state"}},
        },
    }
    
    # Add date range filter if date parameters provided
    _add_date_range_filter(payload, created_date_after, created_date_before)
    
    return payload


def _get_state_filter_values(state_filter: Optional[str]) -> list[str]:
    """
    Determine which state values to filter by based on the state_filter parameter.
    
    Args:
        state_filter: The state filter value ("draft", "published", or None)
        
    Returns:
        list[str]: List of state values to include in the search filter
    """
    if state_filter is None:
        # Default: search both draft and published products
        return ["available", "draft"]
    elif state_filter == "draft":
        return ["draft"]
    elif state_filter == "published":
        # "published" maps to "available" state in the backend
        return ["available"]
    else:
        # Fallback to default if invalid value provided
        LOGGER.warning(f"Invalid state_filter value '{state_filter}', defaulting to all states")
        return ["available", "draft"]

  
def _add_date_range_filter(
    payload: dict,
    created_date_after: Optional[str] = None,
    created_date_before: Optional[str] = None
) -> None:
    """Add date range filter to payload based on provided date parameters."""
    if not created_date_after and not created_date_before:
        return
    
    # Determine actual start and end dates
    if created_date_after and created_date_before:
        start_date = created_date_after
        end_date = created_date_before
    elif created_date_after:
        start_date = created_date_after
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        # Only end date - start is one year before
        assert created_date_before is not None
        end_date = created_date_before
        start_date = calculate_date_one_year_before(end_date)
    
    # Validate and convert to ISO format
    start_iso, end_iso = validate_date_range(start_date, end_date)
    
    # Add range filter to payload
    payload["query"]["bool"]["filter"].append({
        "range": {
            "metadata.created_on": {
                "gte": start_iso,
                "lte": end_iso
            }
        }
    })


@service_registry.tool(
    name="data_product_search_data_products",
    description="""
    Search for data products in the Data Product Hub with flexible filtering by name, domain, state, and creation date.
    Please note that the date filter is only for creation date. If the query is about a different date not related to product creation, please do not provide creation dates.

    This tool searches the Data Product Hub catalog and returns matching data products. Multiple filters can be
    applied simultaneously to refine results (e.g., find products in a specific domain created within a date range).
    
    State Filter:
    - "draft": Returns only unpublished/draft data products
    - "published": Returns only published data products
    - None (default): Returns both draft and published data products
    
    Date filters are inclusive and can be used independently or together. When only one date is provided,
    it creates an open-ended filter (e.g., only created_date_after finds all products from that date onwards).

    CRITICAL - Natural Language Date Parsing (only for creation date filters):
    This tool ONLY accepts dates in YYYY-MM-DD format. When users provide natural language dates,
    convert them to YYYY-MM-DD before calling this tool using these rules:
    
    Temporal Logic (assume current date: February 11, 2026):
    1. NEVER return future dates - always use most recent PAST occurrence
    2. "today" → 2026-02-11, "yesterday" → 2026-02-10
    3. "last week" → created_date_after="2026-02-04", created_date_before="2026-02-11" (7 days)
    4. "past month" → created_date_after="2026-01-12", created_date_before="2026-02-11" (30 days)
    5. "this year" → created_date_after="2026-01-01", created_date_before="2026-02-11"
    6. Day only: "5th" → 2026-02-05 (current month if not passed), "15th" → 2026-01-15 (previous month if passed)
    7. Month+Day: "Dec 15th" → 2025-12-15 (December 2026 would be future, use 2025)
    8. Month only: "December" or "in December" → 2025-12-01 to 2025-12-31 (December 2026 would be future, use 2025)
    9. Month only (already passed this year): "January" → 2026-01-01 to 2026-01-31 (January 2026 is in the past)
    10. Explicit year: "March 5th 2025" → 2025-03-05
    11. Leap years: "Feb 29th" → use most recent leap year (2024-02-29)

    Examples:
        # Basic search
        search_data_products(product_search_query="Customer")
        search_data_products()  # All products (default "*")
        
        # Domain filtering
        search_data_products(domain="Finance")
        
        # State filtering
        search_data_products(state_filter="draft")  # Only drafts
        search_data_products(state_filter="published")  # Only published
        
        # Date filtering (ISO format)
        search_data_products(created_date_after="2026-01-01", created_date_before="2026-01-31")
        
        # Natural language conversions (convert before calling):
        # User: "products from yesterday" →
        search_data_products(created_date_after="2026-02-10", created_date_before="2026-02-10")
        
        # User: "products from last week" →
        search_data_products(created_date_after="2026-02-04", created_date_before="2026-02-11")
        
        # User: "products created in December" (Dec 2026 would be future, use Dec 2025) →
        search_data_products(created_date_after="2025-12-01", created_date_before="2025-12-31")
        
        # User: "products created in January" (Jan 2026 already passed, use Jan 2026) →
        search_data_products(created_date_after="2026-01-01", created_date_before="2026-01-31")
        
        # User: "products from 15th December" →
        search_data_products(created_date_after="2025-12-15", created_date_before="2025-12-15")
        
        # Combined filters
        search_data_products(product_search_query="Sales", domain="Finance", created_date_after="2026-01-01", state_filter="published")

    Args:
        product_search_query (str): Search query for product name or description. Use "*" for all products.
        domain (Optional[str]): Business domain name to filter by. Must match an existing domain.
        state_filter (Optional[str]): Filter by product state ("draft", "published", or None for all).
        created_date_after (Optional[str]): Include products created on or after this date (YYYY-MM-DD format).
        created_date_before (Optional[str]): Include products created on or before this date (YYYY-MM-DD format).
""",
    tags={"search", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_search_data_products(
    product_search_query: Union[Literal["*"], str],
    domain: Optional[str] = None,
    state_filter: Optional[Union[Literal["draft"], Literal["published"]]] = None,
    created_date_after: Optional[str] = None,
    created_date_before: Optional[str] = None
) -> SearchDataProductsResponse:
    """Watsonx Orchestrator compatible version that expands SearchDataProductsRequest object into individual parameters."""

    request = SearchDataProductsRequest(
        product_search_query=product_search_query,
        domain=domain,
        state_filter=state_filter,
        created_date_after=created_date_after,
        created_date_before=created_date_before
    )

    # Call the original search_data_products function
    return await search_data_products(request)
