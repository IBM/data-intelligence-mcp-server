# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field, field_validator
from app.shared.models import BaseResponseModel
from typing import Literal


class AssetInContainer(BaseModel):
    """Represents an asset within a container (catalog or project)."""
    asset_id: str = Field(
        description="The ID of the asset selected from container (catalog/project) to be imported to DPH catalog."
    )
    container_id: str = Field(
        description="The ID of the container (catalog/project) that the asset belongs to."
    )
    container_type: Literal["catalog", "project"] = Field(
        description="The type of container - either 'project' or 'catalog'."
    )


class ImportRemoteAssetsToDphCatalogRequest(BaseModel):
    """Request model for importing remote assets to DPH catalog."""
    assets: list[AssetInContainer] = Field(
        description="List of assets to be imported to DPH catalog. Each asset can be from a different container (catalog or project). Provide at least one asset."
    )
    force: bool = Field(
        default=False,
        description="If True, imports assets even if they already exist in data products. If False (default), checks for duplicates and fails if found."
    )

    @field_validator('assets')
    @classmethod
    def validate_assets_not_empty(cls, v):
        """Ensure assets list is not empty and does not exceed maximum limit."""
        if not v or len(v) == 0:
            raise ValueError("assets must contain at least one asset")
        if len(v) > 5:
            raise ValueError("assets cannot contain more than 5 assets. Please process assets in batches of 5 or fewer.")
        return v


class ImportRemoteAssetsToDphCatalogResponse(BaseResponseModel):
    """Response model for importing remote assets to DPH catalog."""
    message: str = Field(..., description="Success message of the import operation")
    target_asset_ids: list[str] = Field(
        ...,
        description="List of target asset IDs in DPH catalog. Use these IDs to create data products."
    )
    asset_count: int = Field(..., description="Number of assets successfully imported")

