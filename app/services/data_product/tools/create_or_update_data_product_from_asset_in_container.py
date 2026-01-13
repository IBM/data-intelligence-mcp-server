# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Literal
from urllib.parse import urlencode

from app.core.registry import service_registry
from app.services.data_product.models.create_or_update_data_product_from_asset_in_container import (
    CreateOrUpdateDataProductFromAssetInContainerRequest,
    CreateOrUpdateDataProductFromAssetInContainerResponse,
)
from app.shared.exceptions.base import ServiceError
from app.services.data_product.utils.common_utils import get_data_product_url, get_dph_catalog_id_for_user
from app.services.data_product.utils.data_product_creation_utils import (
    is_data_product_draft_create,
    validate_inputs_for_draft_create,
    create_part_asset_and_set_relationship,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service


@service_registry.tool(
    name="data_product_create_or_update_from_asset_in_container",
    description="""
    This tool creates a data product draft via add from a container or updates an existing draft to add a new asset from container.
    The container can be one of "catalog" or "project".
    Call this tool after calling data_product_get_assets_from_container tool.
    Example 1 - Create a data product draft:
        If you want to create a data product from asset in catalog, call
            - data_product_get_assets_from_container tool with request.container_type="catalog"
            - data_product_create_or_update_from_asset_in_container tool with request.container_type="catalog" and other parameters.
        If you want to create a data product from asset in project, call
            - data_product_get_assets_from_container tool with request.container_type="project"
            - data_product_create_or_update_from_asset_in_container tool with request.container_type="project" and other parameters.
    Example 2 - Add a data asset item to an existing data product draft:
        In this case, request.existing_data_product_draft_id is NOT null/None.
        Identifies the data product draft by request.existing_data_product_draft_id and adds the asset to the data product draft.
    
    This receives the asset ID selected by the user (from data_product_get_assets_from_container) and the container id of the selected asset (from data_product_get_assets_from_container) along with other info from user.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def create_or_update_data_product_from_asset_in_container(
    request: CreateOrUpdateDataProductFromAssetInContainerRequest,
) -> CreateOrUpdateDataProductFromAssetInContainerResponse:
    LOGGER.info(
        f"In the data_product_create_or_update_from_asset_in_container tool, creating data product from container_type {request.container_type} with name {request.name}, asset id {request.asset_id} and container id {request.container_id_of_asset}."
    )
    if is_data_product_draft_create(request):
        validate_inputs_for_draft_create(request)

    dph_catalog_id = await get_dph_catalog_id_for_user()

    target_asset_id = await create_assets_for_data_product(
        request.asset_id, request.container_id_of_asset, request.container_type
    )

    if is_data_product_draft_create(request):
        # This is not adding data asset item operation, so creating data product draft.
        payload = get_data_product_draft_method_creation_payload(
            dph_catalog_id, target_asset_id, request
        )
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products",
            json=payload,
            tool_name="data_product_create_or_update_from_asset_in_container",
        )  
        LOGGER.info(
            "In the data_product_create_or_update_from_asset_in_container tool, created data product draft."
        )
        message = "Created data product draft with the provided data asset item successfully."
        draft = response["drafts"][0]
    else:
        # Draft exists already. The task is to add data asset item to the existing draft.
        payload = get_patch_data_asset_items_to_draft_payload(
            dph_catalog_id, target_asset_id
        )
        response = await tool_helper_service.execute_patch_request(
            url=f"{tool_helper_service.base_url}/data_product_exchange/v1/data_products/-/drafts/{request.existing_data_product_draft_id}",
            json=payload,
            tool_name="data_product_create_or_update_from_asset_in_container",
        )
        LOGGER.info(
            "In the data_product_create_or_update_from_asset_in_container tool, patched data product draft with the provided data asset item."
        )
        message = "Updated data product draft with the provided data asset item successfully."
        draft = response

    data_product_draft_id = request.existing_data_product_draft_id if request.existing_data_product_draft_id else draft["id"]
    contract_terms_id = draft["contract_terms"][0]["id"]

    return CreateOrUpdateDataProductFromAssetInContainerResponse(
        message=message,
        data_product_draft_id=data_product_draft_id,
        contract_terms_id=contract_terms_id,
        url=get_data_product_url(data_product_draft_id, "draft")
    )


@auto_context
async def create_assets_for_data_product(
    asset_id: str, container_id: str, container_type: str
) -> str:
    LOGGER.info(
        f"Creating assets for data product from {container_type} with asset id {asset_id} and container id {container_id}."
    )
    dph_catalog_id = await get_dph_catalog_id_for_user()

    # getting asset details
    asset_details = await get_asset_details(asset_id, container_id, container_type)

    _validate_if_asset_is_not_a_local_asset(asset_details)

    connection_id = _get_connection_id(asset_details)

    datasource_type = await get_datasource_type_from_connection(connection_id, container_id, container_type)
    await _validate_if_datasource_type_is_supported(datasource_type)

    asset_name = asset_details.get("asset", {}).get("metadata", {}).get("name", {})

    # copying asset to dph catalog
    copied_details = await copy_asset_to_dph_catalog(
        asset_id, container_id, container_type, dph_catalog_id
    )

    connection_id = _get_connection_id(copied_details)
    await _validate_if_connection_credentials_are_available(connection_id)

    target_asset_id = copied_details.get("copied_assets", [{}])[0].get("target_asset_id", "")

    # creating asset revision
    await create_asset_revision(target_asset_id, dph_catalog_id)

    # creating ibm_data_product_part asset and setting relationship
    await create_part_asset_and_set_relationship(asset_name, target_asset_id)

    LOGGER.info(f"Returning target asset id {target_asset_id}.")
    return target_asset_id


@auto_context
async def get_asset_details(asset_id: str, container_id: str, container_type: str) -> dict:
    query_params = {
            "asset_ids": asset_id,
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
        tool_name="data_product_create_or_update_from_asset_in_container",
    )
    response = response["resources"][0]
    
    if response.get('errors'):
        LOGGER.error(f"Something happened while getting asset details: {response.get('errors')}")
        raise ServiceError(f"Something happened while getting asset details: {response.get('errors')}") 

    return response


def _get_connection_id(asset_details: dict) -> str:
    connection_id = ""
    for attachment in asset_details.get("asset", {}).get("attachments", []):
        if attachment.get("asset_type", "") == "data_asset":
            connection_id = attachment.get("connection_id")
            break
    return connection_id


@auto_context
async def get_datasource_type_from_connection(connection_id: str, container_id: str, container_type: str | None = None) -> str:
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
        tool_name="data_product_create_or_update_from_asset_in_container",
    )
    datasource_type = response.get("entity", {}).get("datasource_type", "")
    LOGGER.info(f"Datasource type found: {datasource_type}")
    return datasource_type


@auto_context
async def _validate_if_datasource_type_is_supported(datasource_type: str) -> None:
    """
    This function validates if the datasource type is supported for the asset selected.
    """
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
        tool_name="data_product_create_or_update_from_asset_in_container",
    )
    supported_datasource_types = set({resource.get("metadata", {}).get("asset_id") for resource in response["resources"]})
    if datasource_type not in supported_datasource_types:
        LOGGER.error("Data source type is not supported for the selected asset.")
        raise ServiceError("The selected asset belongs to a data source type that is not supported currently, and hence this cannot be a data product." \
        "Please select a different asset that has a data source supported.")


def _validate_if_asset_is_not_a_local_asset(asset_details: dict) -> None:
    """
    This function validates if the asset chosen is a local asset or not.
    If the asset is a local asset, we do not support creating data product from it.
    """
    for attachment in asset_details.get("asset", {}).get("attachments", []):
        if attachment.get("asset_type", "") == "data_asset":
            if (not attachment.get("connection_id") and not attachment.get("is_remote")) or \
            ("-datacatalog-" in attachment.get("connection_path", "") and "/data_asset/" in attachment.get("connection_path", "")):
                LOGGER.error("Asset is a local asset, so not supported.")
                raise ServiceError("The selected asset is a local asset and is not part of a connection asset, and hence this cannot be a data product. " \
                                            "Please select a different asset.")


@auto_context
async def copy_asset_to_dph_catalog(
    asset_id: str, container_id: str, container_type: str, dph_catalog_id: str
) -> dict:
    payload = {
        "catalog_id": dph_catalog_id,
        "copy_configurations": [{"asset_id": asset_id}],
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
        tool_name="data_product_create_or_update_from_asset_in_container",
    )
    response = response["responses"][0]

    if response.get('errors'):
        LOGGER.error(f"Something happened while copying assets: {response.get('errors')}")
        raise ServiceError(f"Something happened while copying assets: {response.get('errors')}") 
    
    return response


@auto_context
async def _validate_if_connection_credentials_are_available(connection_id: str | None) -> None:
    """
    This function validates if the connections has functional credentials available on the DPH side.
    It is mandatory to have functional credentials on the DPH side for each connection.
    """
    if not connection_id:
        return

    dph_catalog_id = await get_dph_catalog_id_for_user()
    
    query_params = {
        "catalog_id": dph_catalog_id,
        "caller": True
    }
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/data_product_exchange/v1/connections/{connection_id}/get_credentials",
        params=query_params,
        tool_name="data_product_create_or_update_from_asset_in_container",
    )
    if not response.get("caller", False):
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
    payload = {"commit_message": "copy asset to dpx"}
    await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/assets/{target_asset_id}/revisions?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=payload,
        tool_name="data_product_create_or_update_from_asset_in_container",
    )


def get_data_product_draft_method_creation_payload(
    dph_catalog_id: str, data_asset_id: str, request: CreateOrUpdateDataProductFromAssetInContainerRequest
) -> dict:
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
                "parts_out": [
                    {
                        "asset": {
                            "id": data_asset_id,
                            "container": {"id": dph_catalog_id},
                        }
                    }
                ],
            }
        ]
    }


def get_patch_data_asset_items_to_draft_payload(
    dph_catalog_id: str, data_asset_id: str
) -> list[dict]:
    return [
        {
            "op": "add",
            "path": "/parts_out/-",
            "value": {
                "asset": {
                    "id": data_asset_id,
                    "container": {
                        "id": dph_catalog_id,
                        "type": "catalog"
                    },
                    "type": "data_asset"
                },
                "delivery_methods": []
            }
        }
    ]


@service_registry.tool(
    name="data_product_create_or_update_from_asset_in_container",
    description="""
    This tool creates a data product draft via add from a container or updates an existing draft to add a new asset from container.
    The container can be one of "catalog" or "project".
    Call this tool after calling data_product_get_assets_from_container tool.
    Example 1 - Create a data product draft:
        If you want to create a data product from asset in catalog, call
            - data_product_get_assets_from_container tool with request.container_type="catalog"
            - data_product_create_or_update_from_asset_in_container tool with request.container_type="catalog" and other parameters.
        If you want to create a data product from asset in project, call
            - data_product_get_assets_from_container tool with request.container_type="project"
            - data_product_create_or_update_from_asset_in_container tool with request.container_type="project" and other parameters.
    Example 2 - Add a data asset item to an existing data product draft:
        In this case, request.existing_data_product_draft_id is NOT null/None.
        Identifies the data product draft by request.existing_data_product_draft_id and adds the asset to the data product draft.
    
    This receives the asset ID selected by the user (from data_product_get_assets_from_container) and the container id of the selected asset (from data_product_get_assets_from_container) along with other info from user.

    Args:
        name (str): The name of the data product. Read the value from user.
        description (str): The description of the data product. Read the value from user.
        asset_id (str): The ID of the asset selected from container (catalog/project) to be added to the data product.
        container_id_of_asset (str): The ID of the container (catalog/project) that the asset belongs to.
        container_type (Literal["catalog", "project"]): Where to create data product from - either 'project' or 'catalog'. This is a mandatory field.
        existing_data_product_draft_id (str | None, optional): The ID of the existing data product draft. This field is populated only if we are adding a data asset item to an existing draft, otherwise this field value is None.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_create_or_update_data_product_from_asset_in_container(
    name: str,
    description: str,
    asset_id: str,
    container_id_of_asset: str,
    container_type: Literal["catalog", "project"],
    existing_data_product_draft_id: str | None = None,
) -> CreateOrUpdateDataProductFromAssetInContainerResponse:
    """Watsonx Orchestrator compatible version that expands CreateOrUpdateDataProductFromAssetInContainerRequest object into individual parameters."""

    request = CreateOrUpdateDataProductFromAssetInContainerRequest(
        name=name,
        description=description,
        asset_id=asset_id,
        container_id_of_asset=container_id_of_asset,
        container_type=container_type,
        existing_data_product_draft_id=existing_data_product_draft_id,
    )

    # Call the original create_or_update_data_product_from_asset_in_container function
    return await create_or_update_data_product_from_asset_in_container(request)
