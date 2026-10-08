# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated, Any

from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.services.metadata_enrichment.models.metadata_enrichment import CategoryInfo
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.helpers import is_uuid_bool
from app.shared.utils.tool_helper_service import tool_helper_service

_MAX_CATEGORIES = 50


def _format_categories_for_table(categories_data: list[CategoryInfo]) -> list[dict]:
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


async def _search_categories(category_contains: str | None = None) -> list[CategoryInfo] | str:
    auth_scope = "category"
    LOGGER.info("Starting searching categories...")

    must_clauses: list[dict[str, Any]] = [
        {
            "term": {
                "metadata.artifact_type": "category",
            },
        },
    ]

    if category_contains:
        if is_uuid_bool(category_contains):
            must_clauses.append(
                {
                    "wildcard": {
                        "artifact_id": {
                            "value": f"{category_contains}",
                            "case_insensitive": True,
                        }
                    }
                }
            )
        else:
            must_clauses.append(
                {
                    "wildcard": {
                        "metadata.name.keyword": {
                            "value": f"*{category_contains}*",
                            "case_insensitive": True,
                        }
                    }
                }
            )

    payload = {
        "size": _MAX_CATEGORIES + 1,
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
                        "must": must_clauses,
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
    total_size = response.get("size", 0)

    if total_size > _MAX_CATEGORIES:
        filter_hint = f" matching '{category_contains}'" if category_contains else ""
        return (
            f"Too many categories found{filter_hint} ({total_size} total). "
            f"Please re-call this tool with a more specific `category_contains` value to narrow down the results "
            f"(e.g. category_contains='revenue' to find categories whose names contain 'revenue')."
        )

    categories: list[CategoryInfo] = [
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
    description="""Use this tool when you need to retrieve the available business glossary categories from IBM Data Intelligence.
                    Returns a flat list of category names and their IDs that can be used to scope governance workflows, metadata enrichment jobs, or term assignments.
                    The tool accepts an optional category_contains parameter to filter results:
                    - To look up a category by UUID, pass the full UUID string directly as category_contains (e.g. category_contains='01dbeeb5-e085-4f27-b5ab-84b3d74cc086').
                    - To search by name, pass a substring (case-insensitive) as category_contains (e.g. category_contains='revenue').
                    - If no filter is provided, all categories are returned (up to 50).
                    Present the list to the user and ask them to select one or more before proceeding with any downstream operation.
                    Return: A list of categories and the category IDs. ALWAYS include ALL fields in your response: name and category_id.""",
)
@auto_context
async def list_glossary_categories(
    category_contains: Annotated[str | None, Field(description="Optional filter. Pass a full UUID to look up a category by ID (e.g. '01dbeeb5-e085-4f27-b5ab-84b3d74cc086'), or a name substring to search by name (e.g. 'revenue'). Leave empty to list all categories.")] = None
) -> list[CategoryInfo] | str:

    return await _search_categories(category_contains=category_contains)
