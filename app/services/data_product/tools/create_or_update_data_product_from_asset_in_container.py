# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import time
from typing import Any, cast

from app.core.registry import service_registry
from app.services.data_product.models.create_or_update_data_product_from_asset_in_container import (
    CreateOrUpdateDataProductFromAssetInContainerRequest,
    CreateOrUpdateDataProductFromAssetInContainerResponse,
)
from app.services.data_product.utils.common_utils import get_data_product_url, get_dph_catalog_id_for_user
from app.services.data_product.utils.data_product_creation_utils import (
    is_data_product_draft_create,
    validate_inputs_for_draft_create,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service

@auto_context
async def _create_or_update_data_product_from_asset_in_container(
    request: CreateOrUpdateDataProductFromAssetInContainerRequest,
) -> CreateOrUpdateDataProductFromAssetInContainerResponse:
    """
    Create or update a data product using pre-imported DPH catalog assets.
    
    This tool expects target_asset_ids from the import_remote_assets_to_dph_catalog tool.
    It only handles data product creation/update, not asset import.
    """
    asset_count = len(request.target_asset_ids)
    asset_summary = ", ".join(request.target_asset_ids[:3])
    if asset_count > 3:
        asset_summary += f" and {asset_count - 3} more"
    
    LOGGER.info(
        f"Creating/updating data product with {asset_count} DPH catalog asset(s): {asset_summary}"
    )
    
    # Step 1: Determine operation type and validate inputs
    is_create = is_data_product_draft_create(request)
    if is_create:
        LOGGER.info("Operation type: CREATE new data product draft")
        await validate_inputs_for_draft_create(request, "name", "description")
    else:
        LOGGER.info(f"Operation type: UPDATE existing draft {request.existing_data_product_draft_id}")

    # Step 2: Get DPH catalog ID
    dph_catalog_id = await get_dph_catalog_id_for_user()
    
    # Use the provided target_asset_ids directly (they're already in DPH catalog)
    target_asset_ids = request.target_asset_ids

    # Step 3: Create or update data product with all assets
    if is_create:
        # This is not adding data asset item operation, so creating data product draft.
        payload = get_data_product_draft_method_creation_payload(
            dph_catalog_id, target_asset_ids, request
        )
        
        # Log timing for data product draft creation
        start_time = time.time()
        LOGGER.info(
            f"Starting data product draft creation with {asset_count} asset(s) at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}"
        )
        
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products",
            json=payload,
            tool_name="data_product_create_or_update_from_asset_in_container",
        )
        
        end_time = time.time()
        duration = end_time - start_time
        LOGGER.info(
            f"Completed data product draft creation at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}"
        )
        LOGGER.info(
            f"Data product draft creation took {duration:.2f} seconds ({duration/60:.2f} minutes)"
        )
        message = f"Created data product draft with {asset_count} data asset item(s) successfully."
        response_dict = cast(dict[str, Any], response)
        draft = cast(list[dict[str, Any]], response_dict.get("drafts", []))[0]
    else:
        # Draft exists already. The task is to add data asset items to the existing draft.
        payload = get_patch_data_asset_items_to_draft_payload(
            dph_catalog_id, target_asset_ids
        )
        response = await tool_helper_service.execute_patch_request(
            url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.existing_data_product_draft_id}",
            json=payload,
            tool_name="data_product_create_or_update_from_asset_in_container",
        )
        LOGGER.info(
            f"In the data_product_create_or_update_from_asset_in_container tool, patched data product draft with {asset_count} data asset item(s)."
        )
        message = f"Updated data product draft with {asset_count} data asset item(s) successfully."
        draft = cast(dict[str, Any], response)

    data_product_draft_id = request.existing_data_product_draft_id if request.existing_data_product_draft_id else draft["id"]
    contract_terms_id = draft["contract_terms"][0]["id"]

    return CreateOrUpdateDataProductFromAssetInContainerResponse(
        message=message,
        data_product_draft_id=data_product_draft_id,
        contract_terms_id=contract_terms_id,
        url=get_data_product_url(data_product_draft_id, "draft")
    )


def get_data_product_draft_method_creation_payload(
    dph_catalog_id: str, data_asset_ids: list[str], request: CreateOrUpdateDataProductFromAssetInContainerRequest
) -> dict:
    """
    Generate payload for creating a data product draft with multiple assets.
    
    Args:
        dph_catalog_id: The DPH catalog ID
        data_asset_ids: List of asset IDs to include in the data product
        request: The request containing data product information
        
    Returns:
        Payload dictionary for the API request
    """
    parts_out = [
        {
            "asset": {
                "id": asset_id,
                "container": {"id": dph_catalog_id},
            }
        }
        for asset_id in data_asset_ids
    ]
    
    return {
        "drafts": [
            {
                "asset": {"container": {"id": dph_catalog_id}},
                "version": None,
                "data_product": None,
                "name": request.name,
                "description": request.description,
                "types": None,
                "dataview_enabled": False,
                "parts_out": parts_out,
            }
        ]
    }


def get_patch_data_asset_items_to_draft_payload(
    dph_catalog_id: str, data_asset_ids: list[str]
) -> list[dict]:
    """
    Generate payload for patching a data product draft with multiple assets.
    
    Args:
        dph_catalog_id: The DPH catalog ID
        data_asset_ids: List of asset IDs to add to the data product
        
    Returns:
        List of patch operations for the API request
    """
    return [
        {
            "op": "add",
            "path": "/parts_out/-",
            "value": {
                "asset": {
                    "id": asset_id,
                    "container": {
                        "id": dph_catalog_id,
                        "type": "catalog"
                    },
                    "type": "data_asset"
                },
                "delivery_methods": []
            }
        }
        for asset_id in data_asset_ids
    ]


@service_registry.tool(
    name="data_product_create_or_update_from_asset_in_container",
    description="""
    This tool creates or updates a data product draft using pre-imported DPH catalog assets.
    
    IMPORTANT: This tool expects target_asset_ids from the import_remote_assets_to_dph_catalog tool.
    It does NOT import assets - use import_remote_assets_to_dph_catalog first to prepare assets.
    If any asset import fails during import_remote_assets_to_dph_catalog tool call, DO NOT call this tool.
    
    Workflow:
    1. Call import_remote_assets_to_dph_catalog to import and prepare assets
    2. Use the returned target_asset_ids with this tool to create/update the data product
    
    Example 1 - Create a data product draft with imported assets:
        target_asset_ids=["dph-asset-id-1", "dph-asset-id-2"]
        name="Customer Analytics Data Product"
        description="Consolidated customer data for analytics"
        
    Example 2 - Add assets to an existing data product draft:
        target_asset_ids=["dph-asset-id-3"]
        existing_data_product_draft_id="existing-draft-id-123"

    Args:
        name (str | None): The name of the data product. Required for CREATE operations.
        description (str | None): The description of the data product. Required for CREATE operations.
        target_asset_ids (list[str]): List of DPH catalog asset IDs (from import_remote_assets_to_dph_catalog tool).
        existing_data_product_draft_id (str | None, optional): The ID of the existing data product draft. Provide only for UPDATE operations.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def create_or_update_data_product_from_asset_in_container(
    target_asset_ids: list[str],
    name: str | None = None,
    description: str | None = None,
    existing_data_product_draft_id: str | None = None,
) -> CreateOrUpdateDataProductFromAssetInContainerResponse:
    """Create or update a data product draft using pre-imported DPH catalog assets."""
    
    request = CreateOrUpdateDataProductFromAssetInContainerRequest(
        name=name,
        description=description,
        target_asset_ids=target_asset_ids,
        existing_data_product_draft_id=existing_data_product_draft_id,
    )

    # Call the internal implementation
    return await _create_or_update_data_product_from_asset_in_container(request)
