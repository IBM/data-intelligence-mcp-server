# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field
from typing import List, Optional

from .lineage_asset import LineageAsset


class SearchLineageAssetsRequest(BaseModel):
    """Request model for searching specific name in the lineage of asset"""

    name_query: str = Field(
        ..., description="search name_query string in the lineage asset name"
    )
    technology_name: Optional[str] = Field(
        None,
        description="If specified, an asset should have this technology to be returned (optional)",
    )
    asset_type: Optional[str] = Field(
        None,
        description="If specified, an asset should have this type (lineage-specific type) to be returned (optional)",
    )


class SearchLineageAssetsResponse(BaseModel):
    """Search lineage assets response  model"""

    lineage_assets: List[LineageAsset] = Field(
        ..., description="List of lineage assets."
    )
    response_is_complete: bool
