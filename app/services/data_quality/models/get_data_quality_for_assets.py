# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Dict, List, Literal


class GetDataQualityForAssetsRequest(BaseModel):
    """Request model for bulk data quality retrieval."""

    asset_ids_or_names: List[str] = Field(
        ...,
        description="List of asset UUIDs or names. "
        "Example: ['customer_data_2023', 'sales_records_q2', 'inventory_management']",
    )
    container_id_or_name: str = Field(
        ...,
        description="Project or catalog UUID or name. Examples: 'marketing_analytics', 'financial_reports', 'supply_chain'",
    )
    container_type: Literal["catalog", "project"] = Field(
        ...,
        description="Type of container. Must be either 'catalog' or 'project'. Enum: ['project', 'catalog']",
    )


class AssetDataQuality(BaseModel):
    """Data quality information for a single asset."""

    asset_id_or_name: str = Field(
        ..., description="Asset UUID or name as provided in the request"
    )
    overall: str = Field(..., description="Overall quality score (percentage)")
    scores_by_dimension: Dict[str, str] = Field(
        default_factory=dict,
        description="Quality scores by dimension (e.g., consistency: '96.0', validity: '95.0'). "
        "Common dimensions: consistency, validity, completeness, timeliness, accuracy",
    )
    report_url: str = Field(
        ..., description="URL to detailed quality dashboard for this asset"
    )


class GetDataQualityForAssetsResponse(BaseResponseModel):
    """Response model for bulk data quality retrieval."""

    assets: List[AssetDataQuality] = Field(
        default_factory=list,
        description="List of asset quality metrics. Only includes assets with available quality data.",
    )
    total_count: int = Field(
        ..., description="Number of assets with quality data returned"
    )
    requested_count: int = Field(..., description="Number of assets requested")
    missing_count: int = Field(..., description="Number of assets without quality data")
