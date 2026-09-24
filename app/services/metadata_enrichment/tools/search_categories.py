# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.services.metadata_enrichment.models.metadata_enrichment import CategoryInfo
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.ui_message.ui_message_context import ui_message_context


def _format_categories_for_table(categories_data: List[CategoryInfo]) -> List[dict]:
    """
    Format categories for table display.

    Args:
        categories_data: List of CategoryInfo objects

    Returns:
        List of dictionaries formatted for table display with Name
    """
    return [
        {
            "Name": cat.name,
            "category_id": cat.category_id
        }
        for cat in categories_data
    ]


async def _search_categories() -> List[CategoryInfo]:
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
        "sort": [
            {"metadata.name.keyword": {"order": "asc"}}
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
    params = {"auth_scope": auth_scope, "tenant_scope": True}

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        params=params,
        json=payload,
    )
    search_response = response.get("rows", [])
    categories: List[CategoryInfo] = [
        CategoryInfo(
            category_id=row.get("artifact_id", ""),
            name=row.get("metadata", {}).get("name", ""),
        )
        for row in search_response
    ] if search_response else []

    if search_response:
        selected_data = ui_message_context.send_table_selector_msg(
            tool_name="list_glossary_categories",
            data=categories,
            formatted_data=_format_categories_for_table(categories),
            title="Available Categories",
            description="Select one or more categories to use for metadata enrichment",
            unique_keys=["Name"]
        )

        categories = selected_data if selected_data is not None else categories

    return categories


@service_registry.tool(
    name="list_glossary_categories",
    annotations={
        "readOnlyHint": True,
        "title": "List All Business Glossary Categories"
    },
    tags={"metadata_management_and_governance"},
    description="""Use this tool when you need to retrieve all available business glossary categories from IBM Data Intelligence.
                    Takes no inputs. Returns a flat list of category names and their IDs that can be used to scope governance workflows, metadata enrichment jobs, or term assignments.
                    Present the full list to the user and ask them to select one or more before proceeding with any downstream operation.
                    Return: A list of categories and the category IDs. ALWAYS include ALL fields in your response: name and category_id.""",
)
@auto_context
async def list_glossary_categories() -> List[CategoryInfo]:

    return await _search_categories()