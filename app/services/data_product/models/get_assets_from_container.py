# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import List, Literal


class Asset(BaseModel):
    id: str = Field(..., description="The ID of the asset.")
    name: str = Field(..., description="The name of the asset.")
    catalog_id: str | None = Field(
        default=None, description="The catalog ID of the asset."
    )
    project_id: str | None = Field(
        default=None, description="The project ID of the asset."
    )

class GetAssetsFromContainerRequest(BaseModel):
    container_type: Literal["catalog", "project"] = Field(
        ..., description="Where to search - either 'project' or 'catalog'. This is a mandatory field."
    )

class GetAssetsFromContainerResponse(BaseResponseModel):
    message: str = Field(
        ..., description="A message showing the number of assets found in the catalog."
    )
    assets: List[Asset] = Field(
        ..., description="A List of assets from the catalog."
    )
