# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Literal, Optional

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


def _format_data_quality_for_table(response) -> list:
    return [
        {
            "Report URL": ui_message_context.create_markdown_link(response.report_url, "Link"),
            "Overall": response.overall,
            "Consistency": response.consistency,
            "Validity": response.validity,
            "Completeness": response.completeness,
        }
    ]


@service_registry.tool(
    name="get_data_quality_for_asset",
    description="""Retrieve data quality metrics and information for a specific asset. This tool fetches quality metrics for a data asset, including overall quality score and specific dimensions like consistency, validity, and completeness. This information helps assess the reliability and usability of the data.

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
async def get_data_quality_for_asset(request: GetDataQualityForAssetRequest) -> GetDataQualityForAssetResponse:
    """
    Retrieve data quality metrics and information for a specific asset.
    """
    LOGGER.info(
        "Getting data quality for asset: asset_id_or_name=%s container_id_or_name=%s container_type=%s",
        request.asset_id_or_name,
        request.container_id_or_name,
        request.container_type
    )

    data_quality = await get_data_quality_for_asset_util(
        asset_id_or_name=request.asset_id_or_name,
        container_id_or_name=request.container_id_or_name,
        container_type=request.container_type,
    )
    
    report_url = ui_message_context.extend_url_with_context(data_quality.report_url)

    response = GetDataQualityForAssetResponse(
        overall=data_quality.overall,
        consistency=data_quality.consistency,
        validity=data_quality.validity,
        completeness=data_quality.completeness,
        report_url=report_url,
    )

    ui_message_context.add_table_ui_message(
        tool_name="get_data_quality_for_asset",
        formatted_data=_format_data_quality_for_table(response),
        title="Data Quality",
    )

    return response


@service_registry.tool(
    name="get_data_quality_for_asset",
    description="""Watsonx Orchestrator compatible wrapper for get_data_quality_for_asset.
    
Retrieve data quality metrics and information for a specific asset. This tool fetches quality metrics for a data asset, including overall quality score and specific dimensions like consistency, validity, and completeness.

Args:
    asset_id_or_name (str): Asset UUID or name.
    container_id_or_name (str): Project or catalog UUID or name.
    container_type (Literal["project", "catalog"]): Type of container. Must be either 'catalog' or 'project'.

Returns:
    GetDataQualityForAssetResponse: Quality metrics including overall, consistency, validity, completeness scores and report URL.""",
    tags={"get", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def wxo_get_data_quality_for_asset(
    asset_id_or_name: str,
    container_id_or_name: str,
    container_type: Literal["catalog", "project"],
) -> GetDataQualityForAssetResponse:
    """
    Watsonx Orchestrator wrapper: builds request model and delegates to main tool.
    """
    request = GetDataQualityForAssetRequest(
        asset_id_or_name=asset_id_or_name,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
    )
    return await get_data_quality_for_asset(request)

