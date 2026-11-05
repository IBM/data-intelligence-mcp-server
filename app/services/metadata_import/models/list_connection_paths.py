# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel  # noqa: I001 # Baseline
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import Optional, List  # noqa: UP035 # Baseline


class ListConnectionPathsRequest(BaseModel):
    project_name: str = Field(
        ..., description="Project name where the connection resides"
    )
    connection_name: str = Field(
        ..., description="The name of the connection to list paths for"
    )
    offset: Optional[int] = Field(1, description="Pagination offset (starts at 1)")  # noqa: UP045 # Baseline
    limit: Optional[int] = Field(  # noqa: UP045 # Baseline
        10, description="Maximum number of items to return, -1 for all"
    )
    filter_text: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="Optional substring to filter path names"
    )


class ListConnectionPathsResponse(BaseResponseModel):
    paths: List[str] = Field(  # noqa: UP006 # Baseline
        ..., description="List of schema/table path strings available in the connection"
    )
    count: int = Field(..., description="The number of paths returned")
