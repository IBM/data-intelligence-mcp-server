# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Any, List

from ..models.search_asset import SearchAssetRequest, SearchAssetResponse

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import GS_BASE_ENDPOINT
from app.shared.exceptions.base import ExternalAPIError
from app.shared.utils.helpers import is_none, append_context_to_url
from app.shared.utils.http_client import get_http_client
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="search_asset",
    description="""Understand user's request about searching data assets and return list of retrieved assets.
                       This function takes a user's search prompt as input and may take container type: project or catalog. Default container type to catalog.
                       It then returns list of asset that has been found""",
)
@auto_context
async def search_asset(
    request: SearchAssetRequest, ctx=None
) -> List[SearchAssetResponse]:
    auth_scope = "catalog"
    if not is_none(request.container_type) and request.container_type in [
        "project",
        "catalog",
    ]:
        auth_scope = request.container_type

    LOGGER.info(
        "Starting asset search with prompt: '%s' and container_type: '%s'",
        request.search_prompt,
        auth_scope,
    )

    payload = {
        "query": {
            "bool": {
                "must": [
                    {
                        "gs_user_query": {
                            "search_string": request.search_prompt,
                            "semantic_search_enabled": True,
                        }
                    },
                    {"term": {"metadata.artifact_type": "data_asset"}},
                ]
            }
        }
    }

    auth = await get_access_token()

    headers = {"Content-Type": "application/json", "Authorization": auth}

    params = {"auth_scope": request.container_type} if request.container_type else {}

    client = get_http_client()

    try:
        response = await client.post(
            settings.di_service_url + GS_BASE_ENDPOINT,
            params=params,
            data=payload,
            headers=headers,
        )

        search_response = response.get("rows", [])
        li = list(map(_construct_search_asset, search_response)) if search_response else []

        return li

    except ExternalAPIError:
        # This will catch HTTP errors (4xx, 5xx) that were raised by raise_for_status()
        raise
    except Exception as e:
        raise ExternalAPIError(f"Failed to search for the assets: {str(e)}")


@service_registry.tool(
    name="search_asset",
    description="""Understand user's request about searching data assets and return list of retrieved assets.
                       This function takes a user's search prompt as input and may take container type: project or catalog. Default container type to catalog.
                       It then returns list of asset that has been found""",
)
@auto_context
async def wxo_search_asset(
    search_prompt: str, container_type: str = "catalog"
) -> List[SearchAssetResponse]:
    """Watsonx Orchestrator compatible version that expands SearchAssetRequest object into individual parameters."""

    request = SearchAssetRequest(
        search_prompt=search_prompt, container_type=container_type
    )

    # Call the original search_asset function
    return await search_asset(request)


def _construct_search_asset(row: Any):
    asset_id = row["artifact_id"]
    catalog_id = row["entity"]["assets"].get("catalog_id", None)
    project_id = row["entity"]["assets"].get("project_id", None)
    base_url = (
        f"{settings.ui_url}/data/catalogs/{catalog_id}/asset/{asset_id}"
        if catalog_id
        else f"{settings.ui_url}/projects/{project_id}/data-assets/{asset_id}"
    )

    url = append_context_to_url(base_url)

    return SearchAssetResponse(
        id=asset_id,
        name=row["metadata"]["name"],
        catalog_id=catalog_id,
        project_id=project_id,
        url=url,
    )
