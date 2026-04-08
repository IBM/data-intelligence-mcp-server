# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional, Dict, Any, List, cast
import re

from app.core.registry import service_registry
from app.services.data_product.models.get_data_product_details import (
    GetDataProductDetailsRequest,
    GetDataProductDetailsResponse,
    DataProductDetails,
    PartOut,
    ColumnInfo,
    SubscribedAsset,
)
from app.services.data_product.utils.common_utils import get_data_product_url, get_dph_catalog_id_for_user
from app.services.data_product.constants import (
    ASSET_TYPE_IBM_URL_DEFINITION,
    FIELD_ASSET,
    FIELD_TYPE,
    FIELD_PROPERTIES,
    FIELD_OUTPUT,
    FIELD_OPEN_URL,
    FIELD_VALUE,
    FIELD_ASSETS_OUT,
    FIELD_ASSET_ID,
    FIELD_URL,
    FIELD_FLIGHT_ASSET_ID,
    FIELD_FLIGHT_CLIENT_URL,
    FIELD_COPY_TEXT,
    FIELD_SELECTED_DATA_CLASS,
    FIELD_NAME,
    FIELD_CONFIDENCE,
    FIELD_COLUMN_INFO,
    FIELD_DATA_CLASS_NAME,
    FIELD_DATA_CLASS_CONFIDENCE,
    FIELD_SEMANTIC_NAME,
    FIELD_SEMANTIC_NAME_CONFIDENCE,
    FIELD_SEMANTIC_NAME_STATUS,
    FIELD_STATUS,
    FIELD_SEMANTIC_DESCRIPTION,
    FIELD_DESCRIPTION,
    FIELD_COLUMN_DESCRIPTION,
    FIELD_SEMANTIC_DESCRIPTION_CONFIDENCE,
    FIELD_SEMANTIC_DESCRIPTION_STATUS,
    FIELD_DATA_TYPE,
    FIELD_LENGTH,
    FIELD_NULLABLE,
    FIELD_NATIVE_TYPE,
    FIELD_IS_PRIMARY_KEY,
    FIELD_METADATA,
    FIELD_ENTITY,
    FIELD_DATA_ASSET,
    FIELD_COLUMNS,
    FIELD_KEY_ANALYSES,
    FIELD_PRIMARY_KEYS,
    FIELD_ASSET_LISTS,
    FIELD_ID,
    FIELD_ITEMS,
    FIELD_STATE,
    FIELD_VERSION,
    FIELD_PARTS_OUT,
    FIELD_CATALOG_ID,
    STATE_SUCCEEDED,
)
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER, auto_context
from app.shared.exceptions.base import ServiceError


def _extract_flight_client_url_from_copy_text(copy_text_list: List[Dict[str, Any]]) -> Optional[str]:
    """
    Extract flight_client_url from copy_text array.
    
    Searches through copy_text entries for a flight_client_url value.
    The flight_client_url can appear in the text field of any copy_text entry.
    
    Args:
        copy_text_list: List of copy_text dictionaries from properties.output
        
    Returns:
        The flight_client_url value if found, None otherwise
    """
    for copy_text_entry in copy_text_list:
        text = copy_text_entry.get("text", "")
        # Look for flight_client_url in the text using regex
        # Pattern matches: "flight_client_url": "value" or flight_client_url = "value"
        match = re.search(r'["\']?flight_client_url["\']?\s*[:=]\s*["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
    return None


def _extract_url_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract URL value from an ibm_url_definition asset.
    
    Args:
        item: Subscription item dictionary
        
    Returns:
        Dict with 'url' key if found, empty dict otherwise
    """
    url_value = (
        item.get(FIELD_PROPERTIES, {})
        .get(FIELD_OUTPUT, {})
        .get(FIELD_OPEN_URL, [{}])[0]
        .get(FIELD_VALUE)
    )
    if url_value:
        return {FIELD_URL: url_value}
    
    LOGGER.warning(f"URL value not found for {ASSET_TYPE_IBM_URL_DEFINITION} asset")
    return {}


def _extract_data_asset_values(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract flight_asset_id and optionally flight_client_url from a data asset.
    
    Args:
        item: Subscription item dictionary
        
    Returns:
        Dict with 'flight_asset_id' and optionally 'flight_client_url', or empty dict if not found
    """
    flight_asset_id = (
        item.get(FIELD_PROPERTIES, {})
        .get(FIELD_ASSETS_OUT, [{}])[0]
        .get(FIELD_ASSET_ID)
    )
    
    if not flight_asset_id:
        asset_type = item.get(FIELD_ASSET, {}).get(FIELD_TYPE)
        LOGGER.warning(f"flight_asset_id not found for {asset_type} asset")
        return {}
    
    result = {FIELD_FLIGHT_ASSET_ID: flight_asset_id}
    
    # Try to extract flight_client_url from copy_text if present
    copy_text_list = (
        item.get(FIELD_PROPERTIES, {})
        .get(FIELD_OUTPUT, {})
        .get(FIELD_COPY_TEXT, [])
    )
    if copy_text_list:
        flight_client_url = _extract_flight_client_url_from_copy_text(copy_text_list)
        if flight_client_url:
            result[FIELD_FLIGHT_CLIENT_URL] = flight_client_url
    
    return result


def _extract_asset_value_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the appropriate value from a subscription item based on asset type.
    
    For data_asset types, extracts the flight_asset_id and flight_client_url (if present).
    For ibm_url_definition types, extracts the URL.
    
    Args:
        item: Subscription item dictionary containing asset information
        
    Returns:
        Dict containing 'flight_asset_id' and optionally 'flight_client_url' for data assets,
        or 'url' for URL definitions, or an empty dict if extraction fails
    """
    asset_type = item.get(FIELD_ASSET, {}).get(FIELD_TYPE)
    
    try:
        if asset_type == ASSET_TYPE_IBM_URL_DEFINITION:
            return _extract_url_from_item(item)
        else:  # asset_type == "data_asset" or other types
            return _extract_data_asset_values(item)
    except (KeyError, IndexError, TypeError) as e:
        LOGGER.warning(f"Failed to extract asset value from item: {e}. Item structure may be unexpected.")
        return {}


def _add_metadata_to_column_info(col_info: Dict[str, Any], extracted_info: Dict[str, Any]) -> None:
    """
    Add metadata (data classification, semantic naming, descriptions) to column info.
    
    Args:
        col_info: Column info dictionary to update
        extracted_info: Extracted metadata from column_info_dict
    """
    # Extract data classification
    selected_data_class = extracted_info.get(FIELD_SELECTED_DATA_CLASS, {})
    if selected_data_class:
        col_info[FIELD_COLUMN_INFO] = {
            FIELD_DATA_CLASS_NAME: selected_data_class.get(FIELD_NAME),
            FIELD_DATA_CLASS_CONFIDENCE: selected_data_class.get(FIELD_CONFIDENCE)
        }
    
    # Extract semantic naming
    semantic_name = extracted_info.get(FIELD_SEMANTIC_NAME, {})
    if semantic_name:
        semantic_data = {
            FIELD_SEMANTIC_NAME: semantic_name.get(FIELD_NAME),
            FIELD_SEMANTIC_NAME_CONFIDENCE: semantic_name.get(FIELD_CONFIDENCE),
            FIELD_SEMANTIC_NAME_STATUS: semantic_name.get(FIELD_STATUS)
        }
        if col_info.get(FIELD_COLUMN_INFO):
            col_info[FIELD_COLUMN_INFO].update(semantic_data)
        else:
            col_info[FIELD_COLUMN_INFO] = semantic_data
    
    # Extract descriptions
    semantic_description = extracted_info.get(FIELD_SEMANTIC_DESCRIPTION, {})
    if semantic_description:
        description_data = {
            FIELD_COLUMN_DESCRIPTION: extracted_info.get(FIELD_COLUMN_DESCRIPTION),
            FIELD_SEMANTIC_DESCRIPTION: semantic_description.get(FIELD_DESCRIPTION),
            FIELD_SEMANTIC_DESCRIPTION_CONFIDENCE: semantic_description.get(FIELD_CONFIDENCE),
            FIELD_SEMANTIC_DESCRIPTION_STATUS: semantic_description.get(FIELD_STATUS)
        }
        if col_info.get(FIELD_COLUMN_INFO):
            col_info[FIELD_COLUMN_INFO].update(description_data)
        else:
            col_info[FIELD_COLUMN_INFO] = description_data


def _extract_column_info_for_columns(
    columns: List[Dict[str, Any]],
    column_info_dict: Dict[str, Any],
    primary_keys: List[List[str]]
) -> List[Dict[str, Any]]:
    """
    Enrich columns with column_info metadata and primary key flags.
    
    Args:
        columns: List of column dictionaries from data_asset
        column_info_dict: Dictionary mapping column names to their metadata
        primary_keys: List of primary key combinations
        
    Returns:
        List of enriched column dictionaries
    """
    # Create a set of all primary key column names for quick lookup
    pk_column_names = set()
    for pk_group in primary_keys:
        pk_column_names.update(pk_group)
    
    enriched_columns = []
    for column in columns:
        column_name = column.get(FIELD_NAME)
        
        # Extract type - it can be either a string or a dict with nested 'type' field
        column_type = column.get(FIELD_TYPE)
        if isinstance(column_type, dict):
            # If type is a dict, extract the nested 'type' field
            data_type = column_type.get(FIELD_TYPE)
            # Also extract native_type from the dict if not at top level
            native_type = column_type.get(FIELD_NATIVE_TYPE) or column.get(FIELD_NATIVE_TYPE)
        else:
            # If type is already a string, use it directly
            data_type = column_type
            native_type = column.get(FIELD_NATIVE_TYPE)
        
        # Create enriched column info
        col_info = {
            FIELD_NAME: column_name,
            FIELD_DATA_TYPE: data_type,
            FIELD_LENGTH: column.get(FIELD_LENGTH),
            FIELD_NULLABLE: column.get(FIELD_NULLABLE),
            FIELD_NATIVE_TYPE: native_type,
            FIELD_IS_PRIMARY_KEY: column_name in pk_column_names
        }
        
        # Add column_info metadata if available
        if column_name in column_info_dict:
            _add_metadata_to_column_info(col_info, column_info_dict[column_name])
        
        enriched_columns.append(col_info)
    
    return enriched_columns


def _build_asset_details_map(parts_out_with_details: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """
    Build a lookup map of asset IDs to their metadata (name and description).
    
    This optimization avoids redundant API calls by reusing asset details that were
    already fetched during the main data product details retrieval.
    
    Args:
        parts_out_with_details: List of enriched parts from get_data_product_details,
                               each containing asset metadata
    
    Returns:
        Dictionary mapping asset_id -> {name, description}
        Example: {"asset-123": {"name": "Customer Data", "description": "..."}}
    """
    asset_details_map = {}
    for part in parts_out_with_details:
        asset_id = part.get(FIELD_ASSET, {}).get(FIELD_ID)
        if asset_id:
            asset_details_map[asset_id] = {
                FIELD_NAME: part.get(FIELD_NAME),
                FIELD_DESCRIPTION: part.get(FIELD_DESCRIPTION)
            }
    return asset_details_map


def _build_subscribed_asset_from_item(
    item: Dict[str, Any],
    asset_name: str
) -> SubscribedAsset:
    """
    Build a SubscribedAsset object from a subscription item.
    
    Extracts the asset type-specific value (flight_asset_id for data assets,
    url for URL definitions) and combines it with the asset name to create
    a complete subscription record.
    
    Args:
        item: Subscription item from the asset_lists API response
        asset_name: Display name of the asset
    
    Returns:
        SubscribedAsset with name and either flight_asset_id or url populated
    """
    # Extract flight_asset_id (for data assets) or url (for URL definitions)
    asset_value = _extract_asset_value_from_item(item)
    
    # Combine name with the extracted value to create the subscription record
    return SubscribedAsset(
        name=asset_name,
        **asset_value
    )


async def _build_subscribed_assets_from_cache(
    items: List[Dict[str, Any]],
    asset_details_map: Dict[str, Dict[str, str]]
) -> List[SubscribedAsset]:
    """
    Build subscription assets using cached asset details (optimization path).
    
    This method uses pre-fetched asset metadata to avoid making additional API calls.
    It's more efficient when we already have the asset details from a previous operation.
    
    Args:
        items: List of subscription items from the asset_lists API
        asset_details_map: Pre-built mapping of asset_id to metadata
    
    Returns:
        List of SubscribedAsset objects with complete metadata
    """
    subscribed_assets = []
    
    for item in items:
        # Get the asset ID from the subscription item
        data_asset_id = item.get(FIELD_ASSET, {}).get(FIELD_ID)
        
        # Look up the asset name from our cached details
        # Use "Unknown" as fallback if asset not found in cache
        asset_details = asset_details_map.get(data_asset_id, {})
        data_asset_name = asset_details.get(FIELD_NAME, "Unknown")
        
        # Build and add the subscription record
        subscribed_asset = _build_subscribed_asset_from_item(item, data_asset_name)
        subscribed_assets.append(subscribed_asset)
    
    return subscribed_assets


async def _build_subscribed_assets_from_api(
    items: List[Dict[str, Any]],
    catalog_id: str
) -> List[SubscribedAsset]:
    """
    Build subscription assets by fetching asset details via API (fallback path).
    
    This method makes individual API calls to fetch asset metadata for each subscription.
    It's used when we don't have pre-fetched asset details available.
    
    Args:
        items: List of subscription items from the asset_lists API
        catalog_id: Catalog ID for API requests
    
    Returns:
        List of SubscribedAsset objects with complete metadata
    """
    subscribed_assets = []
    params = {FIELD_CATALOG_ID: catalog_id}
    
    for item in items:
        # Extract the asset ID from the subscription item
        data_asset_id = item.get(FIELD_ASSET, {}).get(FIELD_ID)
        
        # Fetch the full asset metadata via API
        data_asset_url = f"{tool_helper_service.base_url}/v2/assets/{data_asset_id}"
        data_asset_response = await tool_helper_service.execute_get_request(
            url=data_asset_url,
            params=params,
            tool_name="data_product_get_data_product_details"
        )
        
        # Extract the asset name from the API response
        data_asset_name = data_asset_response.get(FIELD_METADATA, {}).get(FIELD_NAME)
        
        # Build and add the subscription record
        subscribed_asset = _build_subscribed_asset_from_item(item, data_asset_name)
        subscribed_assets.append(subscribed_asset)
    
    return subscribed_assets


async def _get_data_product_subscription_details(
    data_product_id: str,
    catalog_id: str,
    parts_out_with_details: Optional[List[Dict[str, Any]]] = None
) -> List[SubscribedAsset]:
    """
    Retrieve subscription details for a data product.
    
    This function performs a two-step process:
    1. Finds active subscriptions for the data product
    2. Retrieves detailed information about each subscribed asset
    
    The function supports two modes:
    - Optimized: Uses pre-fetched asset details to avoid redundant API calls
    - Standard: Fetches asset details via individual API calls
    
    Args:
        data_product_id: The ID of the data product to get subscriptions for
        catalog_id: The catalog ID where the data product resides
        parts_out_with_details: Optional pre-fetched asset details from get_data_product_details.
                               When provided, enables the optimized path that reuses existing data.
    
    Returns:
        List of SubscribedAsset objects, each containing:
        - name: Display name of the subscribed asset
        - flight_asset_id: ID for data extraction (for data_asset types)
        - url: Direct access URL (for ibm_url_definition types)
    """
    LOGGER.info(f"Retrieving subscription details for data product {data_product_id}")
    
    try:
        # Step 1: Find the subscription list for this data product
        # Query for succeeded subscriptions matching the data product ID
        subscriptions_url = (
            f"{tool_helper_service.base_url}/v2/asset_lists?limit=1&&sort=-last_updated_at&query=asset.id==\"{data_product_id}\"&&state==\"{STATE_SUCCEEDED}\""
        )
        LOGGER.info(f"Searching for subscriptions: {subscriptions_url}")
        subscriptions_response = await tool_helper_service.execute_get_request(
            url=subscriptions_url,
            tool_name="data_product_get_data_product_details"
        )
        LOGGER.info(f"Got subscriptions response: {subscriptions_response}")
        
        # Check if any subscriptions exist
        subscriptions = subscriptions_response.get(FIELD_ASSET_LISTS, [])
        if not subscriptions:
            LOGGER.info("No subscriptions found for this data product")
            return []
        
        # Extract the subscription list ID
        data_product_subscription_id = subscriptions[0].get(FIELD_ID)
        LOGGER.info(f"Extracted subscription id: {data_product_subscription_id}")

        # Step 2: Get the individual items (assets) in the subscription list
        subscription_url = (
            f"{tool_helper_service.base_url}/v2/asset_lists/"
            f"{data_product_subscription_id}/items"
        )
        subscription_response = await tool_helper_service.execute_get_request(
            url=subscription_url,
            tool_name="data_product_get_data_product_details"
        )
        items = subscription_response.get(FIELD_ITEMS, [])

        # Step 3: Build subscription asset records
        # Choose optimized or standard path based on available data
        if parts_out_with_details:
            # Optimized path: Use cached asset details to avoid API calls
            LOGGER.info("Using pre-fetched parts_out details to build subscription details")
            asset_details_map = _build_asset_details_map(parts_out_with_details)
            subscribed_product_assets = await _build_subscribed_assets_from_cache(
                items, asset_details_map
            )
        else:
            # Standard path: Fetch asset details via individual API calls
            LOGGER.info("Fetching asset details via API calls")
            subscribed_product_assets = await _build_subscribed_assets_from_api(
                items, catalog_id
            )

        LOGGER.info(f"Retrieved {len(subscribed_product_assets)} subscription(s)")
        return subscribed_product_assets
        
    except Exception as e:
        LOGGER.warning(f"Could not fetch subscription details: {e}")
        return []


async def _search_data_product_by_name(data_product_name: str, catalog_id: str) -> str:
    """
    Search for a data product by name and return its ID.
    
    Args:
        data_product_name: Name of the data product to search for
        catalog_id: Catalog ID for the search
        
    Returns:
        str: Data product ID
        
    Raises:
        ServiceError: If data product is not found
    """
    LOGGER.info(f"Searching for data product by name: {data_product_name}")
    data_product_details_url = (
        f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_version/search?catalog_id={catalog_id}"
    )
    search_body = {
        "query": f"asset.name: LIKE \"{data_product_name}\" AND ibm_data_product_version.state:\"available\""
    }
    data_product_details_response = await tool_helper_service.execute_post_request(
        url=data_product_details_url,
        json=search_body,
        tool_name="data_product_get_data_product_details"
    )
    LOGGER.info(f"Got product response: {data_product_details_response}")
    
    # Extract search results, defaulting to empty list if not present
    results = data_product_details_response.get("results", [])
    
    # Check if any results were found (empty list evaluates to False)
    if not results:
        raise ServiceError(
            f"Data product '{data_product_name}' could not be found. "
            f"Please try again with a different name. "
            f"If necessary, use the MCP tool data_product_search_data_products to perform a search with a query."
        )
    
    # Extract the data product ID from the first result
    first_result = results[0]
    metadata = first_result.get(FIELD_METADATA)
    
    # Validate that metadata exists in the response
    if not metadata:
        raise ServiceError(
            f"Invalid API response for data product '{data_product_name}': missing metadata. "
            f"The search returned results but the response structure is unexpected."
        )
    
    # Extract and validate the asset_id
    data_product_id = metadata.get(FIELD_ASSET_ID)
    if not data_product_id:
        raise ServiceError(
            f"Invalid API response for data product '{data_product_name}': missing asset_id in metadata. "
            f"The search returned results but the asset_id could not be extracted."
        )
    
    LOGGER.info(f"Got product id: {data_product_id}")
    return data_product_id


async def _process_part_asset(part: Dict[str, Any], params: Dict[str, str]) -> Dict[str, Any]:
    """
    Process a single part asset to enrich it with detailed metadata.
    
    Args:
        part: Part asset dictionary from release response
        params: Query parameters including catalog_id
        
    Returns:
        Dict containing enriched part with name, description, asset, columns, and primary_keys
    """
    # Extract asset IDs from the part asset
    data_asset_id = part.get(FIELD_ASSET, {}).get(FIELD_ID)

    # Fetch detailed metadata for the data asset
    data_asset_url = f"{tool_helper_service.base_url}/v2/assets/{data_asset_id}"
    data_asset_response = await tool_helper_service.execute_get_request(
        url=data_asset_url,
        params=params,
        tool_name="data_product_get_data_product_details"
    )

    # Extract the asset name and description from metadata
    data_asset_name = data_asset_response.get(FIELD_METADATA, {}).get(FIELD_NAME)
    data_asset_desc = data_asset_response.get(FIELD_METADATA, {}).get(FIELD_DESCRIPTION)
    
    # Extract columns from entity.data_asset
    data_asset_columns = data_asset_response.get(FIELD_ENTITY, {}).get(FIELD_DATA_ASSET, {}).get(FIELD_COLUMNS, [])
    
    # Extract column_info dictionary from entity
    column_info_dict = data_asset_response.get(FIELD_ENTITY, {}).get(FIELD_COLUMN_INFO, {})
    
    # Extract primary_keys from entity.key_analyses
    primary_keys = data_asset_response.get(FIELD_ENTITY, {}).get(FIELD_KEY_ANALYSES, {}).get(FIELD_PRIMARY_KEYS, [])
    
    # Enrich columns with column_info metadata and primary key flags
    # Always call this function to handle type extraction (including nested type structures)
    data_asset_columns = _extract_column_info_for_columns(
        data_asset_columns,
        column_info_dict,
        primary_keys
    )
    if column_info_dict or primary_keys:
        LOGGER.debug(f"Enriched {len(data_asset_columns)} columns with column_info metadata and primary key information")

    # Create enriched part
    enriched_part = {
        FIELD_NAME: data_asset_name,
        FIELD_DESCRIPTION: data_asset_desc,
        FIELD_ASSET: part.get(FIELD_ASSET),
        FIELD_COLUMNS: data_asset_columns,
    }
    if primary_keys:
        enriched_part[FIELD_PRIMARY_KEYS] = primary_keys
        LOGGER.debug(f"Added primary_keys to part: {primary_keys}")
    
    return enriched_part


@service_registry.tool(
    name="data_product_get_data_product_details",
    description="""
    Retrieve comprehensive information about IBM Cloud Data Product Hub data products.
    
    This tool provides detailed metadata about data products including:
    
    **get_data_product_details**: Retrieves complete metadata including:
       - Release information (version, state, description)
       - Parts/assets with names, descriptions, and enriched column schemas
       - Primary key information (both at part level and column level)
       - Subscription details (only successful subscriptions with 'succeeded' state - failed deliveries are excluded)
    
    **Column Schema Details** - Each column includes:
       - Basic schema: name, data_type, length, nullable, native_type
       - Primary key flag: is_primary_key (true if column is part of primary key)
       - Column metadata (column_info object):
         * Data classification: data_class_name, data_class_confidence
         * Semantic naming: semantic_name, semantic_name_confidence, semantic_name_status
         * Descriptions: column_description, semantic_description with confidence and status
    
    **Primary Keys**:
       - Part-level: primary_keys array shows all primary key combinations (supports composite keys)
       - Column-level: is_primary_key flag on individual columns for easy identification
    
    **Required Input**: Provide either data_product_id OR data_product_name.
    
    **Subscription Details** (only successful subscriptions returned):
       - Only includes subscriptions with 'succeeded' state - failed subscription deliveries are not returned
       - For data_asset types: Returns 'flight_asset_id' and optionally 'flight_client_url' for data extraction
       - For ibm_url_definition types: Returns 'url' for accessing external resources
       - Each subscribed asset includes 'name' and either 'flight_asset_id' or 'url'
       - If no successful subscriptions exist, the list will be empty
    
    **Usage Tips**:
       - Rich column metadata helps understand data semantics and quality before querying
       - Primary key information is essential for joins and data relationships
       - Data classification and confidence scores indicate data sensitivity and reliability
       - flight_asset_id from subscription details enables data extraction via Flight API
       - url from subscription details provides direct access to external data sources
    """,
    tags={"read", "data_product"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def get_data_product_details(
    request: GetDataProductDetailsRequest,
) -> GetDataProductDetailsResponse:
    """
    Retrieve comprehensive details about a data product.
    
    Fetches complete metadata including release information, parts/assets,
    column schemas, and subscription details.
    """
    LOGGER.info(
        f"In data_product_get_data_product_details tool, retrieving details for "
        f"data_product_id={request.data_product_id}, data_product_name={request.data_product_name}"
    )
    
    # Validate that at least one identifier is provided
    if not request.data_product_id and not request.data_product_name:
        raise ServiceError(
            "Missing required data product id or data product name. "
            "Please supply either the id or name of a data product for which to get details."
        )
    
    catalog_id = await get_dph_catalog_id_for_user()
    
    try:
        # Prepare query parameters
        params = {FIELD_CATALOG_ID: catalog_id}
        
        # If name is provided but not ID, search for the data product
        data_product_id = request.data_product_id
        if request.data_product_name and not data_product_id:
            data_product_id = await _search_data_product_by_name(request.data_product_name, catalog_id)

        # Get Data Product Release details
        LOGGER.info(f"Fetching release details for {data_product_id}")
        
        # Defensive code: only append @catalog_id if not already present
        # The data_product_id should ideally be just a GUID, but sometimes it may already include @catalog_id
        if data_product_id and "@" not in data_product_id:
            data_product_id_with_catalog = f"{data_product_id}@{catalog_id}"
        else:
            data_product_id_with_catalog = data_product_id
            
        release_url = (
            f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/releases/{data_product_id_with_catalog}"
        )
        release_response = await tool_helper_service.execute_get_request(
            url=release_url,
            tool_name="data_product_get_data_product_details"
        )
        LOGGER.info(f"Got release response: {release_response}")
        
        parts_out = release_response.get(FIELD_PARTS_OUT, [])

        # Process each part asset
        LOGGER.info(f"Processing {len(parts_out)} asset(s)")
        enriched_parts = []
        for part in parts_out:
            enriched_part = await _process_part_asset(part, params)
            enriched_parts.append(enriched_part)

        # Get subscription details and add to the response
        # Pass enriched_parts to avoid redundant API calls since we already have the asset details
        # At this point data_product_id is guaranteed to be a non-empty string:
        # - Either provided directly via request.data_product_id
        # - Or obtained via _search_data_product_by_name() which always returns a string or raises an error
        # Use cast() to inform the type checker without runtime overhead
        subscription_details = await _get_data_product_subscription_details(
            data_product_id=cast(str, data_product_id),
            catalog_id=catalog_id,
            parts_out_with_details=enriched_parts
        )

        # Create response
        data_product_details = DataProductDetails(
            id=release_response.get(FIELD_ID),
            version=release_response.get(FIELD_VERSION),
            url=get_data_product_url(release_response.get(FIELD_ASSET, {}).get(FIELD_ID, ""), "available"),
            state=release_response.get(FIELD_STATE),
            description=release_response.get(FIELD_DESCRIPTION),
            parts_out=[PartOut(**part) for part in enriched_parts]
        )
        
        LOGGER.info(f"Successfully retrieved details for {len(enriched_parts)} asset(s)")
        return GetDataProductDetailsResponse(
            data_product_details=data_product_details,
            data_product_subscription_details=subscription_details
        )
        
    except ServiceError:
        raise
    except Exception as e:
        error_message = f"Exception when getting data product details: {e!s}"
        LOGGER.error(error_message)
        raise ServiceError(
            f"Failed to retrieve data product details. {error_message}"
        )


@service_registry.tool(
    name="data_product_get_data_product_details",
    description="""
    Retrieve comprehensive information about IBM Cloud Data Product Hub data products.
    
    This tool provides detailed metadata about data products including:
    - Release information (version, state, description)
    - Parts/assets with names, descriptions, and enriched column schemas
    - Primary key information (both at part level and column level)
    - Subscription details (if active subscriptions exist)
    
    **Required Input**: Provide either data_product_id OR data_product_name.
    
    Args:
        data_product_id: Optional ID of the data product. Provide either this or data_product_name.
        data_product_name: Optional name of the data product. Provide either this or data_product_id.
    
    Returns:
        GetDataProductDetailsResponse: Object containing data_product_details and data_product_subscription_details
    """,
    tags={"read", "data_product"},
    meta={"version": "1.0", "service": "data_product"}
)
@auto_context
async def wxo_get_data_product_details(
    data_product_id: Optional[str] = None,
    data_product_name: Optional[str] = None
) -> GetDataProductDetailsResponse:
    """Watsonx Orchestrator compatible version that expands GetDataProductDetailsRequest object into individual parameters."""

    request = GetDataProductDetailsRequest(
        data_product_id=data_product_id,
        data_product_name=data_product_name,
    )

    return await get_data_product_details(request)
