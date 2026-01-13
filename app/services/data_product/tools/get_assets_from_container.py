# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Literal

from app.core.registry import service_registry
from app.services.data_product.models.get_assets_from_container import (
    Asset,
    GetAssetsFromContainerRequest,
    GetAssetsFromContainerResponse,
)
from app.core.auth import get_bss_account_id
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.data_product.utils.common_utils import get_dph_default_project_id


@service_registry.tool(
    name="data_product_get_assets_from_container",
    description="""
    This tool gets assets from container. The container can be one of "catalog" or "project" - always ask container_type from user.
    This is also called as the first step to create a data product from asset in container.
    If you want to create a data product from asset in catalog, call
        - data_product_get_assets_from_container tool with request.container_type="catalog"
        - data_product_create_or_update_from_asset_in_container tool with request.container_type="catalog" and other parameters.
    If you want to create a data product from asset in project, call
        - data_product_get_assets_from_container tool with request.container_type="project"
        - data_product_create_or_update_from_asset_in_container tool with request.container_type="project" and other parameters.  
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def get_assets_from_container(
    request: GetAssetsFromContainerRequest
) -> GetAssetsFromContainerResponse:
    # step 1: get assets from container
    LOGGER.info(f"In the data_product_get_assets_from_container tool, getting assets from container_type {request.container_type}.")
    payload = {}
    if request.container_type == "catalog":
        payload = await get_assets_from_catalog_payload()
    else:
        payload = await get_assets_from_project_payload()

    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v3/search",
        json=payload,
        tool_name="data_product_get_assets_from_container",
    )
    number_of_responses = response["size"]
    if number_of_responses > 0:
        if request.container_type == "catalog":
            assets = []
            for row in response["rows"]:
                assets.append(
                    Asset(
                        name=row["metadata"]["name"],
                        id=row["artifact_id"],
                        catalog_id=row["entity"]["assets"]["catalog_id"],
                    )
                )
        else:
            assets = []
            for row in response["rows"]:
                assets.append(
                    Asset(
                        name=row["metadata"]["name"],
                        id=row["artifact_id"],
                        project_id=row["entity"]["assets"]["project_id"],
                    )
                )
    else:
        assets = [] 

    LOGGER.info(f"In the data_product_get_assets_from_container tool, {len(assets)} assets found in the {request.container_type}.")
    return GetAssetsFromContainerResponse(
        message=f"There are {len(assets)} assets found in the {request.container_type}.",
        assets=assets,
    )


async def get_assets_from_catalog_payload() -> dict:
    return {
        "query": {
            "bool": {
                "must": [
                    {
                        "gs_user_query": {
                            "search_string": "*",
                            "search_fields": [
                                "metadata.name",  # NOSONAR
                                "metadata.description",  # NOSONAR
                                "metadata.tags",  # NOSONAR
                            ],
                            "nlq_analyzer_enabled": True,
                            "semantic_expansion_enabled": True,
                        }
                    },
                    {"term": {"metadata.artifact_type": "data_asset"}},  # NOSONAR
                    {"exists": {"field": "entity.assets.catalog_id"}},  # NOSONAR
                ],
                "must_not": [
                    {"exists": {"field": "entity.assets.project_id"}},  # NOSONAR
                    {"term": {"entity.assets.rov.privacy": "private"}},
                ],
                "filter": [
                    {"terms": {"metadata.artifact_type": ["data_asset"]}},  # NOSONAR
                    {"terms": {"tenant_id": [await get_bss_account_id()]}},
                ],
            }
        },
        "size": 100,
        "aggregations": {
            "owners": {"terms": {"field": "entity.assets.rov.owners"}},
            "catalogs": {"terms": {"field": "entity.assets.catalog_id"}},  # NOSONAR
        },
    }

async def get_assets_from_project_payload() -> dict:
    bss_account_id = await get_bss_account_id()
    return {
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
                    {"exists": {"field": "entity.assets.project_id"}},
                ],
                "must_not": [
                    {"exists": {"field": "entity.assets.catalog_id"}},
                    {"term": {"entity.assets.rov.privacy": "private"}},
                    {
                        "term": {
                            "entity.assets.project_id": await get_dph_default_project_id(
                                bss_account_id
                            )
                        }
                    },
                ],
                "filter": [
                    {
                        "terms": {
                            "metadata.artifact_type": [
                                "data_asset",
                                "notebook",
                                "ibm_document_library",
                            ]
                        }
                    },
                    {"terms": {"tenant_id": [bss_account_id]}},
                ],
            }
        },
        "size": 100,
        "aggregations": {
            "owners": {"terms": {"field": "entity.assets.rov.owners"}},
            "projects": {"terms": {"field": "entity.assets.project_id"}},
        },
    }

@service_registry.tool(
    name="data_product_get_assets_from_container",
    description="""
    This tool gets assets from container. The container can be one of "catalog" or "project" - always ask container_type from user.
    This is called as the first step to create a data product from asset in container.
    If you want to create a data product from asset in catalog, call
        - data_product_get_assets_from_container tool with container_type="catalog"
        - data_product_create_or_update_from_asset_in_container tool with container_type="catalog"
    If you want to create a data product from asset in project, call
        - data_product_get_assets_from_container tool with container_type="project"
        - data_product_create_or_update_from_asset_in_container tool with container_type="project"
    
    Args:
        container_type (Literal["catalog", "project"]): Where to search - either 'project' or 'catalog'. This is a mandatory field.
    """,
    tags={"create", "data_product"},
    meta={"version": "1.0", "service": "data_product"},
)
@auto_context
async def wxo_get_assets_from_container(
    container_type: Literal["catalog", "project"]
) -> GetAssetsFromContainerResponse:

    # Call the original get_assets_from_container function
    return await get_assets_from_container(
        GetAssetsFromContainerRequest(
            container_type=container_type
            )
    )
    
