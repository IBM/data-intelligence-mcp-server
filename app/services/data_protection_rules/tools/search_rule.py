# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from app.core.registry import service_registry
from app.services.data_protection_rules.models.search_rule import (
    SearchDataProtectionRuleRequest,
    SearchDataProtectionRuleResponse,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings, ENV_MODE_SAAS
from app.shared.logging import LOGGER, auto_context
from app.services.constants import SEARCH_PATH
from app.shared.utils.tool_helper_service import tool_helper_service


TABLE_TITLE_DATA_PROTECTION_RULES="Data protection rules"
METADATA_NAME = "metadata.name"
METADAT_DESCRIPTION = "metadata.description"

@service_registry.tool(
    name="data_protection_rule_search",
    description="""
    This tool searches all data protection rules to return data protection rules that match the given search query.
    Example: 'Find all data protection rules with Deny name.'
    In this case, data_protection_rule_search_query is 'Deny', and this tool returns all data protection rules that have Deny in their name or description.
    Example: 'Show me all data protection rules'
    In this case, data_protection_rule_search_query is '*'.
    """,
    tags={"search", "data_protection_rules"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def search_rules(
    request: SearchDataProtectionRuleRequest,
) -> SearchDataProtectionRuleResponse:
    LOGGER.info(
        f"In the data_protection_rule_search tool, searching data protection rules with query {request.data_protection_rule_search_query}."
    )

    payload = get_dps_search_payload(
        data_protection_rule_search_query=request.data_protection_rule_search_query,
    )

    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}{SEARCH_PATH}?role=viewer&auth_scope=all&auth_cache=true",
            json=payload,
            tool_name="search_rule"
        )
        number_of_responses = response["size"]
        if number_of_responses == 0:
            LOGGER.info(
                "In the data_protection_rule_search tool, no data protection rules found."
            )
            return SearchDataProtectionRuleResponse(count=0, data_protection_rules=[])
        LOGGER.info(f"Found {number_of_responses} data protection rules.")
        data_protection_rules = []

        if settings.di_env_mode.upper() == ENV_MODE_SAAS:
            url_prefix = tool_helper_service.base_url.replace("https://api.", "https://") + "/governance/rules/dataProtection/view/"
        else:
            url_prefix = str(tool_helper_service.ui_base_url) + "/gov/rules/dataProtection/view/"
        for row in response["rows"]:
            data_protection_rules.append(
                {
                    "name": row.get("metadata", {}).get("name", ""),
                    "description": row.get("metadata", {}).get("description", ""),
                    "modified_on": row.get("metadata", {}).get("modified_on", ""),
                    "url": url_prefix + row.get("artifact_id", "")
                }
            )

        format_response = format_data_protection_rule_for_table(data_protection_rules)
        ui_message_context.add_table_ui_message(tool_name="search_data_protection_rule",
                         formatted_data=format_response, title=TABLE_TITLE_DATA_PROTECTION_RULES)
        
    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_protection_rule_search tool. Error while searching data protection rules: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to run data_protection_rule_search tool. Error while searching data protection rules: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_protection_rule_search tool. Error while searching data protection rules: {str(e)}"
        )
        raise ServiceError(
            f"Failed to run data_protection_rule_search tool. Error while searching data protection rules: {str(e)}"
        )

    return SearchDataProtectionRuleResponse(count=number_of_responses, data_protection_rules=data_protection_rules)

def format_data_protection_rule_for_table(data_protection_rules: list[dict]) -> list:
    """Format data protection rules list by changing keys to Title Case for table display."""
    return [
        {
            "Name": rule.get("name", ""),
            "Description": rule.get("description", ""),
            "Modified On": rule.get("modified_on", ""),
            "URL": rule.get("url", "")
        }
        for rule in data_protection_rules
    ]

@service_registry.tool(
    name="data_protection_rule_search",
    description="""
    This tool searches all data protection rules to return data protection rules that match the given search query.
    Example: 'Find all data protection rules with Deny name.'
    In this case, data_protection_rule_search_query is 'Deny', and this tool returns all data protection rules that have Deny in their name or description.
    Example: 'Show me all data protection rules'
    In this case, data_protection_rule_search_query is '*'.
    """,
    tags={"search", "data_protection_rules"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def wxo_search_rule(
    data_protection_rule_search_query: str
) -> SearchDataProtectionRuleResponse:
    """Watsonx Orchestrator compatible version that expands SearchDataProductsRequest object into individual parameters."""

    request = SearchDataProtectionRuleRequest(
        data_protection_rule_search_query=data_protection_rule_search_query,
    )

    # Call the original search_data_protection_rules function
    return await search_rules(request)

def get_dps_search_payload(data_protection_rule_search_query: str) -> dict:
    if data_protection_rule_search_query == "*":
        return {
            "size": 10000,
            "from": "0",
            "_source": [
                "artifact_id",
                METADATA_NAME,
                METADAT_DESCRIPTION,
                "metadata.modified_on"
            ],
            "query": {
                "bool": {
                    "must": [
                        {"match": {"provider_type_id": "dps"}},
                        {"match": {"metadata.artifact_type": "data_protection_rule"}}
                    ]
                }
            }
        }
    else:
        return {
        "size": 10000,
        "from": "0",
        "_source": [
            "artifact_id",
            METADATA_NAME,
            METADAT_DESCRIPTION,
            "metadata.modified_on"
        ],
        "query": {
            "bool": {
                "must": [
                    {"match": {"provider_type_id": "dps"}},
                    {"match": {"metadata.artifact_type": "data_protection_rule"}},
                    {
                            "gs_user_query": {
                            "search_string": data_protection_rule_search_query,
                            "semantic_search_enabled": True
                        }
                    }
                ]
            }
        }
    }
