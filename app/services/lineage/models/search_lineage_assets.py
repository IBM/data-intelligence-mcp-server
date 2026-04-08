# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field, model_validator
from app.shared.models import BaseResponseModel
from typing import List, Optional

from app.services.lineage.models.lineage_asset import LineageAsset

# Sentinel value for data_quality_value indicating no value was provided
# This is outside the valid range (0.0-100.0) and is used to work around
# MCP framework serialization issues with optional parameters
SENTINEL_NO_QUALITY_VALUE = -0.01


class SearchLineageAssetsRequest(BaseModel):
    """Request model for searching specific name in the lineage of asset"""

    name_query: str = Field(
        default="*",
        description="Search text for asset names - exact matches appear first, followed by partial matches",
    )
    is_operational: Optional[bool] = Field(
        default=None,
        description="Filters assets based on whether the asset has asset type which belongs to the operational asset types.",
    )
    tag: Optional[str] = Field(
        default=None,
        description="Filters assets by tags.",
    )
    data_quality_operator: Optional[str] = Field(
        default=None,
        description="""a comparison operator for quality score (greater, lesser, or symbols like >, <, <=). The accepted values are:
            1) equals
            2) greater_than
            3) greater_than_or_equal
            4) less_than
            5) less_than_or_equal""",
    )
    data_quality_value: Optional[float] = Field(
        default=None,
        description="a numerical value associated with quality score (valid range: 0.0-100.0).",
    )
    business_term: Optional[str] = Field(
        default=None,
        description="Business term provided by the user.",
    )
    business_classification: Optional[str] = Field(
        default=None,
        description="Business classification provided by the user.",
    )
    technology_name: Optional[str] = Field(
        default=None,
        description="Fill this optional value ONLY with the name of technology passed by the user.",
    )
    asset_type: Optional[str] = Field(
        default=None,
        description="Fill this optional value ONLY with the type of asset passed by the user",
    )
    dates: Optional[str] = Field(
        default=None,
        description="""Two dates in ISO 8601 format separated by comma or space. This optional field should get value:
            - If user mentions dates when assets should be valid
            - If user mentions version comparison
            - Format examples: "2025-01-01T00:00:00Z,2025-12-31T23:59:59Z" or "2025-01-01T00:00:00Z 2025-12-31T23:59:59Z"
            - Can also be JSON array: '["2025-01-01T00:00:00Z","2025-12-31T23:59:59Z"]'""",
    )

    @model_validator(mode='after')
    def set_default_values(self):
        """
        Set default values for optional fields when they are None.
        
        This validator is required because the MCP framework may inject placeholder values
        during serialization of optional parameters. By accepting None and converting to
        appropriate defaults, we ensure the tool works correctly with MCP clients.
        
        - is_operational: defaults to False if None
        - data_quality_value: defaults to SENTINEL_NO_QUALITY_VALUE (-0.01) if None
          This sentinel value is outside the valid range (0.0-100.0) and indicates
          no value was provided by the user.
        - All string fields remain None if not provided
        
        Additionally validates that user-provided data_quality_value is within valid range.
        """
        self.is_operational = self.is_operational or False
        
        self.data_quality_value = self.data_quality_value or SENTINEL_NO_QUALITY_VALUE
        
        # Validate range for user-provided values
        if self.data_quality_value != SENTINEL_NO_QUALITY_VALUE:
            if not (0.0 <= self.data_quality_value <= 100.0):
                raise ValueError(
                    f"data_quality_value must be between 0.0 and 100.0, got {self.data_quality_value}"
                )
        
        return self


class SearchLineageAssetsResponse(BaseResponseModel):
    """Search lineage assets response  model"""

    lineage_assets: List[LineageAsset] = Field(
        ..., description="List of lineage assets."
    )
    response_is_complete: bool
