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

from app.services.constants import DATA_PRODUCT_ENDPOINT, CAMS_ASSETS_BASE_ENDPOINT
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user


@auto_context
async def validate_url_not_in_existing_data_products(url_value: str, force: bool = False) -> list[dict]:
    """
    Validates that a URL doesn't already exist in any data product's parts_out.
    
    Process:
    1. Get list of all data products and drafts
    2. Fetch each data product individually by ID to get full details
    3. Check parts_out for ibm_url_definition assets
    4. Fetch asset details to compare URL values
    
    Args:
        url_value (str): The URL value to check for duplicates
        force (bool): If True, returns existing products but doesn't raise error
        
    Returns:
        list[dict]: List of existing data products that contain the URL
    """
    LOGGER.info(f"Validating URL not in existing data products: {url_value}")
    
    dph_catalog_id = await get_dph_catalog_id_for_user()
    existing_products = []
    
    # Step 1: Get list of all data product IDs (both drafts and released)
    all_dp_ids = await _get_all_data_product_ids(dph_catalog_id)
    LOGGER.info(f"Found {len(all_dp_ids)} total data products to check")
    
    # Step 2: Fetch each data product individually and check for URL
    for dp_info in all_dp_ids:
        dp_id = dp_info.get("id")
        is_draft = dp_info.get("is_draft", False)
        
        if not dp_id:
            continue
            
        try:
            # Step 2a: Get full data product details by ID
            dp_details = await _get_data_product_details_by_id(dp_id, is_draft)
            
            if not dp_details:
                LOGGER.warning(f"Could not fetch details for data product {dp_id}")
                continue
            
            # Step 3: Check parts_out for URL assets
            url_found = await _check_data_product_for_url(
                dp_details,
                url_value,
                dph_catalog_id
            )
            
            if url_found:
                existing_products.append(url_found)
                LOGGER.info(f"Found matching URL in data product: {dp_details.get('name')}")
                # Return immediately when URL is found - early exit
                LOGGER.warning("URL already present in data product. Returning immediately.")
                return existing_products
                
        except Exception as e:
            LOGGER.warning(f"Error checking data product {dp_id}: {str(e)}")
            continue
    
    # No existing products found with the URL
    LOGGER.info(f"No existing data products found with URL: {url_value}")
    return existing_products


async def _get_all_data_product_ids(dph_catalog_id: str) -> list[dict]:
    """
    Step 1: Get list of all data product IDs (both drafts and released).
    
    Args:
        dph_catalog_id (str): The catalog ID
        
    Returns:
        list[dict]: List of dicts with 'id' and 'is_draft' keys
    """
    all_ids = []
    
    # Get all draft IDs
    try:
        drafts_response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{DATA_PRODUCT_ENDPOINT}/-/drafts",
            tool_name="validate_url_not_in_existing_data_products",
        )
        
        drafts = drafts_response.get("drafts", [])
        for draft in drafts:
            if draft.get("id"):
                all_ids.append({
                    "id": draft.get("id"),
                    "is_draft": True
                })
        
        LOGGER.info(f"Found {len(drafts)} draft data products")
        
    except Exception as e:
        LOGGER.warning(f"Failed to fetch drafts: {str(e)}")
    
    # Get all released data product IDs using the new endpoint with state=available&limit=200
    try:
        products_response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{DATA_PRODUCT_ENDPOINT}/-/releases?state=available&limit=200",
            tool_name="validate_url_not_in_existing_data_products",
        )
        
        products = products_response.get("releases", [])
        for product in products:
            if product.get("id"):
                all_ids.append({
                    "id": product.get("id"),
                    "is_draft": False
                })
        
        LOGGER.info(f"Found {len(products)} released data products")
        
    except Exception as e:
        LOGGER.warning(f"Failed to fetch released products: {str(e)}")
    
    return all_ids


async def _get_data_product_details_by_id(dp_id: str, is_draft: bool) -> dict:
    """
    Step 2: Fetch individual data product by ID to get full details including parts_out.
    
    Args:
        dp_id (str): The data product ID
        is_draft (bool): Whether this is a draft or released product
        
    Returns:
        dict: The data product with full details
    """
    if is_draft:
        # For drafts, use the draft endpoint with correct format: /data_products/-/drafts/{draft_id}
        url = f"{tool_helper_service.base_url}{DATA_PRODUCT_ENDPOINT}/-/drafts/{dp_id}"
    else:
        # For released products, use the regular endpoint
        url = f"{tool_helper_service.base_url}{DATA_PRODUCT_ENDPOINT}/{dp_id}"
    
    response = await tool_helper_service.execute_get_request(
        url=url,
        tool_name="validate_url_not_in_existing_data_products",
    )
    
    return response


async def _check_data_product_for_url(dp_details: dict, url_value: str, dph_catalog_id: str) -> dict | None:
    """
    Step 3: Check a data product's parts_out for matching URL.
    
    Args:
        dp_details (dict): The data product details
        url_value (str): The URL to search for
        dph_catalog_id (str): The catalog ID
        
    Returns:
        dict | None: Data product info if URL found, None otherwise
    """
    parts_out = dp_details.get("parts_out", [])
    
    for part in parts_out:
        asset_id = part.get("asset", {}).get("id")
        asset_type = part.get("asset", {}).get("type")
        
        # Only check URL definition assets
        if asset_type == "ibm_url_definition" and asset_id:
            try:
                # Fetch the asset to get the URL value and name
                asset_url, asset_name = await _get_url_asset_value(asset_id, dph_catalog_id)
                
                # Compare URLs
                if asset_url == url_value:
                    return {
                        "data_product_id": dp_details.get("id"),
                        "name": dp_details.get("name"),
                        "version": dp_details.get("version"),
                        "state": dp_details.get("state", "draft"),
                        "url_asset_name": asset_name,
                        "url": asset_url
                    }
            except Exception as e:
                LOGGER.warning(f"Error fetching asset {asset_id}: {str(e)}")
                continue
    
    return None


async def _get_url_asset_value(asset_id: str, dph_catalog_id: str) -> tuple[str, str]:
    """
    Fetch the URL value and name from a URL asset.
    
    Args:
        asset_id (str): The asset ID
        dph_catalog_id (str): The catalog ID
        
    Returns:
        tuple[str, str]: The URL value and asset name from the asset
    """
    asset_response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/{asset_id}?catalog_id={dph_catalog_id}",
        tool_name="validate_url_not_in_existing_data_products",
    )
    
    asset_url = asset_response.get("entity", {}).get("ibm_url_definition", {}).get("url", "")
    asset_name = asset_response.get("metadata", {}).get("name", "")
    return asset_url, asset_name