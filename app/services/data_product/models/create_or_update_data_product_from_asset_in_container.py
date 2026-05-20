# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field, field_validator
from app.shared.models import BaseResponseModel


class CreateOrUpdateDataProductFromAssetInContainerRequest(BaseModel):
    """Request model for creating or updating data product from DPH catalog assets."""
    name: str | None = Field(
        default=None,
        description="The name of the data product. Required for CREATE operations. Read the value from user."
    )
    description: str | None = Field(
        default=None,
        description="The description of the data product. Required for CREATE operations. Read the value from user."
    )
    target_asset_ids: list[str] = Field(
        description=(
            "List of target asset IDs in DPH catalog to be added to the data product. "
            "These should be the asset IDs returned from import_remote_assets_to_dph_catalog tool. "
            "Provide at least one asset ID."
        )
    )
    existing_data_product_draft_id: str | None = Field(
        default=None,
        description=(
            "The ID of the existing data product draft. "
            "Provide this field ONLY if adding assets to an existing draft (UPDATE operation). "
            "Leave as None for CREATE operations."
        )
    )

    @field_validator('target_asset_ids')
    @classmethod
    def validate_target_asset_ids_not_empty(cls, v):
        """Ensure target_asset_ids list is not empty and does not exceed maximum limit."""
        if not v or len(v) == 0:
            raise ValueError("target_asset_ids must contain at least one asset ID")
        if len(v) > 5:
            raise ValueError("target_asset_ids cannot contain more than 5 asset IDs. Please process assets in batches of 5 or fewer.")
        return v


class CreateOrUpdateDataProductFromAssetInContainerResponse(BaseResponseModel):
    """Response model for creating or updating data product."""
    message: str = Field(..., description="Success message of the create/update operation")
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft created or updated"
    )
    contract_terms_id: str = Field(
        ...,
        description="The ID of the contract terms of the data product draft"
    )
    url: str = Field(..., description="The URL of the data product draft")

