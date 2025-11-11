# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import List, Optional

from app.services.lineage.models.lineage_asset import LineageAsset


class SearchLineageAssetsRequest(BaseModel):
    """Request model for searching specific name in the lineage of asset"""

    name_query: str = Field(
        "*",
        description="Search text for asset names - exact matches appear first, followed by partial matches",
    )
    is_operational: bool = Field(
        False,
        description="Filters assets based on whether the asset has asset type which belongs to the operational asset types.",
    )
    tag: Optional[str] = Field(
        None,
        description="Filters assets by tags.",
    )
    data_quality_operator: Optional[str] = Field(
        None,
        description="""a comparison operator for quality score (greater, lesser, or symbols like >, <, <=). The accepted values are:
            1) equals
            2) greater_than
            3) greater_than_or_equal
            4) less_than
            5) less_than_or_equal""",
    )
    data_quality_value: float = Field(
        0.0,
        description="a numerical value assotiated with quality score.",
    )
    business_term: Optional[str] = Field(
        None,
        description="Business term provided by the user.",
    )
    business_classification: Optional[str] = Field(
        None,
        description="Business classification provided by the user.",
    )
    technology_name: Optional[str] = Field(
        None,
        description="Fill this optional value ONLY with the name of technology passed by the user.",
    )
    asset_type: Optional[str] = Field(
        None,
        description="Fill this optional value ONLY with the type of asset passed by the user",
    )


class SearchLineageAssetsResponse(BaseModel):
    """Search lineage assets response  model"""

    lineage_assets: List[LineageAsset] = Field(
        ..., description="List of lineage assets."
    )
    response_is_complete: bool
