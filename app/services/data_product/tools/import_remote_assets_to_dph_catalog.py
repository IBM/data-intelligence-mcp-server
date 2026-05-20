# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import time
from typing import Any, cast
from collections import defaultdict
from urllib.parse import urlencode

from app.core.registry import service_registry
from app.services.data_product.models.import_remote_assets_to_dph_catalog import (
    ImportRemoteAssetsToDphCatalogRequest,
    ImportRemoteAssetsToDphCatalogResponse
)
from app.shared.exceptions.base import ServiceError
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user
from app.services.data_product.utils.data_product_creation_utils import (
    batch_check_for_duplicate_data_products_by_source_asset_ids,
    batch_create_part_assets_and_set_relationships,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service

# ============================================================================
# Helper Functions for Asset Import
# ============================================================================

def _format_error_report(
    errors: list[dict],
    successes: list[dict],
    total_count: int,
    phase: str,
    state_changed: bool
) -> str:
    """
    Format a detailed error report for validation or post-processing failures.
    
    Args:
        errors: List of error dictionaries with asset details and error info
        successes: List of success dictionaries with asset details
        total_count: Total number of assets processed
        phase: "Validation" or "Import"
        state_changed: Whether any state changes occurred (assets copied, etc.)
        
    Returns:
        Formatted error message string
    """
    error_summary = (
        f"{phase} failed for {len(errors)} of {total_count} asset(s).\n\n"
        f"{phase.upper()} FAILURES ({len(errors)}):\n"
        f"{'=' * 80}\n"
    )
    
    for i, err in enumerate(errors, 1):
        error_summary += (
            f"\n{i}. Asset: {err['asset_name']}\n"
            f"   Asset ID: {err.get('source_asset_id', err.get('asset_id', 'N/A'))}\n"
        )
        if 'target_asset_id' in err:
            error_summary += f"   Target ID: {err['target_asset_id']}\n"
        error_summary += (
            f"   Container: {err['container_type']}:{err['container_id']}\n"
            f"   Error Type: {err['error_type']}\n"
            f"   Error: {err['error']}\n"
        )
    
    if successes:
        error_summary += (
            f"\n{'=' * 80}\n"
            f"SUCCESSFULLY PROCESSED ASSETS ({len(successes)}):\n"
            f"{'=' * 80}\n"
        )
        for i, success in enumerate(successes, 1):
            error_summary += (
                f"\n{i}. Asset: {success['asset_name']}\n"
                f"   Asset ID: {success.get('source_asset_id', success.get('asset_id', 'N/A'))}\n"
            )
            if 'target_asset_id' in success:
                error_summary += f"   Target ID: {success['target_asset_id']}\n"
            error_summary += f"   Container: {success['container_type']}:{success['container_id']}\n"
    
    error_summary += (
        f"\n{'=' * 80}\n"
        "IMPORTANT NOTES:\n"
        f"{'=' * 80}\n"
    )
    
    if state_changed:
        error_summary += (
            f"• All {total_count} assets were successfully copied to DPH catalog\n"
            f"• {phase} (revisions, relationships) failed for {len(errors)} asset(s)\n"
            "• Failed assets may need manual cleanup or retry\n"
        )
    else:
        error_summary += (
            f"• No assets were copied ({phase.lower()} happens before any state changes)\n"
            f"• Fix the {phase.lower()} errors above and retry the operation\n"
            f"• All assets must pass {phase.lower()} before data product creation can proceed\n"
        )
    
    error_summary += ("• IMPORTANT: ALWAYS present these error(s) 'AS IT IS' to the user and let the user review the error details above to understand what went wrong\n"
        "• Do not assume the next step. Wait for user's input\n"
        "• Note that data product will not be created until all assets are successfully processed."
    )
    
    return error_summary


@auto_context
async def batch_get_asset_details(
    asset_ids: list[str], container_id: str, container_type: str
) -> dict[str, dict]:
    """
    Fetch details for multiple assets from the same container in a single API call.
    The /v2/assets/bulk endpoint supports up to 20 comma-separated asset IDs.
    
    Args:
        asset_ids: List of asset IDs to fetch (max 20)
        container_id: The container ID (catalog or project)
        container_type: The container type ('catalog' or 'project')
        
    Returns:
        Dictionary mapping asset_id to asset details
        
    Raises:
        ServiceError: If the API call fails or returns errors
    """
    if len(asset_ids) > 20:
        LOGGER.warning(f"Batch get_asset_details called with {len(asset_ids)} assets, max is 20. Will be chunked.")
    
    LOGGER.info(f"Batch fetching details for {len(asset_ids)} assets from {container_type}:{container_id}")
    
    query_params = {
        "asset_ids": ",".join(asset_ids),
        "hide_deprecated_response_fields": "false",
        "include_relationship_count": "true",
        "include_source_columns": "false",
    }
    if container_type == "catalog":
        query_params["catalog_id"] = container_id
    else:
        query_params["project_id"] = container_id

    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/assets/bulk",
        params=query_params,
        tool_name="import_remote_assets_to_dph_catalog",
    )
    response_dict = cast(dict[str, Any], response)
    
    LOGGER.info(f"Batch get_asset_details response received for {len(asset_ids)} assets.")
    # Check if response has resources
    resources = response_dict.get("resources", [])
    if not resources or len(resources) == 0:
        error_msg = f"Failed to retrieve asset details for {len(asset_ids)} assets in {container_type}={container_id}. "
        if response_dict.get("errors"):
            error_msg += f"API errors: {response_dict.get('errors')}"
        else:
            error_msg += "No resources returned from the API."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)
    
    # Build a map of asset_id -> asset_details
    asset_details_map = {}
    for resource in cast(list[dict[str, Any]], resources):
        if resource.get('errors'):
            asset_id = resource.get('asset', {}).get('asset_id', 'unknown')
            LOGGER.error(f"Error fetching asset {asset_id}: {resource.get('errors')}")
            raise ServiceError(f"Error fetching asset {asset_id}: {resource.get('errors')}")
        
        asset_id = resource.get('asset_id')
        if asset_id:
            asset_details_map[asset_id] = resource
    
    LOGGER.info(f"Successfully fetched details for {len(asset_details_map)} assets")
    return asset_details_map


def _get_connection_id(asset_details: dict) -> str:
    """Extract connection ID from asset details."""
    connection_id = ""
    for attachment in asset_details.get("asset", {}).get("attachments", []):
        if attachment.get("asset_type", "") == "data_asset":
            connection_id = attachment.get("connection_id")
            break
    return connection_id


@auto_context
async def get_datasource_type_from_connection(connection_id: str, container_id: str, container_type: str | None = None) -> str:
    """Get datasource type from connection."""
    query_params: dict[str, bool | str] = {
        "decrypt_secrets": True,
        "userfs": False
    }
    if not container_type or container_type == "catalog":
        query_params["catalog_id"] = container_id
    else:
        query_params["project_id"] = container_id
    
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/connections/{connection_id}",
        params=query_params,
        tool_name="import_remote_assets_to_dph_catalog",
    )
    response_dict = cast(dict[str, Any], response)
    datasource_type = cast(dict[str, Any], response_dict.get("entity", {})).get("datasource_type", "")
    LOGGER.info(f"Datasource type found: {datasource_type}")
    return datasource_type


@auto_context
async def _validate_if_datasource_type_is_supported(datasource_type: str) -> None:
    """Validate if the datasource type is supported for the asset selected."""
    query_params = {
        "offset": 0,
        "limit": 100,
        "entity.product": "cpd",
        "generate_transitive_conditions": False,
        "show_data_source_definitions_only":False,
        "show_data_source_definition_section": True
    }
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/datasource_types",
        params=query_params,
        tool_name="import_remote_assets_to_dph_catalog",
    )
    response_dict = cast(dict[str, Any], response)
    supported_datasource_types = {
        resource.get("metadata", {}).get("asset_id")
        for resource in cast(list[dict[str, Any]], response_dict.get("resources", []))
    }
    if datasource_type not in supported_datasource_types:
        LOGGER.error("Data source type is not supported for the selected asset.")
        raise ServiceError("The selected asset belongs to a data source type that is not supported currently, and hence this cannot be a data product." \
        "Please select a different asset that has a data source supported.")


def _validate_if_asset_is_not_a_local_asset(asset_details: dict) -> None:
    """
    Validate if the asset chosen is a local asset or not.
    If the asset is a local asset, we do not support creating data product from it.
    """
    for attachment in asset_details.get("asset", {}).get("attachments", []):
        if attachment.get("asset_type", "") == "data_asset":
            if (not attachment.get("connection_id") and not attachment.get("is_remote")) or \
            ("-datacatalog-" in attachment.get("connection_path", "") and "/data_asset/" in attachment.get("connection_path", "")):
                LOGGER.error("Asset is a local asset, so not supported.")
                raise ServiceError("The selected asset is a local asset and is not part of a connection asset, and hence this cannot be a data product. " \
                                            "Please select a different asset.")


def _extract_connection_id_from_attachments(attachments: list[dict]) -> str:
    """
    Extract connection_id from attachments list.
    
    Args:
        attachments: List of attachment dictionaries
        
    Returns:
        Connection ID if found, empty string otherwise
    """
    for attachment in attachments:
        if attachment.get("asset_type") == "data_asset":
            return attachment.get("connection_id", "")
    return ""


def _process_search_result(result: dict, source_to_target_map: dict[str, dict]) -> None:
    """
    Process a single search result and update the source_to_target_map.
    
    Args:
        result: Search result dictionary
        source_to_target_map: Map to update with found assets
    """
    metadata = result.get("metadata", {})
    if not isinstance(metadata, dict):
        return
    
    source_asset = metadata.get("source_asset")
    if not isinstance(source_asset, dict):
        return
        
    source_asset_id = source_asset.get("asset_id")
    target_asset_id = metadata.get("asset_id")
    
    if not (source_asset_id and target_asset_id):
        return
        
    # Only keep the first copy found for each source asset (avoid duplicates)
    if source_asset_id in source_to_target_map:
        return
        
    connection_id = _extract_connection_id_from_attachments(result.get("attachments", []))
    
    source_to_target_map[source_asset_id] = {
        "target_asset_id": target_asset_id,
        "connection_id": connection_id
    }
    LOGGER.info(f"Found existing copied asset: {source_asset_id} -> {target_asset_id} (connection: {connection_id})")


@auto_context
async def find_existing_copied_assets(
    source_asset_ids: list[str],
    dph_catalog_id: str
) -> dict[str, dict]:
    """
    Find existing copied assets in DPH catalog using source_asset_id field.
    
    Uses Lucene query to search for assets that were previously copied from the given source assets.
    This enables idempotent retry by reusing existing copies instead of creating duplicates.
    
    Args:
        source_asset_ids: List of source asset IDs to search for
        dph_catalog_id: The DPH catalog ID where copied assets are stored
        
    Returns:
        Dictionary mapping source_asset_id -> asset info dict with:
            - target_asset_id: The copied asset ID in DPH catalog
            - connection_id: The connection ID (if available)
    """
    if not source_asset_ids:
        return {}
    
    # Build Lucene query: asset.source_asset_id:(id1 id2 id3)
    source_ids_query = " ".join(source_asset_ids)
    query = f"asset.source_asset_id:({source_ids_query})"
    
    LOGGER.info(f"Searching for existing copied assets for {len(source_asset_ids)} source asset(s)")
    LOGGER.debug(f"Lucene query: {query}")
    
    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}/v2/asset_types/data_asset/search",
            params={"catalog_id": dph_catalog_id, "hide_deprecated_response_fields": False},
            json={"query": query, "include": "entity,attachments"},
            tool_name="find_existing_copied_assets"
        )
        
        # Parse response and build mapping
        source_to_target_map = {}
        response_dict = cast(dict[str, Any], response)
        results = cast(list[dict[str, Any]], response_dict.get("results", []))
        
        for result in results:
            _process_search_result(result, source_to_target_map)
        
        found_count = len(source_to_target_map)
        total_count = len(source_asset_ids)
        LOGGER.info(f"Found {found_count} existing copied asset(s) out of {total_count}")
        
        return source_to_target_map
        
    except Exception as e:
        # If search fails, log warning and return empty dict (will copy all assets)
        LOGGER.warning(f"Failed to search for existing copied assets: {e}. Will proceed with copying all assets.")
        return {}


def _validate_bulk_copy_response_has_no_errors(responses: list[dict], asset_ids: list[str]) -> None:
    """
    Validate that bulk copy responses contain no errors.
    
    Args:
        responses: List of response dictionaries from bulk copy API
        asset_ids: Original list of asset IDs being copied
        
    Raises:
        ServiceError: If any response contains errors
    """
    for idx, resp in enumerate(responses):
        if resp.get('errors'):
            asset_id = asset_ids[idx] if idx < len(asset_ids) else "unknown"
            LOGGER.error(f"Error copying asset {asset_id}: {resp.get('errors')}")
            raise ServiceError(f"Failed to copy asset {asset_id}: {resp.get('errors')}")


def _parse_copied_asset_from_response(resp: dict, asset_ids: list[str], idx: int) -> dict:
    """
    Parse and validate copied asset information from a single bulk copy response.
    
    Args:
        resp: Single response dictionary from bulk copy API
        asset_ids: Original list of asset IDs being copied
        idx: Index of current response
        
    Returns:
        Dictionary containing source_asset_id, target_asset_id, and connection_id
        
    Raises:
        ServiceError: If response is missing required fields or data
    """
    asset_id = asset_ids[idx] if idx < len(asset_ids) else "unknown"
    
    copied_assets_list = resp.get("copied_assets", [])
    if not copied_assets_list:
        LOGGER.error(f"No copied_assets in response for asset {asset_id}: {resp}")
        raise ServiceError(f"Failed to copy asset {asset_id}: No copied_assets in response")
    
    copied_asset_info = copied_assets_list[0]
    if not copied_asset_info.get("source_asset_id") or not copied_asset_info.get("target_asset_id"):
        LOGGER.error(f"Invalid copied_asset_info for asset {asset_id}: {copied_asset_info}")
        raise ServiceError(
            f"Failed to copy asset {asset_id}: Missing source_asset_id or target_asset_id in response"
        )
    
    return {
        "source_asset_id": copied_asset_info.get("source_asset_id"),
        "target_asset_id": copied_asset_info.get("target_asset_id"),
        "connection_id": copied_asset_info.get("target_connection_id", "")
    }


@auto_context
async def batch_copy_assets_to_dph_catalog(
    asset_ids: list[str], container_id: str, container_type: str, dph_catalog_id: str
) -> list[dict]:
    """
    Copy multiple assets from the same container to DPH catalog in a single batch operation.
    
    Args:
        asset_ids: List of asset IDs to copy
        container_id: The source container ID
        container_type: The source container type ('catalog' or 'project')
        dph_catalog_id: The target DPH catalog ID
        
    Returns:
        List of copied asset results, one per input asset
        
    Raises:
        ServiceError: If any asset copy fails
    """
    LOGGER.info(f"Batch copying {len(asset_ids)} assets from {container_type}:{container_id} to DPH catalog")
    
    payload = {
        "catalog_id": dph_catalog_id,
        "copy_configurations": [{"asset_id": asset_id} for asset_id in asset_ids],
    }
    query_params: dict[str, bool | str] = {"auto_copy_connections_in_remote_attachments": True}
    if container_type == "catalog":
        query_params["catalog_id"] = container_id
    else:
        query_params["project_id"] = container_id

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/assets/bulk_copy",
        params=query_params,
        json=payload,
        tool_name="import_remote_assets_to_dph_catalog",
    )
    response_dict = cast(dict[str, Any], response)
    responses = cast(list[dict[str, Any]], response_dict.get("responses", []))
    
    # Validate all responses for errors first
    _validate_bulk_copy_response_has_no_errors(responses, asset_ids)
    
    # Extract and build copied asset details from each response
    copied_assets = [
        _parse_copied_asset_from_response(resp, asset_ids, idx)
        for idx, resp in enumerate(responses)
    ]
    
    LOGGER.info(f"Successfully batch copied {len(copied_assets)} assets")
    return copied_assets


@auto_context
async def batch_copy_assets_with_deduplication(
    asset_ids: list[str],
    container_id: str,
    container_type: str,
    dph_catalog_id: str
) -> list[dict]:
    """
    Copy assets to DPH catalog, reusing existing copies if they exist.
    
    This function makes the copy operation idempotent by:
    1. Searching for assets that were already copied (using source_asset_id)
    2. Only copying assets that don't exist yet
    3. Combining existing + newly copied assets in the result
    
    Args:
        asset_ids: List of source asset IDs to copy
        container_id: Source container ID (catalog or project)
        container_type: Source container type ('catalog' or 'project')
        dph_catalog_id: Target DPH catalog ID
        
    Returns:
        List of asset info dicts with target_asset_id for each source asset.
        Each dict contains:
        - target_asset_id: The asset ID in DPH catalog
        - source_asset_id: The original source asset ID (if available)
        - reused_existing: Boolean indicating if asset was reused (True) or newly copied (False)
        
    Raises:
        ServiceError: If bulk copy fails for any asset
    """
    LOGGER.info(f"Starting batch copy with deduplication for {len(asset_ids)} asset(s)")
    
    # Step 1: Check for existing copied assets
    existing_copies = await find_existing_copied_assets(asset_ids, dph_catalog_id)
    
    # Step 2: Identify assets that need to be copied
    assets_to_copy = [aid for aid in asset_ids if aid not in existing_copies]
    
    if not assets_to_copy:
        LOGGER.info(f"All {len(asset_ids)} asset(s) already exist in DPH catalog, skipping copy")
        # Return existing asset info with reused flag
        return [
            {
                "target_asset_id": existing_copies[aid]["target_asset_id"],
                "source_asset_id": aid,
                "connection_id": existing_copies[aid].get("connection_id", ""),
                "reused_existing": True
            }
            for aid in asset_ids
        ]
    
    LOGGER.info(
        f"Reusing {len(existing_copies)} existing asset(s), "
        f"copying {len(assets_to_copy)} new asset(s)"
    )
    
    # Step 3: Bulk copy only the assets that don't exist
    newly_copied = await batch_copy_assets_to_dph_catalog(
        assets_to_copy, container_id, container_type, dph_catalog_id
    )
    
    # Step 4: Build complete result list combining existing + newly copied
    # Create a map of newly copied assets for quick lookup
    newly_copied_map = {}
    for idx, copied in enumerate(newly_copied):
        # Try to get source_asset_id from the copied asset metadata
        source_id = copied.get("source_asset_id")
        if not source_id:
            # Fallback: match by position in assets_to_copy list
            if idx < len(assets_to_copy):
                source_id = assets_to_copy[idx]
                LOGGER.warning(
                    f"Asset copy response missing source_asset_id at index {idx}, "
                    f"using fallback mapping to {source_id}"
                )
        
        if source_id:
            newly_copied_map[source_id] = copied
    
    # Build final result maintaining original order
    result = []
    for asset_id in asset_ids:
        if asset_id in existing_copies:
            # Use existing copied asset
            result.append({
                "target_asset_id": existing_copies[asset_id]["target_asset_id"],
                "source_asset_id": asset_id,
                "connection_id": existing_copies[asset_id].get("connection_id", ""),
                "reused_existing": True
            })
        elif asset_id in newly_copied_map:
            # Use newly copied asset
            copied_info = newly_copied_map[asset_id].copy()
            copied_info["source_asset_id"] = asset_id
            copied_info["reused_existing"] = False
            result.append(copied_info)
        else:
            # This shouldn't happen, but handle gracefully
            LOGGER.error(
                f"Asset {asset_id} not found in existing or newly copied assets. "
                f"Existing copies: {list(existing_copies.keys())}, "
                f"Newly copied map: {list(newly_copied_map.keys())}, "
                f"Assets to copy: {assets_to_copy}"
            )
            raise ServiceError(
                f"Failed to copy or find asset {asset_id}. "
                f"The asset was not in existing copies and was not successfully copied. "
                f"This may indicate an issue with the bulk copy API response."
            )
    
    LOGGER.info(
        f"Batch copy with deduplication complete: {len(existing_copies)} reused, "
        f"{len(assets_to_copy)} newly copied, {len(result)} total"
    )
    return result


@auto_context
async def _validate_if_connection_credentials_are_available(connection_id: str | None) -> None:
    """
    Validate if the connection has functional credentials available on the DPH side.
    It is mandatory to have functional credentials on the DPH side for each connection.
    
    Args:
        connection_id: The connection ID to validate
        
    Raises:
        ServiceError: If connection_id is empty or credentials are not available
    """
    if not connection_id:
        LOGGER.info("No connection_id provided for credential validation - asset may not have a connection")
        return

    dph_catalog_id = await get_dph_catalog_id_for_user()
    
    query_params = {
        "catalog_id": dph_catalog_id,
        "caller": True
    }
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/connections/{connection_id}/get_credentials",
        params=query_params,
        tool_name="import_remote_assets_to_dph_catalog",
    )
    response_dict = cast(dict[str, Any], response)
    if not response_dict.get("caller", False):
        LOGGER.error("DPH Functional credentials are not added for this connection.")
        query_params = {
            "catalog_id": dph_catalog_id,
            "tearsheet_mode": True,
            "entity_product": "cpd,dph"
        }
        redirect_url = f"{tool_helper_service.ui_base_url}/connections/{connection_id}?{urlencode(query_params)}"
        error_message = f"Functional credentials for this connection is not found to be added on Data Product Hub. " \
                        f"Please add and verify connection by clicking this link {redirect_url} in order to add this asset from this connection to a data product."
        raise ServiceError(error_message)


async def create_asset_revision(target_asset_id: str, dph_catalog_id: str):
    """Create a revision for the copied asset."""
    payload = {"commit_message": "copy asset to dpx"}
    await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/assets/{target_asset_id}/revisions?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=payload,
        tool_name="import_remote_assets_to_dph_catalog",
    )



async def _batch_fetch_all_asset_details(
    assets_by_container: dict[tuple[str, str], list[tuple[int, Any]]]
) -> dict[str, dict]:
    """
    Batch fetch asset details for all assets grouped by container.
    
    Args:
        assets_by_container: Assets grouped by (container_id, container_type)
        
    Returns:
        Dictionary mapping asset_id to asset details
    """
    all_asset_details: dict[str, dict] = {}
    
    for container_key, asset_group in assets_by_container.items():
        container_id, container_type = container_key
        asset_ids = [asset_info.asset_id for _, asset_info in asset_group]
        
        LOGGER.info(f"Batch fetching details for {len(asset_ids)} asset(s) from {container_type}:{container_id}")
        
        # Handle chunking if more than 20 assets from same container
        for i in range(0, len(asset_ids), 20):
            chunk = asset_ids[i:i+20]
            chunk_details = await batch_get_asset_details(chunk, container_id, container_type)
            all_asset_details.update(chunk_details)
    
    return all_asset_details


async def _perform_duplicate_check_if_needed(
    request: ImportRemoteAssetsToDphCatalogRequest,
    dph_catalog_id: str
) -> dict[str, dict]:
    """
    Perform batch duplicate check if force=False.
    
    Args:
        request: Import request
        dph_catalog_id: DPH catalog ID
        
    Returns:
        Dictionary mapping asset_id to duplicate data product info
    """
    if request.force:
        return {}
    
    source_asset_ids = [asset_info.asset_id for asset_info in request.assets]
    LOGGER.info(f"Performing batch duplicate check for {len(source_asset_ids)} asset(s)")
    
    duplicate_map = await batch_check_for_duplicate_data_products_by_source_asset_ids(
        source_asset_ids, dph_catalog_id
    )
    
    if duplicate_map:
        LOGGER.warning(f"Found {len(duplicate_map)} asset(s) already in data products")
    
    return duplicate_map


async def _validate_single_asset(
    idx: int,
    asset_info: Any,
    asset_count: int,
    all_asset_details: dict[str, dict],
    duplicate_map: dict[str, dict],
    force: bool
) -> tuple[dict | None, dict | None]:
    """
    Validate a single asset and return validation result.
    
    Args:
        idx: Asset index (1-based)
        asset_info: Asset information
        asset_count: Total asset count
        all_asset_details: Map of asset_id to asset details
        duplicate_map: Map of asset_id to duplicate info
        force: Whether to force import
        
    Returns:
        Tuple of (source_asset_details, validation_error_dict or None)
    """
    LOGGER.info(f"Validating asset {idx}/{asset_count}: {asset_info.asset_id} from {asset_info.container_type}:{asset_info.container_id}")
    
    try:
        # Get asset details from batch-fetched map
        source_asset_details = all_asset_details.get(asset_info.asset_id)
        if not source_asset_details:
            raise ServiceError(f"Failed to fetch details for asset {asset_info.asset_id}")
        
        # Validate asset is not a local asset
        _validate_if_asset_is_not_a_local_asset(source_asset_details)
        
        # Get and validate datasource type
        connection_id = _get_connection_id(source_asset_details)
        datasource_type = await get_datasource_type_from_connection(
            connection_id, asset_info.container_id, asset_info.container_type
        )
        await _validate_if_datasource_type_is_supported(datasource_type)
        
        # Extract asset name for use in validation messages
        source_asset_name = source_asset_details.get("asset", {}).get("metadata", {}).get("name", "")
        
        # Check if this asset is in the duplicate map (batch check done before loop)
        if not force:
            duplicate = duplicate_map.get(asset_info.asset_id)
            if duplicate:
                error_msg = (
                    f"Source asset '{source_asset_name}' (ID: {asset_info.asset_id}) "
                    f"already exists in data product:\n"
                    f"  - {duplicate['name']} (ID: {duplicate['data_product_id']}, "
                    f"State: {duplicate['state']})\n\n"
                    f"This prevents creating multiple data products from the same source asset.\n"
                    f"To import anyway, set force=true"
                )
                raise ServiceError(error_msg)
        
        LOGGER.info(f"Asset {idx}/{asset_count} passed validation: {source_asset_name}")
        return source_asset_details, None
        
    except Exception as e:
        # Collect validation error
        source_asset_name = (
            all_asset_details.get(asset_info.asset_id, {})
            .get("asset", {})
            .get("metadata", {})
            .get("name", asset_info.asset_id)
        )
        error_dict = {
            "asset_name": source_asset_name,
            "asset_id": asset_info.asset_id,
            "container_id": asset_info.container_id,
            "container_type": asset_info.container_type,
            "index": idx,
            "error": str(e),
            "error_type": type(e).__name__
        }
        LOGGER.error(f"Asset {idx}/{asset_count} failed validation: {source_asset_name} - {e}")
        return None, error_dict


async def _validate_all_assets(
    request: ImportRemoteAssetsToDphCatalogRequest,
    all_asset_details: dict[str, dict],
    duplicate_map: dict[str, dict],
    asset_count: int
) -> tuple[dict[tuple[str, str], list[tuple[int, Any, dict]]], list[dict], list[dict]]:
    """
    Validate all assets and group validated ones by container.
    
    Args:
        request: Import request
        all_asset_details: Map of asset_id to asset details
        duplicate_map: Map of asset_id to duplicate info
        asset_count: Total asset count
        
    Returns:
        Tuple of (assets_by_container_with_details, validation_errors, validated_assets)
        
    Raises:
        ServiceError: If any validation fails
    """
    assets_by_container_with_details: dict[tuple[str, str], list[tuple[int, Any, dict]]] = defaultdict(list)
    validation_errors = []
    validated_assets = []
    
    for idx, asset_info in enumerate(request.assets, 1):
        source_asset_details, error_dict = await _validate_single_asset(
            idx, asset_info, asset_count, all_asset_details, duplicate_map, request.force
        )
        
        if error_dict:
            validation_errors.append(error_dict)
        else:
            # Validation passed - source_asset_details should not be None here
            # If it is None, that's a bug in _validate_single_asset
            assert source_asset_details is not None, f"Bug: source_asset_details is None but no error for asset {asset_info.asset_id}"
            source_asset_name = source_asset_details.get("asset", {}).get("metadata", {}).get("name", "")
            container_key = (asset_info.container_id, asset_info.container_type)
            assets_by_container_with_details[container_key].append((idx, asset_info, source_asset_details))
            validated_assets.append({
                "asset_name": source_asset_name,
                "asset_id": asset_info.asset_id,
                "container_id": asset_info.container_id,
                "container_type": asset_info.container_type,
                "index": idx
            })
    
    # Check if any validation failed - fail before any state changes
    if validation_errors:
        error_summary = _format_error_report(
            errors=validation_errors,
            successes=validated_assets,
            total_count=asset_count,
            phase="Validation",
            state_changed=False
        )
        LOGGER.error(error_summary)
        raise ServiceError(error_summary)
    
    LOGGER.info(f"All {asset_count} asset(s) passed validation")
    return assets_by_container_with_details, validation_errors, validated_assets


async def _fetch_connection_id_from_target_asset(
    target_asset_id: str,
    dph_catalog_id: str
) -> str:
    """
    Fetch connection_id from target asset's attachments.
    
    Args:
        target_asset_id: Target asset ID
        dph_catalog_id: DPH catalog ID
        
    Returns:
        Connection ID if found, empty string otherwise
    """
    LOGGER.info(f"Connection ID not in copy result, fetching from target asset {target_asset_id}")
    target_asset_details = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/v2/assets/{target_asset_id}",
        params={"catalog_id": dph_catalog_id},
        tool_name="import_remote_assets_to_dph_catalog",
    )
    target_asset_dict = cast(dict[str, Any], target_asset_details)
    
    # Extract connection_id from attachments
    attachments = target_asset_dict.get("attachments", [])
    for attachment in attachments:
        if attachment.get("object_key_is_read_only"):
            conn_id = attachment.get("connection_id")
            if conn_id:
                LOGGER.info(f"Found connection_id from target asset: {conn_id}")
                return conn_id
    
    return ""


async def _process_copied_asset_for_revision(
    idx: int,
    asset_info: Any,
    source_asset_details: dict,
    copied_result: dict,
    container_id: str,
    container_type: str,
    dph_catalog_id: str,
    asset_count: int
) -> tuple[dict | None, dict | None]:
    """
    Process a copied asset: validate connection and create revision.
    
    Args:
        idx: Asset index
        asset_info: Asset information
        source_asset_details: Source asset details
        copied_result: Result from batch copy
        container_id: Container ID
        container_type: Container type
        dph_catalog_id: DPH catalog ID
        asset_count: Total asset count
        
    Returns:
        Tuple of (asset_data_for_part_creation or None, error_dict or None)
    """
    source_asset_name = source_asset_details.get("asset", {}).get("metadata", {}).get("name", "")
    target_asset_id = copied_result.get("target_asset_id", "")
    source_asset_id = asset_info.asset_id
    
    try:
        # Get connection_id from copied result, or fetch from target asset if not available
        connection_id = copied_result.get("connection_id", "")
        
        # If connection_id is empty, fetch it from the target asset metadata
        if not connection_id:
            connection_id = await _fetch_connection_id_from_target_asset(target_asset_id, dph_catalog_id)
        else:
            LOGGER.info(f"Got connection_id from copy result: {connection_id}")
        
        # Validate connection credentials
        await _validate_if_connection_credentials_are_available(connection_id)
        
        # Create revision for the copied asset
        await create_asset_revision(target_asset_id, dph_catalog_id)
        
        # Collect for batch part asset creation
        asset_data = {
            "idx": idx,
            "asset_name": source_asset_name,
            "target_asset_id": target_asset_id,
            "source_asset_id": source_asset_id,
            "container_id": container_id,
            "container_type": container_type
        }
        
        LOGGER.info(f"Validated and created revision for asset {idx}/{asset_count}: {source_asset_name}")
        return asset_data, None
        
    except Exception as e:
        # Log error but continue processing other assets
        error_info = {
            "asset_name": source_asset_name,
            "source_asset_id": source_asset_id,
            "target_asset_id": target_asset_id,
            "container_id": container_id,
            "container_type": container_type,
            "index": idx,
            "error": str(e),
            "error_type": type(e).__name__
        }
        LOGGER.error(
            f"Failed to validate/create revision for asset {idx}/{asset_count} '{source_asset_name}': {e}"
        )
        return None, error_info


def _process_part_asset_creation_results(
    assets_for_part_creation: list[dict],
    part_results: list[dict],
    asset_count: int
) -> tuple[list[str], list[dict], list[dict]]:
    """
    Process results from batch part asset creation.
    
    Args:
        assets_for_part_creation: List of asset data for part creation
        part_results: Results from batch part asset creation
        asset_count: Total asset count
        
    Returns:
        Tuple of (target_asset_ids, successfully_processed, processing_errors)
    """
    target_asset_ids = []
    successfully_processed = []
    processing_errors = []
    
    for asset_data, part_result in zip(assets_for_part_creation, part_results):
        if part_result["success"]:
            # Success - add to processed lists
            target_asset_ids.append(asset_data["target_asset_id"])
            successfully_processed.append({
                "asset_name": asset_data["asset_name"],
                "source_asset_id": asset_data["source_asset_id"],
                "target_asset_id": asset_data["target_asset_id"],
                "container_id": asset_data["container_id"],
                "container_type": asset_data["container_type"],
                "index": asset_data["idx"]
            })
            LOGGER.info(
                f"Successfully processed asset {asset_data['idx']}/{asset_count}: "
                f"{asset_data['asset_name']} (target: {asset_data['target_asset_id']})"
            )
        else:
            # Part asset creation failed
            error_info = {
                "asset_name": asset_data["asset_name"],
                "source_asset_id": asset_data["source_asset_id"],
                "target_asset_id": asset_data["target_asset_id"],
                "container_id": asset_data["container_id"],
                "container_type": asset_data["container_type"],
                "index": asset_data["idx"],
                "error": part_result["error"],
                "error_type": "PartAssetCreationError"
            }
            processing_errors.append(error_info)
            LOGGER.error(
                f"Failed to create part asset for {asset_data['idx']}/{asset_count} "
                f"'{asset_data['asset_name']}': {part_result['error']}"
            )
    
    return target_asset_ids, successfully_processed, processing_errors


async def _process_container_assets(
    container_key: tuple[str, str],
    asset_group: list[tuple[int, Any, dict]],
    dph_catalog_id: str,
    asset_count: int
) -> tuple[list[str], list[dict], list[dict]]:
    """
    Process all assets from a single container: copy, validate, create revisions, and part assets.
    
    Args:
        container_key: Tuple of (container_id, container_type)
        asset_group: List of (idx, asset_info, source_asset_details) tuples
        dph_catalog_id: DPH catalog ID
        asset_count: Total asset count
        
    Returns:
        Tuple of (target_asset_ids, successfully_processed, processing_errors)
    """
    container_id, container_type = container_key
    LOGGER.info(f"Batch copying {len(asset_group)} asset(s) from {container_type}:{container_id}")
    
    # Batch copy assets with deduplication (reuses existing copies if they exist)
    copied_results = await batch_copy_assets_with_deduplication(
        [asset_info.asset_id for _, asset_info, _ in asset_group],
        container_id,
        container_type,
        dph_catalog_id
    )
    
    # Validate connections and create revisions for all copied assets
    assets_for_part_creation = []
    processing_errors = []
    
    for (idx, asset_info, source_asset_details), copied_result in zip(asset_group, copied_results):
        asset_data, error_dict = await _process_copied_asset_for_revision(
            idx, asset_info, source_asset_details, copied_result,
            container_id, container_type, dph_catalog_id, asset_count
        )
        
        if error_dict:
            processing_errors.append(error_dict)
        else:
            assets_for_part_creation.append(asset_data)
    
    # Batch create part assets and relationships for all validated assets
    target_asset_ids = []
    successfully_processed = []
    
    if assets_for_part_creation:
        LOGGER.info(f"Batch creating {len(assets_for_part_creation)} part asset(s) and relationships")
        
        # Prepare data for batch operation
        asset_names_and_ids = [
            (asset_data["asset_name"], asset_data["target_asset_id"])
            for asset_data in assets_for_part_creation
        ]
        
        try:
            # Batch create all part assets and relationships
            part_results = await batch_create_part_assets_and_set_relationships(
                asset_names_and_ids,
                dph_catalog_id
            )
            
            # Process results
            target_ids, success_list, error_list = _process_part_asset_creation_results(
                assets_for_part_creation, part_results, asset_count
            )
            target_asset_ids.extend(target_ids)
            successfully_processed.extend(success_list)
            processing_errors.extend(error_list)
                    
        except Exception as e:
            # Batch operation failed entirely - mark all as failed
            LOGGER.error(f"Batch part asset creation failed: {e}")
            for asset_data in assets_for_part_creation:
                error_info = {
                    "asset_name": asset_data["asset_name"],
                    "source_asset_id": asset_data["source_asset_id"],
                    "target_asset_id": asset_data["target_asset_id"],
                    "container_id": asset_data["container_id"],
                    "container_type": asset_data["container_type"],
                    "index": asset_data["idx"],
                    "error": f"Batch operation failed: {str(e)}",
                    "error_type": "BatchOperationError"
                }
                processing_errors.append(error_info)
    
    return target_asset_ids, successfully_processed, processing_errors


@auto_context
async def _import_remote_assets_to_dph_catalog(
    request: ImportRemoteAssetsToDphCatalogRequest,
) -> ImportRemoteAssetsToDphCatalogResponse:
    """
    Import remote assets from catalogs/projects to DPH catalog.
    
    This tool performs all the heavy lifting:
    1. Validates source assets
    2. Checks for duplicates (if force=False)
    3. Batch copies assets to DPH catalog
    4. Creates revisions
    5. Creates part assets and relationships
    
    Returns target_asset_ids that can be used to create data products.
    """
    asset_count = len(request.assets)
    asset_summary = ", ".join([f"{a.asset_id} from {a.container_type}:{a.container_id}" for a in request.assets[:3]])
    if asset_count > 3:
        asset_summary += f" and {asset_count - 3} more"
    
    start_time = time.time()
    LOGGER.info(
        f"Starting import of {asset_count} asset(s) to DPH catalog: {asset_summary}, force={request.force}"
    )
    
    # Step 1: Get DPH catalog ID
    dph_catalog_id = await get_dph_catalog_id_for_user()
    LOGGER.info(f"Using DPH catalog: {dph_catalog_id}")

    # Step 2: Group assets by container for batch processing
    assets_by_container: dict[tuple[str, str], list[tuple[int, Any]]] = defaultdict(list)
    for idx, asset_info in enumerate(request.assets, 1):
        container_key = (asset_info.container_id, asset_info.container_type)
        assets_by_container[container_key].append((idx, asset_info))
    
    # Step 3: Batch fetch asset details by container
    all_asset_details = await _batch_fetch_all_asset_details(assets_by_container)
    
    # Step 4: Batch duplicate check BEFORE validation loop
    duplicate_map = await _perform_duplicate_check_if_needed(request, dph_catalog_id)
    
    # Step 5: Validate all assets - collect all validation errors
    assets_by_container_with_details, _, _ = await _validate_all_assets(
        request, all_asset_details, duplicate_map, asset_count
    )
    
    # Step 6: Batch copy assets by container and process them
    target_asset_ids = []
    processing_errors = []
    successfully_processed = []
    
    for container_key, asset_group in assets_by_container_with_details.items():
        target_ids, success_list, error_list = await _process_container_assets(
            container_key, asset_group, dph_catalog_id, asset_count
        )
        target_asset_ids.extend(target_ids)
        successfully_processed.extend(success_list)
        processing_errors.extend(error_list)
    
    # Check if any processing failed
    if processing_errors:
        error_summary = _format_error_report(
            errors=processing_errors,
            successes=successfully_processed,
            total_count=asset_count,
            phase="Import",
            state_changed=True
        )
        LOGGER.error(error_summary)
        raise ServiceError(error_summary)
    
    end_time = time.time()
    duration = end_time - start_time
    
    LOGGER.info(f"Successfully imported all {asset_count} asset(s) to DPH catalog")
    LOGGER.info(f"Total import time: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    
    message = f"Successfully imported {asset_count} asset(s) to DPH catalog in {duration:.2f} seconds"
    
    return ImportRemoteAssetsToDphCatalogResponse(
        message=message,
        target_asset_ids=target_asset_ids,
        asset_count=asset_count
    )


@service_registry.tool(
    name="data_product_import_remote_assets_to_dph_catalog",
    description=(
        "Import remote assets from catalogs or projects to the DPH (Data Product Hub) catalog. "
        "This tool validates assets, checks for duplicates, copies them to DPH catalog, "
        "creates revisions, and sets up part assets with relationships. "
        "Returns target_asset_ids that can be used to create data products. "
        "Use this tool BEFORE creating a data product to prepare the assets."
    ),
    tags={"data_product", "import", "dph_catalog"},
    meta={"version": "1.0", "service": "data_product"}
)
async def import_remote_assets_to_dph_catalog(
    input: ImportRemoteAssetsToDphCatalogRequest
) -> ImportRemoteAssetsToDphCatalogResponse:
    """
    Import remote assets to DPH catalog.
    
    This is the first step in creating a data product. It handles all the heavy lifting
    of copying assets, creating revisions, and setting up relationships.
    """
    return await _import_remote_assets_to_dph_catalog(input)
