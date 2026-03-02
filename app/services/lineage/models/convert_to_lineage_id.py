# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class ConvertToLineageIdRequest(BaseModel):
    container_id: str = Field(
        ...,
        description="The container identifier - can be either a catalog ID or project ID (must be valid UUID)",
    )
    asset_id: str = Field(
        ...,
        description="The asset identifier within the container (must be valid UUID)",
    )


class ConvertToLineageIdResponse(BaseResponseModel):
    lineage_id: str = Field(
        ...,
        description="A unique lineage identifier that can be used with other lineage tools",
    )
