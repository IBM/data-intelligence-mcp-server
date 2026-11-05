# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List  # noqa: I001, UP035 # Baseline
from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel, field_validator


class BulkPublishAssetsRequest(BaseModel):
    """Request model for bulk publishing assets from a metadata import."""

    project_name: str = Field(
        ..., description="Name of the project containing the metadata import"
    )
    connection_name: str = Field(
        ..., description="Name of the connection used in the metadata import"
    )
    catalog_name: str = Field(
        ..., description="Name of the catalog for publishing assets"
    )
    metadata_import_name: str = Field(
        ..., description="Name of the metadata import asset"
    )
    asset_names: List[str] = Field(  # noqa: UP006 # Baseline
        ...,
        description="List of asset names to publish. Must be a list of strings.",
        min_length=1,
    )

    @field_validator(
        "project_name", "connection_name", "catalog_name", "metadata_import_name"
    )
    @classmethod
    def validate_non_empty_string(cls, v: str, info) -> str:  # noqa: ANN001 # Baseline
        """Ensure name fields are non-empty strings."""
        if not v or not v.strip():
            field_name = info.field_name
            raise ValueError(f"{field_name} cannot be empty")
        return v.strip()

    @field_validator("asset_names")
    @classmethod
    def validate_asset_names(cls, v: List[str]) -> List[str]:  # noqa: UP006 # Baseline
        """Ensure asset_names contains no empty or whitespace-only strings."""
        for idx, name in enumerate(v):
            if not name or not name.strip():
                raise ValueError(f"asset_names[{idx}] cannot be empty")

        return [name.strip() for name in v]


class BulkPublishAssetsResponse(BaseResponseModel):
    """Response model for bulk publish assets operation."""

    message: str = Field(
        ..., description="Success message describing the operation result"
    )
    published_count: int = Field(
        ..., description="Number of assets successfully published"
    )
    project_id: str = Field(..., description="ID of the project")
    connection_id: str = Field(..., description="ID of the connection")
    catalog_id: str = Field(..., description="ID of the catalog")
    mdi_id: str = Field(..., description="ID of the metadata import")
    asset_ids: List[str] = Field(  # noqa: UP006 # Baseline
        ..., description="List of asset IDs that were published"
    )
