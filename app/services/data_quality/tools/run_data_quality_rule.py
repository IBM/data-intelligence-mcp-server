# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Optional

from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context

from app.services.data_quality.models.run_data_quality_rule import (
    RunDataQualityRuleRequest,
    RunDataQualityRuleResponse,
)

from app.services.data_quality.utils.data_quality_common_utils import (
    run_data_quality_rule as run_data_quality_rule_util,
)

@service_registry.tool(
    name="run_data_quality_rule",
    description="""Executes a specific data quality rule and returns details about the execution. Use when the user wants to re-run a rule.
    Do NOT use when the user only wants to view rule. Do NOT use for creating, updating, or deleting rules. Do NOT call this tool for describe data quality rules.
    Do NOT use when required parameters (project_id, rule_id) are missing.
    
    Args:
        project_id_or_name (str): The ID or name of the project containing the data quality rule.
        data_quality_rule_id_or_name (str): The ID or name of the data quality rule to execute.
    
    Returns:
        RunDataQualityRuleResponse: An object containing complete information about the data quality rule:
            - data_quality_rule_id: The ID of the data quality rule
            - project_id: The ID of the project
            - data_quality_rule_ui_url: URL to view the data quality rule in the UI
            - data_quality_rule_name: The name of the data quality rule
    
    Raises:
        ToolProcessFailedError: If the data quality rule run fails.
        ExternalServiceError: If the data quality rule service request fails.""",
    tags={"run", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def run_data_quality_rule(
    request: RunDataQualityRuleRequest,
) -> RunDataQualityRuleResponse:
    """
    Executes a specific data quality rule and returns details about the execution.
    """
    LOGGER.info(
        "Running data quality rule via util: rule=%s project=%s ",
        request.data_quality_rule_id_or_name,
        request.project_id_or_name
    )
    result = await run_data_quality_rule_util(request.project_id_or_name, request.data_quality_rule_id_or_name)
    
    # Convert DataQualityRule to RunDataQualityRuleResponse
    return RunDataQualityRuleResponse(
        data_quality_rule_id=result.data_quality_rule_id,
        project_id=result.project_id,
        data_quality_rule_ui_url=result.data_quality_rule_ui_url,
        data_quality_rule_name=result.data_quality_rule_name,
    )


@service_registry.tool(
    name="run_data_quality_rule",
    description="""Executes a specific data quality rule and returns details about the execution. Use when the user wants to re-run a rule.
    Do NOT use when the user only wants to view rule. Do NOT use for creating, updating, or deleting rules. Do NOT call this tool for describe data quality rules.
    Do NOT use when required parameters (project_id, rule_id) are missing.
    
    This is a Watsonx Orchestrator compatible wrapper that accepts direct parameters instead of a request object.
    
    Args:
        project_id_or_name (str): The ID or name of the project containing the data quality rule.
        data_quality_rule_id_or_name (str): The ID or name of the data quality rule to execute.
    
    Returns:
        RunDataQualityRuleResponse: An object containing complete information about the data quality rule:
            - data_quality_rule_id: The ID of the data quality rule
            - project_id: The ID of the project
            - data_quality_rule_ui_url: URL to view the data quality rule in the UI
            - data_quality_rule_name: The name of the data quality rule
    
    Raises:
        ToolProcessFailedError: If the data quality rule run fails.
        ExternalServiceError: If the data quality rule service request fails.""",
    tags={"run", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def wxo_run_data_quality_rule(
    project_id_or_name: str,
    data_quality_rule_id_or_name: str,
) -> RunDataQualityRuleResponse:
    """
    Watsonx Orchestrator wrapper: builds request model and delegates to main tool.
    """
    request = RunDataQualityRuleRequest(
        project_id_or_name=project_id_or_name,
        data_quality_rule_id_or_name=data_quality_rule_id_or_name,
    )
    return await run_data_quality_rule(request)
