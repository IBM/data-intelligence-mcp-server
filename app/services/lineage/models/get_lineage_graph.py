# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from typing import List
from pydantic import BaseModel, Field

from .lineage_asset import LineageAsset


class GetLineageGraphRequest(BaseModel):
    lineage_id: str = Field(..., description="The lineage asset id.")


class GetLineageGraphResponse(BaseModel):
    lineage_assets: List[LineageAsset] = Field(
        ..., description="List of lineage assets."
    )
    url: str = Field(..., description="Link to upstream and downstream lineage graph.")
