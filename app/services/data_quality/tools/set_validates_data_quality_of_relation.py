# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context

from app.services.data_quality.models.set_validates_data_quality_of_relation import (
    SetValidatesDataQualityOfRelationRequest,
    SetValidatesDataQualityOfRelationResponse,
)

from app.services.data_quality.utils.data_quality_common_utils import (
    set_validates_data_quality_of_relation as set_validates_data_quality_of_relation_util,
)


@service_registry.tool(
    name="set_validates_data_quality_of_relation",
    description="""Establishes a relationship between a data quality rule and a column in a data asset within a project. This relationship is used to report the data quality score for the specified column using the logic defined in the data quality rule. The tool returns details of the data quality rule, including its ID, project ID, UI URL, and name.

Args:
    project_id_or_name (str): The ID or name of the project containing the data quality rule. Examples: 'customer_analytics_project', 'financial_reporting_2023', 'supply_chain_optimization'
    data_quality_rule_id_or_name (str): The ID or name of the data quality rule to execute. Examples: 'validate_customer_email_format', 'check_sales_transaction_completeness', 'verify_inventory_data_consistency'
    data_asset_id_or_name (str): The ID or name of the data asset. Examples: 'customer_data_2023', 'sales_records_q2', 'inventory_management'
    column_name (str): The name of column. Examples: 'customer_id', 'transaction_date', 'product_category'

Returns:
    SetValidatesDataQualityOfRelationResponse: The tool returns a DataQualityRule object containing the rule ID, project ID, UI URL, and name of the data quality rule.

Raises:
    ToolProcessFailedError: If the data quality rule relation set operation fails.
    ExternalServiceError: If the data quality rule service request fails.""",
    tags={"update", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def set_validates_data_quality_of_relation(
    request: SetValidatesDataQualityOfRelationRequest,
) -> SetValidatesDataQualityOfRelationResponse:
    """
    Sets a validates data quality of relationship from a data quality rule to a column from a data asset in a project.
    """
    LOGGER.info(
        "Setting validates data quality of relation: project=%s rule=%s asset=%s column=%s",
        request.project_id_or_name,
        request.data_quality_rule_id_or_name,
        request.data_asset_id_or_name,
        request.column_name
    )

    result = await set_validates_data_quality_of_relation_util(
        project_id_or_name=request.project_id_or_name,
        data_quality_rule_id_or_name=request.data_quality_rule_id_or_name,
        data_asset_id_or_name=request.data_asset_id_or_name,
        column_name=request.column_name,
    )

    return SetValidatesDataQualityOfRelationResponse(
        data_quality_rule_id=result.data_quality_rule_id,
        project_id=result.project_id,
        data_quality_rule_ui_url=result.data_quality_rule_ui_url,
        data_quality_rule_name=result.data_quality_rule_name,
    )


@service_registry.tool(
    name="set_validates_data_quality_of_relation",
    description="""Watsonx Orchestrator compatible wrapper for set_validates_data_quality_of_relation.

Establishes a relationship between a data quality rule and a column in a data asset within a project.

Args:
    project_id_or_name (str): The ID or name of the project containing the data quality rule.
    data_quality_rule_id_or_name (str): The ID or name of the data quality rule to execute.
    data_asset_id_or_name (str): The ID or name of the data asset.
    column_name (str): The name of column.

Returns:
    SetValidatesDataQualityOfRelationResponse: DataQualityRule object with rule details.""",
    tags={"update", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def wxo_set_validates_data_quality_of_relation(
    project_id_or_name: str,
    data_quality_rule_id_or_name: str,
    data_asset_id_or_name: str,
    column_name: str,
) -> SetValidatesDataQualityOfRelationResponse:
    """
    Watsonx Orchestrator wrapper: builds request model and delegates to main tool.
    """
    request = SetValidatesDataQualityOfRelationRequest(
        project_id_or_name=project_id_or_name,
        data_quality_rule_id_or_name=data_quality_rule_id_or_name,
        data_asset_id_or_name=data_asset_id_or_name,
        column_name=column_name,
    )
    return await set_validates_data_quality_of_relation(request)
