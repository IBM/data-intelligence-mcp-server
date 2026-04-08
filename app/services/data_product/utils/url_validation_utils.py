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

"""
URL validation utilities for data product creation.

This module provides functionality to validate that URLs don't already exist
in data products before creating new ones, preventing duplicate URL data products.
"""

from typing import List, Dict, Any

from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user


# Constants for search API
SEARCH_ENDPOINT = "/v3/search"
SEARCH_PARAMS = "role=viewer&auth_cache=false&auth_scope=all&type=metadata"
MAX_RESULTS = 50


@auto_context
async def validate_url_not_in_existing_data_products(
    url_value: str, 
    force: bool = False
) -> List[Dict[str, Any]]:
    """
    Validates that a URL doesn't already exist in any data product.
    
    Uses the v3/search API with a nested query to efficiently search for data products
    containing the specified URL in their parts_out. This approach directly queries
    the search index for matching URLs, making it much more efficient than fetching
    all data products and checking each one.
    
    Args:
        url_value: The URL value to check for duplicates
        force: If True, skips validation and returns empty list (allows duplicate creation)
        
    Returns:
        List of dictionaries containing information about existing data products with the URL.
        Each dictionary contains:
            - data_product_id: The product ID
            - name: The data product name
            - version: The version ID
            - state: The state (draft or available)
            - url_asset_name: The name of the URL asset
            - url: The URL value
            
    Raises:
        Exception: Re-raises any critical errors that prevent validation from running
        
    Note:
        There may be a small delay (seconds to minutes) between creating a data product
        and it appearing in search results due to search index update latency.
    """
    LOGGER.info(f"Starting URL validation for: {url_value}")
    
    if force:
        LOGGER.info("Force flag is True, skipping validation")
        return []
    
    try:
        dph_catalog_id = await get_dph_catalog_id_for_user()
        search_payload = _build_search_payload(url_value, dph_catalog_id)
        
        LOGGER.info(f"Searching for data products containing URL: {url_value}")
        search_response = await _execute_search(search_payload)
        
        rows = search_response.get("rows", [])
        LOGGER.info(f"Found {len(rows)} data products containing URL: {url_value}")
        
        existing_products = _extract_product_info(rows, url_value)
        
        if existing_products:
            LOGGER.warning(
                f"Found {len(existing_products)} data products with matching URL '{url_value}'"
            )
        else:
            LOGGER.info(f"No existing data products found with URL: {url_value}")
            
        return existing_products
        
    except Exception as e:
        LOGGER.error(f"Critical error during URL validation: {str(e)}")
        LOGGER.error(f"Exception type: {type(e).__name__}", exc_info=True)
        # Re-raise critical errors - we cannot proceed without validation
        raise


def _build_search_payload(url_value: str, catalog_id: str) -> Dict[str, Any]:
    """
    Builds the search payload for finding data products with a specific URL.
    
    Uses a nested query to search directly in parts_out.name for the URL value.
    This is much more efficient than fetching all data products.
    
    Args:
        url_value: The URL to search for
        catalog_id: The catalog ID to filter by
        
    Returns:
        Dictionary containing the search payload
    """
    return {
        "_source": [
            "artifact_id",
            "metadata.name",
            "metadata.description",
            "entity.data_product_version.product_id",
            "entity.data_product_version.id",
            "entity.data_product_version.version",
            "entity.data_product_version.state",
            "entity.data_product_version.parts_out"
        ],
        "query": {
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "entity.data_product_version.parts_out",
                            "query": {
                                "term": {
                                    "entity.data_product_version.parts_out.name.keyword": url_value
                                }
                            }
                        }
                    }
                ],
                "filter": [
                    {
                        "term": {
                            "metadata.artifact_type": "ibm_data_product_version"
                        }
                    },
                    {
                        "terms": {
                            "entity.data_product_version.state": ["available", "draft"]
                        }
                    },
                    {
                        "term": {
                            "entity.assets.catalog_id": catalog_id
                        }
                    }
                ]
            }
        },
        "size": MAX_RESULTS
    }


async def _execute_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the search request against the v3/search API.
    
    Args:
        payload: The search payload
        
    Returns:
        The search response dictionary
        
    Raises:
        Exception: If the search request fails
    """
    search_url = f"{tool_helper_service.base_url}{SEARCH_ENDPOINT}?{SEARCH_PARAMS}"
    
    return await tool_helper_service.execute_post_request(
        url=search_url,
        json=payload,
        tool_name="validate_url_not_in_existing_data_products",
    )


def _extract_product_info(rows: List[Dict[str, Any]], url_value: str) -> List[Dict[str, Any]]:
    """
    Extracts relevant information from search results.
    
    Args:
        rows: List of search result rows
        url_value: The URL being searched for
        
    Returns:
        List of dictionaries containing extracted product information
    """
    existing_products = []
    
    for row in rows:
        try:
            metadata = row.get("metadata", {})
            entity = row.get("entity", {})
            dp_version = entity.get("data_product_version", {})
            
            dp_id = dp_version.get("product_id")
            version_id = dp_version.get("id")
            dp_name = metadata.get("name", "Unknown")
            state = dp_version.get("state", "unknown")
            
            # Find the URL asset name from parts_out
            parts_out = dp_version.get("parts_out", [])
            url_asset_name = _find_url_asset_name(parts_out, url_value)
            
            existing_products.append({
                "data_product_id": dp_id,
                "name": dp_name,
                "version": version_id,
                "state": state,
                "url_asset_name": url_asset_name,
                "url": url_value
            })
            
            LOGGER.warning(
                f"DUPLICATE FOUND! Data product '{dp_name}' "
                f"(ID: {dp_id}, State: {state}) contains URL '{url_value}'"
            )
            
        except Exception as e:
            LOGGER.warning(f"Error processing search result: {str(e)}")
            continue
    
    return existing_products


def _find_url_asset_name(parts_out: List[Dict[str, Any]], url_value: str) -> str:
    """
    Finds the URL asset name from parts_out that matches the URL value.
    
    Args:
        parts_out: List of parts from the data product
        url_value: The URL to match
        
    Returns:
        The name of the matching URL asset, or the URL value if not found
    """
    for part in parts_out:
        if part.get("name") == url_value:
            return part.get("name", url_value)
    return url_value

# Made with Bob
