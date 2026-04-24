# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Dict, Literal


class GetDataQualityForAssetRequest(BaseModel):
    """Request model for getting data quality for an asset."""
    
    asset_id_or_name: str = Field(
        ...,
        description="Asset UUID or name. Examples: 'customer_data_2023', 'sales_records_q2', 'inventory_management'"
    )
    container_id_or_name: str = Field(
        ...,
        description="Project or catalog UUID or name. Examples: 'marketing_analytics', 'financial_reports', 'supply_chain'"
    )
    container_type: Literal["catalog", "project"] = Field(
        ...,
        description="Type of container. Must be either 'catalog' or 'project'. Enum: ['project', 'catalog']"
    )


class GetDataQualityForAssetResponse(BaseResponseModel):
    """
    Response model for getting data quality for an asset.
    
    Uses a dictionary to store dimension scores, allowing dynamic handling of any
    data quality dimensions returned by the API without requiring model changes.
    """
    
    overall: str = Field(..., description="Overall quality score (percentage)")
    scores_by_dimension: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary of dimension names to their scores (percentages). "
                    "Common dimensions: consistency, validity, completeness, timeliness, accuracy"
    )
    report_url: str = Field(..., description="Link to detailed quality dashboard")
