# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Literal, Optional
from datetime import datetime


from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context

from app.services.data_quality.models.get_data_quality_for_asset import (
    GetDataQualityForAssetRequest,
    GetDataQualityForAssetResponse,
)

from app.services.data_quality.utils.data_quality_common_utils import (
    get_data_quality_for_asset as get_data_quality_for_asset_util,
)


def _format_data_quality_for_table(response: GetDataQualityForAssetResponse) -> list:
    """
    Format data quality response into a table.
    Dynamically includes all dimension scores from the scores_by_dimension dictionary.
    
    Args:
        response: GetDataQualityForAssetResponse model containing data quality metrics
        
    Returns:
        List containing a single formatted dictionary for table display
    """
    formatted_row = {
        "Report URL": ui_message_context.create_markdown_link(response.report_url, "Link"),
        "Overall": response.overall,
    }
    
    # Add all dimensions dynamically, capitalizing dimension names for display
    for dimension_name, score in response.scores_by_dimension.items():
        formatted_row[dimension_name.capitalize()] = score
    
    # Add SLA assessment summary if available
    if response.sla_assessment_summary:
        summary = response.sla_assessment_summary
        formatted_row["Matching Data Quality SLAs"] = f"{summary.matching_data_quality_slas} SLA(s)"
        
        # Format violations count
        violations_count = summary.total_data_quality_sla_violations
        if violations_count > 0:
            formatted_row["Total Data Quality SLA Violations"] = f"{violations_count} violation(s)"
        else:
            formatted_row["Total Data Quality SLA Violations"] = "None"
        
        if summary.last_assessment_time:
            # Format ISO 8601 timestamp to human-readable format
            try:
                dt = datetime.fromisoformat(summary.last_assessment_time.replace('Z', '+00:00'))
                formatted_row["Last Assessment"] = dt.strftime("%B %d, %Y at %-I:%M %p %Z").replace("  ", " ")
            except (ValueError, AttributeError) as e:
                LOGGER.warning("Failed to parse timestamp %s: %s", summary.last_assessment_time, str(e))
                formatted_row["Last Assessment"] = summary.last_assessment_time
    
    return [formatted_row]

    
async def _get_data_quality_for_asset(request: GetDataQualityForAssetRequest) -> GetDataQualityForAssetResponse:
    """
    Retrieve data quality metrics and information for a specific asset.
    """
    

    data_quality = await get_data_quality_for_asset_util(
        asset_id_or_name=request.asset_id_or_name,
        container_id_or_name=request.container_id_or_name,
        container_type=request.container_type,
    )
    
    report_url = ui_message_context.extend_url_with_context(data_quality.report_url)

    response = GetDataQualityForAssetResponse(
        overall=data_quality.overall,
        scores_by_dimension=data_quality.scores_by_dimension,
        report_url=report_url,
        sla_assessment_summary=data_quality.sla_assessment_summary,
    )

    ui_message_context.add_table_ui_message(
        tool_name="get_data_quality_for_asset",
        formatted_data=_format_data_quality_for_table(response),
        title="Data Quality",
    )

    return response
    

@service_registry.tool(
    name="get_data_quality_for_asset",
    annotations={
        "readOnlyHint": True,
        "title": "Get Data Quality Metrics and Assessment Scores for Specific Asset"
    },
    description="""Wrapper for get_data_quality_for_asset.

    
Retrieve data quality metrics and information for a specific asset. This tool fetches quality metrics for a data asset, including overall quality score and specific dimensions like consistency, validity, and completeness. This information helps assess the reliability and usability of the data.

You can pass either IDs or names for both asset and container.

REQUIRED: ALL THREE parameters are mandatory. Ask for any missing information:
1. asset_id_or_name - The specific data asset name/ID (e.g., "CustomerTable") - REQUIRED
2. container_id_or_name - The project or catalog name/ID (e.g., "AgentsDemo") - REQUIRED
3. container_type - Either "project" or "catalog" - REQUIRED

When asking for missing information:
- If asset name is missing: Ask "Which asset would you like to check?"
- If container is missing: Ask "Which project or catalog contains this asset?"
- If container type is missing: Ask "Is this in a project or catalog?"
- If user mentions "project" or "catalog", use that value directly

Args:
    asset_id_or_name (str): Asset UUID or name. Examples: 'customer_data_2023', 'sales_records_q2', 'inventory_management'
    container_id_or_name (str): Project or catalog UUID or name. Examples: 'marketing_analytics', 'financial_reports', 'supply_chain'
    container_type (Literal["project", "catalog"]): Type of container. Must be either 'catalog' or 'project'. Enum: ['project', 'catalog']

Returns:
    GetDataQualityForAssetResponse: The tool returns quality metrics including overall quality score, consistency score, validity score, completeness score, and a URL to the detailed quality dashboard.

Raises:
    ToolProcessFailedError: If quality metrics cannot be retrieved or the service call fails.""",
    tags={"get", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def get_data_quality_for_asset(
    asset_id_or_name: str,
    container_id_or_name: str,
    container_type: Literal["catalog", "project"],
) -> GetDataQualityForAssetResponse:
    """
    Wrapper that builds request model and delegates to main tool.
    """
    request = GetDataQualityForAssetRequest(
        asset_id_or_name=asset_id_or_name,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
    )
    return await _get_data_quality_for_asset(request)


