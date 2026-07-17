# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Optional


class AddAssetToProjectRequest(BaseModel):
    """Request model for adding a catalog asset reference to a project."""

    asset_id_or_name: str = Field(
        ...,
        description="The ID (UUID) or name of the catalog asset to add to the project"
    )
    project_id_or_name: str = Field(
        ...,
        description="The ID or name of the target project where the asset will be added"
    )
    catalog_id_or_name: Optional[str] = Field(
        default=None,
        description="Optional ID or name of the catalog containing the asset. Required when asset_id_or_name is provided as a name. If asset_id_or_name is a UUID and this field is omitted, accessible catalogs are searched to locate the asset."
    )


class AddAssetToProjectResponse(BaseResponseModel):
    """Response model describing the created project asset reference."""

    asset_id: str = Field(
        ...,
        description="The ID of the asset that was added to the project"
    )
    asset_name: str = Field(
        ...,
        description="The name of the asset that was added"
    )
    project_id: str = Field(
        ...,
        description="The ID of the project where the asset was added"
    )
    project_name: str = Field(
        ...,
        description="The name of the project"
    )
    catalog_id: str = Field(
        ...,
        description="The ID of the catalog containing the source asset"
    )
    catalog_name: str = Field(
        ...,
        description="The name of the catalog"
    )
    asset_url: str = Field(
        ...,
        description="URL to access the asset in the project"
    )
    message: str = Field(
        default="Asset successfully added to project",
        description="Success message"
    )

# Made with Bob
