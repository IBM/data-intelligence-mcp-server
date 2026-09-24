# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated, List, Literal

from pydantic import Field

from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context

from app.services.data_quality.models.get_data_quality_for_assets import (
    GetDataQualityForAssetsRequest,
    GetDataQualityForAssetsResponse,
    AssetDataQuality,
)

from app.services.data_quality.utils.data_quality_common_utils import (
    get_data_quality_for_assets as get_data_quality_for_assets_util,
)


def _format_bulk_data_quality_for_table(
    response: GetDataQualityForAssetsResponse,
) -> list:
    """
    Format bulk data quality response into a table.
    Dynamically includes all dimension scores from the scores_by_dimension dictionary.

    Args:
        response: GetDataQualityForAssetsResponse model containing data quality metrics

    Returns:
        List of formatted dictionaries for table display
    """
    formatted_rows = []
    for asset in response.assets:
        row = {
            "Asset": asset.asset_id_or_name,
            "Overall": asset.overall,
            "Report": ui_message_context.create_markdown_link(asset.report_url, "View"),
        }
        for dimension_name, score in asset.scores_by_dimension.items():
            row[dimension_name.capitalize()] = score
        formatted_rows.append(row)

    return formatted_rows


async def _get_data_quality_for_assets(
    request: GetDataQualityForAssetsRequest,
) -> GetDataQualityForAssetsResponse:
    """
    Retrieve data quality metrics for multiple assets in bulk.
    """
    LOGGER.info(
        "Getting bulk data quality for %d assets in %s %s",
        len(request.asset_ids_or_names),
        request.container_type,
        request.container_id_or_name,
    )

    results = await get_data_quality_for_assets_util(
        asset_ids_or_names=request.asset_ids_or_names,
        container_id_or_name=request.container_id_or_name,
        container_type=request.container_type,
    )

    assets = []
    for asset_name, data_quality in results.items():
        if data_quality is None:
            continue
        assets.append(
            AssetDataQuality(
                asset_id_or_name=asset_name,
                overall=data_quality.overall,
                scores_by_dimension=data_quality.scores_by_dimension,
                report_url=ui_message_context.extend_url_with_context(
                    data_quality.report_url
                ),
            )
        )

    requested_count = len(request.asset_ids_or_names)
    total_count = len(assets)
    missing_count = requested_count - total_count

    response = GetDataQualityForAssetsResponse(
        assets=assets,
        total_count=total_count,
        requested_count=requested_count,
        missing_count=missing_count,
    )

    if assets:
        ui_message_context.add_table_ui_message(
            tool_name="get_data_quality_for_assets",
            formatted_data=_format_bulk_data_quality_for_table(response),
            title=f"Data Quality for {total_count} Assets",
        )

        if missing_count > 0:
            LOGGER.warning(
                "%d/%d assets do not have data quality information",
                missing_count,
                requested_count,
            )
    else:
        LOGGER.warning(
            "No data quality information found for any of the %d requested assets",
            requested_count,
        )

    return response


@service_registry.tool(
    name="get_data_quality_for_assets",
    description="""
Retrieve data quality metrics for multiple assets in bulk. This tool fetches quality metrics for multiple data assets, including overall quality score and specific dimensions like consistency, validity, and completeness. This information helps assess the reliability and usability of the data.

You can pass either IDs or names for both assets and container.

REQUIRED: ALL THREE parameters are mandatory. Ask for any missing information:
1. asset_ids_or_names - List of data asset names/IDs (e.g., ["CustomerTable", "OrdersTable"]) - REQUIRED
2. container_id_or_name - The project or catalog name/ID (e.g., "AgentsDemo") - REQUIRED
3. container_type - Either "project" or "catalog" - REQUIRED

When asking for missing information:
- If asset names are missing: Ask "Which assets would you like to check?"
- If container is missing: Ask "Which project or catalog contains these assets?"
- If container type is missing: Ask "Are these in a project or catalog?"
- If user mentions "project" or "catalog", use that value directly

Returns: Quality metrics for all requested assets including:
- assets: list of per-asset results, each containing asset_id_or_name, overall quality score, scores_by_dimension (e.g. consistency, validity, completeness), and report_url
- total_count: number of assets with quality data returned
- requested_count: number of assets requested
- missing_count: number of assets without quality data

Raises:
    ToolProcessFailedError: If quality metrics cannot be retrieved or the service call fails.""",
    tags={"get", "data_quality", "bulk"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def get_data_quality_for_assets(
    asset_ids_or_names: Annotated[List[str], Field(description="List of asset UUIDs or names. Examples: ['customer_data_2023', 'sales_records_q2'], ['asset_uuid_1', 'asset_uuid_2']")],
    container_id_or_name: Annotated[str, Field(description="Project or catalog UUID or name. Examples: 'marketing_analytics', 'financial_reports', 'supply_chain'")],
    container_type: Annotated[Literal["catalog", "project"], Field(description="Type of container. Must be either 'catalog' or 'project'. Enum: ['project', 'catalog']")],
) -> GetDataQualityForAssetsResponse:
    """
    Wrapper that builds request model and delegates to main tool.
    """
    request = GetDataQualityForAssetsRequest(
        asset_ids_or_names=asset_ids_or_names,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
    )
    return await _get_data_quality_for_assets(request)
