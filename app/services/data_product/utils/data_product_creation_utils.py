# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import asyncio
from typing import Any
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user
from app.shared.exceptions.base import ServiceError

def is_data_product_draft_create(request) -> bool:
    return not request.existing_data_product_draft_id and request.existing_data_product_draft_id != "None"


@auto_context
async def validate_inputs_for_draft_create(request, *additional_fields_to_validate):
    required_fields = ("name",) + additional_fields_to_validate

    for field in required_fields:
        value = getattr(request, field, None)
        if not value:
            msg = f"{field.capitalize()} of the data product is mandatory to create a data product draft."
            LOGGER.error(msg)
            raise ServiceError(msg)


@auto_context
async def create_part_asset_and_set_relationship(
    asset_name: str, target_asset_id: str
) -> None:
    """This common method can be called from create data product tools to:
    1. Create a part asset.
    2. Set relationship between the part asset and the target asset.
    
    NOTE: For batch operations with multiple assets, use batch_create_part_assets_and_set_relationships()
    which is significantly faster.
    """
    LOGGER.info("Creating ibm_data_product_part asset and setting relationship.")
    dph_catalog_id = await get_dph_catalog_id_for_user()
    payload = {
        "metadata": {
            "name": asset_name,
            "asset_type": "ibm_data_product_part",
            "rov": {"mode": 0},
        },
        "entity": {"ibm_data_product_part": {"dataset": True}},
    }
    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/assets?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=payload,
    )
    response_dict = _as_dict_response(response)
    metadata = response_dict.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    data_product_part_asset_id = metadata.get("asset_id", "")

    LOGGER.info(
        f"Created ibm_data_product_part asset with id {data_product_part_asset_id}."
    )
    # creating relationship
    await create_relationship(dph_catalog_id, target_asset_id, data_product_part_asset_id)


def _process_successful_response(
    asset_name: str,
    target_asset_id: str,
    response_item: dict,
    relationships_to_create: list[dict]
) -> dict:
    """
    Process a successful bulk create response (HTTP 200/201).
    
    Args:
        asset_name: Name of the asset
        target_asset_id: Target asset ID
        response_item: Response item from bulk create
        relationships_to_create: List to append relationship data to
        
    Returns:
        Result dictionary with success/error information
    """
    asset_data = response_item.get("asset", {})
    if not isinstance(asset_data, dict):
        asset_data = {}
    
    metadata = asset_data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    
    part_asset_id = metadata.get("asset_id", "")
    
    if not part_asset_id:
        return {
            "asset_name": asset_name,
            "target_asset_id": target_asset_id,
            "part_asset_id": "",
            "success": False,
            "error": "No asset_id in response"
        }
    
    # Success - prepare relationship for batch creation
    relationships_to_create.append({
        "target_asset_id": target_asset_id,
        "part_asset_id": part_asset_id
    })
    
    LOGGER.info(f"Created part asset {part_asset_id} for '{asset_name}'")
    return {
        "asset_name": asset_name,
        "target_asset_id": target_asset_id,
        "part_asset_id": part_asset_id,
        "success": True,
        "error": ""
    }


def _process_failed_response(
    asset_name: str,
    target_asset_id: str,
    response_item: dict
) -> dict:
    """
    Process a failed bulk create response.
    
    Args:
        asset_name: Name of the asset
        target_asset_id: Target asset ID
        response_item: Response item from bulk create
        
    Returns:
        Result dictionary with error information
    """
    http_status = response_item.get("http_status")
    errors = response_item.get("errors", [])
    error_msg = "Unknown error"
    if isinstance(errors, list) and errors:
        # Join all errors into a single message
        error_msg = "; ".join(str(err) for err in errors)
    
    LOGGER.error(f"Failed to create part asset for '{asset_name}': {error_msg}")
    return {
        "asset_name": asset_name,
        "target_asset_id": target_asset_id,
        "part_asset_id": "",
        "success": False,
        "error": f"HTTP {http_status}: {error_msg}"
    }


@auto_context
async def batch_create_part_assets_and_set_relationships(
    asset_names_and_ids: list[tuple[str, str]],
    dph_catalog_id: str
) -> list[dict]:
    """
    Batch create part assets and set relationships for multiple assets.
    
    This is significantly faster than calling create_part_asset_and_set_relationship()
    for each asset individually, as it uses:
    - /v2/assets/bulk_create for creating all part assets in one call
    - /v2/assets/set_relationships for setting up to 20 relationships in one call
    
    Args:
        asset_names_and_ids: List of tuples (asset_name, target_asset_id)
        dph_catalog_id: The DPH catalog ID
        
    Returns:
        List of dictionaries with part asset creation results:
        [
            {
                "asset_name": str,
                "target_asset_id": str,
                "part_asset_id": str,
                "success": bool,
                "error": str (if success=False)
            },
            ...
        ]
        
    Example:
        results = await batch_create_part_assets_and_set_relationships(
            [("Customer Data", "asset-123"), ("Orders Data", "asset-456")],
            "catalog-789"
        )
    """
    if not asset_names_and_ids:
        return []
    
    LOGGER.info(f"Batch creating {len(asset_names_and_ids)} part asset(s) and setting relationships")
    
    # Step 1: Build bulk create payload for all part assets
    assets_payload = []
    for asset_name, target_asset_id in asset_names_and_ids:
        assets_payload.append({
            "metadata": {
                "name": asset_name,
                "asset_type": "ibm_data_product_part",
                "rov": {"mode": 0}
            },
            "entity": {"ibm_data_product_part": {"dataset": True}},
        })
    
    # Step 2: Bulk create all part assets
    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}/v2/assets/bulk_create?catalog_id={dph_catalog_id}",
            json={"assets": assets_payload},
            tool_name="batch_create_part_assets"
        )
        response_dict = _as_dict_response(response)
        responses = response_dict.get("responses", [])
        
        if not isinstance(responses, list) or len(responses) != len(asset_names_and_ids):
            raise ServiceError(
                f"Bulk create returned unexpected response: expected {len(asset_names_and_ids)} responses, "
                f"got {len(responses) if isinstance(responses, list) else 'invalid'}"
            )
        
        LOGGER.info(f"Bulk created {len(responses)} part asset(s)")
        
    except Exception as e:
        LOGGER.error(f"Failed to bulk create part assets: {e}")
        # Return error results for all assets
        return [
            {
                "asset_name": name,
                "target_asset_id": target_id,
                "part_asset_id": "",
                "success": False,
                "error": f"Bulk create failed: {str(e)}"
            }
            for name, target_id in asset_names_and_ids
        ]
    
    # Step 3: Process responses and collect successful part asset IDs
    results = []
    relationships_to_create = []
    
    for (asset_name, target_asset_id), response_item in zip(asset_names_and_ids, responses):
        if not isinstance(response_item, dict):
            results.append({
                "asset_name": asset_name,
                "target_asset_id": target_asset_id,
                "part_asset_id": "",
                "success": False,
                "error": "Invalid response format"
            })
            continue
        
        http_status = response_item.get("http_status")
        
        # Check if creation was successful (201 = created, 200 = updated/duplicate)
        if http_status in (200, 201):
            result = _process_successful_response(asset_name, target_asset_id, response_item, relationships_to_create)
        else:
            result = _process_failed_response(asset_name, target_asset_id, response_item)
        
        results.append(result)
    
    # Step 4: Batch create relationships (up to 20 at a time)
    if relationships_to_create:
        await _batch_create_relationships(relationships_to_create, dph_catalog_id)
    
    success_count = sum(1 for r in results if r["success"])
    LOGGER.info(f"Successfully created {success_count}/{len(results)} part asset(s) with relationships")
    
    return results


async def _batch_create_relationships(
    relationships_data: list[dict],
    dph_catalog_id: str
) -> None:
    """
    Create all relationships in a single API call.
    
    Args:
        relationships_data: List of dicts with target_asset_id and part_asset_id
        dph_catalog_id: The DPH catalog ID
    """
    if not relationships_data:
        return
    
    total = len(relationships_data)
    LOGGER.info(f"Creating {total} relationship(s) in a single batch")
    
    # Build relationships payload for all relationships
    relationships_payload = []
    for rel_data in relationships_data:
        relationships_payload.append({
            "relationship_name": "has_part",
            "source": {
                "catalog_id": dph_catalog_id,
                "asset_id": rel_data["target_asset_id"]
            },
            "target": {
                "catalog_id": dph_catalog_id,
                "asset_id": rel_data["part_asset_id"]
            },
        })
    
    try:
        await tool_helper_service.execute_post_request(
            f"{tool_helper_service.base_url}/v2/assets/set_relationships",
            json={"relationships": relationships_payload},
            tool_name="batch_set_relationships"
        )
        LOGGER.info(f"Successfully created {total} relationship(s)")
    except Exception as e:
        LOGGER.error(f"Failed to create {total} relationship(s): {e}")
        raise


async def create_relationship(
    dph_catalog_id: str, target_asset_id: str, data_product_part_asset_id: str
):
    payload = {
        "relationships": [
            {
                "relationship_name": "has_part",
                "source": {"catalog_id": dph_catalog_id, "asset_id": target_asset_id},
                "target": {
                    "catalog_id": dph_catalog_id,
                    "asset_id": data_product_part_asset_id,
                },
            }
        ]
    }

    await tool_helper_service.execute_post_request(
        f"{tool_helper_service.base_url}/v2/assets/set_relationships", json=payload
    )
    LOGGER.info(
        f"Created relationship between {target_asset_id} and {data_product_part_asset_id}."
    )


def _as_dict_response(response: dict[str, Any] | bytes) -> dict[str, Any]:
    """Normalize tool helper response to a dictionary for safe access."""
    if isinstance(response, dict):
        return response
    return {}


def _get_asset_type_search_results(response: dict[str, Any] | bytes) -> list[dict[str, Any]]:
    """Get results list from /v2/asset_types search response."""
    response_dict = _as_dict_response(response)
    results = response_dict.get("results", [])
    if isinstance(results, list):
        return [result for result in results if isinstance(result, dict)]
    return []


def _get_asset_type_search_results_count(response: dict[str, Any] | bytes) -> int:
    """Get result count from /v2/asset_types search response."""
    results = _get_asset_type_search_results(response)
    if results:
        return len(results)

    response_dict = _as_dict_response(response)

    total_rows = response_dict.get("total_rows")
    if isinstance(total_rows, int):
        return total_rows

    size = response_dict.get("size")
    if isinstance(size, int):
        return size

    return 0


def _extract_duplicate_info_from_asset_type_search_result(result: dict[str, Any]) -> dict:
    """Extract duplicate information from /v2/asset_types search result."""
    metadata = result.get("metadata", {})
    entity = result.get("entity", {})
    dp_version = entity.get("ibm_data_product_version", {})

    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(entity, dict):
        entity = {}
    if not isinstance(dp_version, dict):
        dp_version = {}

    return {
        "data_product_id": dp_version.get("product_id", ""),
        "version_id": metadata.get("asset_id", ""),
        "name": metadata.get("name", ""),
        "state": dp_version.get("state", "") or metadata.get("asset_state", ""),
    }


@auto_context
async def check_for_duplicate_data_product_with_asset(
    asset_id: str, dph_catalog_id: str, max_retries: int = 1, initial_delay: float = 1.0
) -> dict | None:
    """
    SIMPLIFIED: Check if a data product already exists with the given asset using /v2/asset_types API.
    
    This uses the simpler /v2/asset_types/ibm_data_product_version/search endpoint with
    a string query instead of complex nested v3/search queries.
    
    Query format: "ibm_data_product_version.parts_out_asset_id:ASSET_ID AND (state:available OR state:draft)"
    
    Args:
        asset_id: The ID of the asset to search for (in DPH catalog)
        dph_catalog_id: The DPH catalog ID where data products are stored
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        
    Returns:
        dict: Information about the existing data product if found, None otherwise.
              Returns: {"data_product_id": str, "version_id": str, "name": str, "state": str}
    """
    LOGGER.info(f"Checking for data products containing asset {asset_id} using /v2/asset_types API (max_retries={max_retries})")
    
    # Simple string query - much easier than nested JSON!
    query = (
        f"ibm_data_product_version.parts_out_asset_id:{asset_id} "
        f"AND (ibm_data_product_version.state:available OR ibm_data_product_version.state:draft)"
    )
    
    # Retry logic with exponential backoff to handle search index propagation delays
    for attempt in range(max_retries):
        try:
            response = await tool_helper_service.execute_post_request(
                url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_version/search",
                params={"catalog_id": dph_catalog_id},
                json={"query": query},
                tool_name="check_for_duplicate_data_product_with_asset"
            )
            
            # Check if any results found
            results_size = _get_asset_type_search_results_count(response)
            
            if results_size > 0:
                # Duplicate found!
                results = _get_asset_type_search_results(response)
                result = results[0]
                duplicate_info = _extract_duplicate_info_from_asset_type_search_result(result)
                
                LOGGER.info(
                    f"Found existing data product '{duplicate_info['name']}' "
                    f"(ID: {duplicate_info['data_product_id']}, State: {duplicate_info['state']}) "
                    f"with asset {asset_id} on attempt {attempt + 1}"
                )
                return duplicate_info
            
            # If no results found and we have retries left, wait and try again
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                LOGGER.info(
                    f"No duplicate found on attempt {attempt + 1}/{max_retries}. "
                    f"Waiting {delay}s for search index to update..."
                )
                await asyncio.sleep(delay)
            else:
                LOGGER.info(f"No existing data product found with asset {asset_id} after {max_retries} attempts")
                return None
                
        except Exception as e:
            LOGGER.error(f"Error checking for duplicates on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            delay = initial_delay * (2 ** attempt)
            LOGGER.info(f"Retrying in {delay}s...")
            await asyncio.sleep(delay)
    
    return None


def _get_data_asset_items(dp) -> list:
    """Extract data_asset_items from data product, handling both dict and object types."""
    if isinstance(dp, dict):
        return dp.get("data_asset_items", [])
    return getattr(dp, "data_asset_items", [])


def _get_asset_item_name(asset_item) -> str:
    """Extract name from asset item, handling both dict and object types."""
    if isinstance(asset_item, dict):
        return asset_item.get("name", "")
    return getattr(asset_item, "name", "")


def _extract_duplicate_info_from_data_product(dp) -> dict:
    """Extract duplicate info from data product, handling both dict and object types."""
    if isinstance(dp, dict):
        return {
            "data_product_id": dp.get("data_product_id", ""),
            "version_id": dp.get("data_product_version_id", ""),
            "name": dp.get("name", ""),
            "state": "available" if "/productState=available" in dp.get("url", "") else "draft"
        }
    
    return {
        "data_product_id": getattr(dp, "data_product_id", ""),
        "version_id": getattr(dp, "data_product_version_id", ""),
        "name": getattr(dp, "name", ""),
        "state": "available" if "/productState=available" in getattr(dp, "url", "") else "draft"
    }


def _check_asset_name_match(asset_item, target_name: str) -> bool:
    """Check if asset item name matches target name (case-insensitive)."""
    asset_item_name = _get_asset_item_name(asset_item)
    return asset_item_name.upper() == target_name.upper()


def _find_matching_asset_in_data_product(dp, asset_name: str) -> bool:
    """Check if data product contains an asset with the given name."""
    data_asset_items = _get_data_asset_items(dp)
    return any(_check_asset_name_match(item, asset_name) for item in data_asset_items)


@auto_context
async def check_for_duplicate_data_product_with_asset_name(
    asset_name: str, dph_catalog_id: str
) -> dict | None:
    """
    Check if a data product (draft or released) already exists with an asset of the given name.
    
    Uses the existing search_data_products function with "*" query to search ALL data products,
    then filters results to find ones containing the specific asset name.
    
    Args:
        asset_name: The name of the asset to search for (e.g., "CREDIT_SCORE")
        dph_catalog_id: The DPH catalog ID where data products are stored (not used, kept for compatibility)
        
    Returns:
        dict: Information about the existing data product if found, None otherwise.
              Returns: {"data_product_id": str, "version_id": str, "name": str, "state": str}
    """
    LOGGER.info(f"=== DUPLICATE CHECK START === Searching for data products with asset '{asset_name}'")
    
    # Import here to avoid circular dependency
    from app.services.data_product.tools.search_data_products import search_data_products
    from app.services.data_product.models.search_data_products import SearchDataProductsRequest
    
    # CRITICAL: Use "*" to search ALL data products
    search_request = SearchDataProductsRequest(product_search_query="*")
    search_response = await search_data_products(search_request)
    
    LOGGER.info(f"=== DUPLICATE CHECK === Found {search_response.count} total data products, filtering for asset '{asset_name}'")
    
    # Find first data product containing the asset
    for dp in search_response.data_products:
        if _find_matching_asset_in_data_product(dp, asset_name):
            duplicate_info = _extract_duplicate_info_from_data_product(dp)
            LOGGER.info(
                f"=== DUPLICATE CHECK FOUND === '{duplicate_info['name']}' "
                f"(ID: {duplicate_info['data_product_id']}, State: {duplicate_info['state']})"
            )
            return duplicate_info
    
    LOGGER.info("=== DUPLICATE CHECK === No duplicate found")
    return None

@auto_context
def _extract_parts_out_from_result(result: dict) -> list[dict]:
    """
    Extract and validate parts_out list from search result.
    
    Args:
        result: Search result dictionary
        
    Returns:
        List of parts_out dictionaries, or empty list if invalid
    """
    entity = result.get("entity", {})
    if not isinstance(entity, dict):
        return []
        
    dp_version = entity.get("ibm_data_product_version", {})
    if not isinstance(dp_version, dict):
        return []
        
    parts_out = dp_version.get("parts_out", [])
    if not isinstance(parts_out, list):
        return []
    
    return parts_out


def _process_parts_for_duplicates(
    parts_out: list[dict],
    target_asset_ids: list[str],
    dp_info: dict,
    duplicates_map: dict[str, dict]
) -> None:
    """
    Process parts_out to find matching asset IDs and update duplicates map.
    
    Args:
        parts_out: List of part dictionaries from data product
        target_asset_ids: List of target asset IDs to check for
        dp_info: Data product info to store for duplicates
        duplicates_map: Map to update with found duplicates
    """
    for part in parts_out:
        if not isinstance(part, dict):
            continue
            
        asset_info = part.get("asset", {})
        if not isinstance(asset_info, dict):
            continue
            
        asset_id = asset_info.get("id")
        
        # Check if this asset is one we're looking for
        if not asset_id or asset_id not in target_asset_ids:
            continue
        
        # Only keep the first data product found for each asset
        if asset_id in duplicates_map:
            continue
            
        duplicates_map[asset_id] = dp_info
        LOGGER.info(
            f"Found duplicate: Asset {asset_id} in data product "
            f"'{dp_info['name']}' (ID: {dp_info['data_product_id']}, State: {dp_info['state']})"
        )


async def batch_check_for_duplicate_data_products_by_target_asset_ids(
    target_asset_ids: list[str],
    dph_catalog_id: str
) -> dict[str, dict]:
    """
    Batch check if any of the given target assets already exist in data products.
    
    Uses a single Lucene query with OR to check multiple assets at once, significantly
    improving performance compared to checking each asset individually.
    
    Args:
        target_asset_ids: List of target asset IDs to check
        dph_catalog_id: The DPH catalog ID where data products are stored
        
    Returns:
        Dictionary mapping source_asset_id -> duplicate info for assets that ARE in data products:
        {
            "asset_id_1": {
                "data_product_id": "dp-123",
                "version_id": "v-456",
                "name": "My Data Product",
                "state": "draft"
            },
            "asset_id_2": {...}
        }
        Only includes assets that are already in data products (not all input assets)
        
    Example:
        Input: ["asset1", "asset2", "asset3"]
        Output: {"asset1": {...}, "asset3": {...}}  # asset2 not in any data product
    """
    if not target_asset_ids:
        return {}
    
    # Build query with OR for all asset IDs: "id1 OR id2 OR id3"
    ids_query_string = " OR ".join(target_asset_ids)
    query = (
        f"ibm_data_product_version.parts_out_asset_id:({ids_query_string}) "
        f"AND (ibm_data_product_version.state:available OR ibm_data_product_version.state:draft)"
    )
    
    LOGGER.info(f"Batch checking {len(target_asset_ids)} source asset(s) for duplicates")
    LOGGER.debug(f"Query: {query}")
    
    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}/v2/asset_types/ibm_data_product_version/search",
            params={"catalog_id": dph_catalog_id},
            json={"query": query},
            tool_name="batch_check_for_duplicate_data_products"
        )
        
        # Parse results - map each asset_id to its data product
        duplicates_map = {}
        results = _get_asset_type_search_results(response)
        
        for result in results:
            dp_info = _extract_duplicate_info_from_asset_type_search_result(result)
            parts_out = _extract_parts_out_from_result(result)
            _process_parts_for_duplicates(parts_out, target_asset_ids, dp_info, duplicates_map)
        
        found_count = len(duplicates_map)
        total_count = len(target_asset_ids)
        LOGGER.info(f"Found {found_count} duplicate(s) out of {total_count} asset(s)")
        
        return duplicates_map
        
    except Exception as e:
        LOGGER.error(f"Error in batch duplicate check: {e}")
        # Return empty dict on error - validation will proceed without duplicate check
        return {}


@auto_context
async def check_for_duplicate_data_product_by_source_asset_id(
    source_asset_id: str,
    source_container_id: str,
    source_container_type: str,
    dph_catalog_id: str
) -> dict | None:
    """
    Check if any data product contains an asset that was copied from the given source asset.
    
    This is a two-step process:
    1. First, check if the source asset has already been copied to DPH catalog (using asset.source_asset_id)
    2. If found, check if that copied asset is used in any data product (using parts_out_asset_id)
    
    Args:
        source_asset_id: The ID of the source asset to check (from source catalog/project)
        source_container_id: The ID of the source container (catalog/project)
        source_container_type: The type of source container ("catalog" or "project")
        dph_catalog_id: The DPH catalog ID where data products are stored
        
    Returns:
        dict: Information about the existing data product if found, None otherwise.
              Returns: {"data_product_id": str, "version_id": str, "name": str, "state": str}
    """
    LOGGER.info(
        f"=== SOURCE ASSET DUPLICATE CHECK === "
        f"Checking for data products containing source asset {source_asset_id} "
        f"from {source_container_type}:{source_container_id}"
    )
    
    # Step 1: Check if source asset has already been copied to DPH catalog
    # Import here to avoid circular dependency
    from app.services.data_product.tools.import_remote_assets_to_dph_catalog import find_existing_copied_assets
    
    existing_copies = await find_existing_copied_assets([source_asset_id], dph_catalog_id)
    
    if not existing_copies or source_asset_id not in existing_copies:
        LOGGER.info(
            f"=== NO DUPLICATE === "
            f"Source asset {source_asset_id} has not been copied to DPH catalog yet"
        )
        return None
    
    # Step 2: Get the target asset ID (the copied asset in DPH catalog)
    target_asset_id = existing_copies[source_asset_id]["target_asset_id"]
    LOGGER.info(
        f"Found copied asset: source {source_asset_id} -> target {target_asset_id}"
    )
    
    # Step 3: Check if this target asset is used in any data product
    duplicate_info = await check_for_duplicate_data_product_with_asset(
        asset_id=target_asset_id,
        dph_catalog_id=dph_catalog_id,
        max_retries=1
    )
    
    if duplicate_info:
        LOGGER.info(
            f"=== DUPLICATE FOUND === "
            f"Source asset {source_asset_id} (copied as {target_asset_id}) "
            f"is already in data product '{duplicate_info['name']}' "
            f"(ID: {duplicate_info['data_product_id']}, State: {duplicate_info['state']})"
        )
        return duplicate_info
    
    LOGGER.info(
        f"=== NO DUPLICATE === "
        f"Source asset {source_asset_id} (copied as {target_asset_id}) "
        f"not found in any data products"
    )
    return None
