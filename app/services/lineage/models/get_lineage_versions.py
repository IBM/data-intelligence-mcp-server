# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List
from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class GetLineageVersionsRequest(BaseModel):
    since: str = Field(
        ...,
        description="ISO-8601 based timestamp indicating the start of the time range",
    )
    until: str = Field(
        ...,
        description="ISO-8601 based timestamp indicating the end of the time range",
    )


class GetLineageVersionsResponse(BaseResponseModel):
    dates: List[str] = Field(
        ...,
        description="List of ISO-8601 based timestamps indicating the available version",

    )
