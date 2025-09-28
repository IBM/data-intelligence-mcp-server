from typing import Any, List

from ..models.search_asset import SearchAssetRequest, SearchAssetResponse

from app.core.auth import get_access_token
from app.core.registry import service_registry
from app.core.settings import settings
from app.services.constants import ASSISTANT_BASE_ENDPOINT
from app.shared.exceptions.base import ExternalAPIError
from app.shared.utils.helpers import is_none
from app.shared.utils.http_client import get_http_client
from app.shared.logging import LOGGER, auto_context

@service_registry.tool(
        name="search_asset",
        description="""Understand user's request about searching data assets and return list of retrieved assets.
                       This function takes a user's search prompt as input and may take container type: project or catalog. Default container type to catalog.
                       It then returns list of asset that has been found""")
@auto_context
async def search_asset(request: SearchAssetRequest, ctx=None) -> List[SearchAssetResponse]:
    auth_scope = "catalog"
    if not is_none(request.container_type) and request.container_type in ["project", "catalog"]:
        auth_scope = request.container_type

    LOGGER.info("Starting asset search with prompt: '%s' and container_type: '%s'", request.search_prompt, auth_scope)

    payload = {
        "operation_type": "search",
        "search_request": {"text": request.search_prompt, "auth_scope": auth_scope},
    }

    auth = await get_access_token()

    headers = {
        "Content-Type": "application/json",
        "Authorization": auth
    }

    client = get_http_client()

    try:
        response = await client.post(settings.di_service_url + ASSISTANT_BASE_ENDPOINT, data=payload, headers=headers)

        search_response = response.get("assets")
        li = list(
            map(_construct_search_asset, search_response)
        )

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
                       It then returns list of asset that has been found""")
@auto_context
async def wxo_search_asset(
    search_prompt: str,
    container_type: str = "catalog"
) -> List[SearchAssetResponse]:
    """Watsonx Orchestrator compatible version that expands SearchAssetRequest object into individual parameters."""

    request = SearchAssetRequest(
        search_prompt=search_prompt,
        container_type=container_type
    )

    # Call the original search_asset function
    return await search_asset(request)

def _construct_search_asset(asset: Any):
    search_asset = SearchAssetResponse.model_validate(asset)
    if "<ui_base_url>" in search_asset.url:
        search_asset.url = search_asset.url.replace("<ui_base_url>", f"{settings.ui_url}")
    return search_asset
