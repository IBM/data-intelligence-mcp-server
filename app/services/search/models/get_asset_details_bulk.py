# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import List, Literal, Optional
from app.services.search.models.get_asset_details import GetAssetDetailsResponse


class GetAssetDetailsForAssetsRequest(BaseModel):
    """Request model for bulk asset details retrieval."""

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


class AssetDetails(BaseModel):
    """Asset details information for a single asset."""

    asset_id_or_name: str = Field(
        ..., description="Asset UUID or name as provided in the request"
    )
    details: Optional[GetAssetDetailsResponse] = Field(
        None, description="Complete asset details including metadata, usage, ROV, etc."
    )
    error: Optional[str] = Field(
        None, description="Error message if asset details could not be retrieved"
    )


class GetAssetDetailsForAssetsResponse(BaseResponseModel):
    """Response model for bulk asset details retrieval."""

    assets: List[AssetDetails] = Field(
        default_factory=list,
        description="List of asset details. Includes both successful and failed retrievals.",
    )
    total_count: int = Field(
        ..., description="Number of assets with details successfully returned"
    )
    requested_count: int = Field(..., description="Number of assets requested")
    failed_count: int = Field(..., description="Number of assets that failed to retrieve")

# Made with Bob
