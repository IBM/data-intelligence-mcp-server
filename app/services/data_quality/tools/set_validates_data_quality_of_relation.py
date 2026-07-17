# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated

from pydantic import Field
from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context

from app.services.data_quality.models.set_validates_data_quality_of_relation import (
    SetValidatesDataQualityOfRelationRequest,
    SetValidatesDataQualityOfRelationResponse,
)

from app.services.data_quality.utils.data_quality_common_utils import (
    set_validates_data_quality_of_relation as set_validates_data_quality_of_relation_util,
)


async def _set_validates_data_quality_of_relation(
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
    description="""Use this tool when you need to establishes a relationship between a data quality rule and a column in a data asset within a project. This relationship is used to report the data quality score for the specified column using the logic defined in the data quality rule. The tool returns details of the data quality rule, including its ID, project ID, UI URL, and name.

Returns: The rule ID, project ID, UI URL, and name of the data quality rule.

Raises:
    ToolProcessFailedError: If the data quality rule relation set operation fails.
    ExternalServiceError: If the data quality rule service request fails.""",
    tags={"update", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
    annotations={
        "title": "Establish Relationship Between Data Quality Rule and Data Asset Column",
        "destructiveHint": True
    }
)
@auto_context
async def set_validates_data_quality_of_relation(
    project_id_or_name: Annotated[str, Field(description="The ID or name of the project containing the data quality rule. Examples: 'customer_analytics_project', 'financial_reporting_2023', 'supply_chain_optimization'")],
    data_quality_rule_id_or_name: Annotated[str, Field(description="The ID or name of the data quality rule to execute. Examples: 'validate_customer_email_format', 'check_sales_transaction_completeness', 'verify_inventory_data_consistency'")],
    data_asset_id_or_name: Annotated[str, Field(description="The ID or name of the data asset. Examples: 'customer_data_2023', 'sales_records_q2', 'inventory_management'")],
    column_name: Annotated[str, Field(description="The name of column. Examples: 'customer_id', 'transaction_date', 'product_category'")],
) -> SetValidatesDataQualityOfRelationResponse:
    """
    Wrapper that builds request model and delegates to main tool.
    """
    request = SetValidatesDataQualityOfRelationRequest(
        project_id_or_name=project_id_or_name,
        data_quality_rule_id_or_name=data_quality_rule_id_or_name,
        data_asset_id_or_name=data_asset_id_or_name,
        column_name=column_name,
    )
    return await _set_validates_data_quality_of_relation(request)
