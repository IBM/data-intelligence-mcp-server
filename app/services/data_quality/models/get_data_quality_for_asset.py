# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Literal, Optional


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
    """Response model for getting data quality for an asset."""
    
    overall: str = Field(..., description="Overall quality score (percentage)")
    consistency: Optional[str] = Field(None, description="Consistency score (percentage)")
    validity: Optional[str] = Field(None, description="Validity score (percentage)")
    completeness: Optional[str] = Field(None, description="Completeness score (percentage)")
    report_url: str = Field(..., description="Link to detailed quality dashboard")
