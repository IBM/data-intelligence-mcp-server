# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated, Optional

from pydantic import Field
from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context

from app.services.data_quality.utils.data_quality_common_utils import (
    list_data_quality_rules as list_data_quality_rules_util,
)

from app.services.data_quality.models.find_data_quality_rules import (
    FindDataQualityRulesRequest,
    FindDataQualityRulesResponse,
    DataQualityRuleInfo,
)


async def _find_data_quality_rules(request: FindDataQualityRulesRequest) -> FindDataQualityRulesResponse:
    """
    Find data quality rules in the given project.
    """
    LOGGER.info(
        "Finding data quality rules: project_id_or_name=%s data_quality_rule_name=%s",
        request.project_id_or_name,
        request.data_quality_rule_name
    )

    result = await list_data_quality_rules_util(
        project_id_or_name=request.project_id_or_name,
        data_quality_rule_name=request.data_quality_rule_name,
    )

    # Convert result list to response format
    if result:
        rules = [
            DataQualityRuleInfo(
                data_quality_rule_id=rule.data_quality_rule_id,
                project_id=rule.project_id,
                data_quality_rule_ui_url=rule.data_quality_rule_ui_url,
                data_quality_rule_name=rule.data_quality_rule_name,
            )
            for rule in result
        ]
        return FindDataQualityRulesResponse(rules=rules, message=None)
    else:
        # Empty list - no rules found
        return FindDataQualityRulesResponse(
            rules=[],
            message="No data quality rules found"
        )


@service_registry.tool(
    name="list_data_quality_rules",
    annotations={
        "readOnlyHint": True,
        "title": "List Data Quality Rules in Project"
    },
    description="""Use this tool when you need to find data quality rules in the given project. If data quality rule name is not provided, then return all the data quality rules from this project.

Do NOT use for running/executing rules (use run_data_quality_rule instead).
Do NOT use for creating, updating, or deleting rules.

Returns:A list of objects, each containing the rule ID, project ID, UI URL, and name. If no data quality rules are found, the tool returns an empty list with a message.

Raises:
    ToolProcessFailedError: If the data quality rule find fails.
    ExternalServiceError: If the data quality rule find service request fails.""",
    tags={"find", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def list_data_quality_rules(
    project_id_or_name: Annotated[str, Field(description="The ID or name of the project. Examples: 'customer_analytics_project', 'financial_reporting_2023', 'supply_chain_optimization'")],
    data_quality_rule_name: Annotated[Optional[str], Field(description="The name of the data quality rule to find. If this is not provided, return all the data quality rules. This parameter is optional. Examples: 'validate_customer_email_format', 'check_sales_transaction_completeness', 'verify_inventory_data_consistency'")] = None,
) -> FindDataQualityRulesResponse:
    """
    Wrapper that builds request model and delegates to main tool.
    """
    request = FindDataQualityRulesRequest(
        project_id_or_name=project_id_or_name,
        data_quality_rule_name=data_quality_rule_name,
    )
    return await _find_data_quality_rules(request)
