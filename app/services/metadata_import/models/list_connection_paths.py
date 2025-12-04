# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field
from typing import Optional, List


class ListConnectionPathsRequest(BaseModel):
    project_name: str = Field(..., description="Project name where the connection resides")
    connection_name: str = Field(..., description="The name of the connection to list paths for")
    offset: Optional[int] = Field(1, description="Pagination offset (starts at 1)")
    limit: Optional[int] = Field(10, description="Maximum number of items to return, -1 for all")
    filter_text: Optional[str] = Field(None, description="Optional substring to filter path names")


class ListConnectionPathsResponse(BaseModel):
    paths: List[str] = Field(..., description="List of schema/table path strings available in the connection")
    count: int = Field(..., description="The number of paths returned")
