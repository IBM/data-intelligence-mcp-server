# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service


@service_registry.tool(
    name="search_categories",
    description="""Searches for user's categories.
                    This function is mainly used when a user want to create or update a metadata enrichment (MDE) and does not provide a category.
                    This function should be used to retrieve the list of categories and surface them back to the user so he can choose one of them""",
)
@auto_context
async def search_categories() -> List[str]:
    auth_scope = "category"
    LOGGER.info("Starting searching categories...")
    payload = {
        "size": 10000,
        "from": 0,
        "_source": [
            "artifact_id",
            "metadata.name",
            "metadata.description",
            "metadata.modified_by",
            "categories",
            "entity.artifacts.artifact_id"
        ],
        "query": {
            "bool": {
                "filter": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "metadata.artifact_type": "category",
                                },
                            },
                        ],
                    },
                },
            },
        },
    }
    params = {"auth_scope": auth_scope}

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        params=params,
        json=payload,
    )
    search_response = response.get("rows", [])
    categories = list(map(lambda x: x["metadata"]["name"], search_response)) if search_response else []
    return categories


@service_registry.tool(
    name="search_categories",
    description="""Searches for user's categories.
                    This function is mainly used when a user want to create or update a metadata enrichment (MDE) and does not provide a category.
                    This function should be used to retrieve the list of categories and surface them back to the user so he can choose one of them""",
)
@auto_context
async def wxo_search_categories() -> List[str]:

    return await search_categories()