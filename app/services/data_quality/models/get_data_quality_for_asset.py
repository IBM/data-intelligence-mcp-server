from pydantic import BaseModel, Field
from typing import Literal

from .data_quality import DataQuality


class GetDataQualityForAssetRequest(BaseModel):
    """Request model for get_data_quality_for_asset."""

    asset_id: str = Field(
        ..., description="UUID of the asset to retrieve quality metrics for."
    )
    asset_name: str = Field(
        ..., description="Name of the asset (used for display and verification)."
    )
    container_id: str = Field(
        ..., description="UUID of the project or catalog containing the asset."
    )
    container_type: Literal["catalog", "project"] = Field(
        ..., description="Type of container - either 'catalog' or 'project'."
    )


class GetDataQualityForAssetResponse(BaseModel):
    """Response model for get_data_quality_for_asset."""

    data_quality: DataQuality = Field(
        ..., description="Object containing quality metrics for the asset."
    )
