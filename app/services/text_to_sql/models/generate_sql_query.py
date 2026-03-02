# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class GenerateSqlQueryRequest(BaseModel):
    """Request model for generating SQL query."""

    container_id_or_name: str = Field(
        ..., description="The id or name of the container containing the data to query."
    )
    container_type: str = Field(
        ...,
        description="Type of the container, either \"catalog\" or \"project\".",
    )
    request: str = Field(..., description="The question the user raised.")


class GenerateSqlQueryResponse(BaseResponseModel):
    generated_sql_query: str = Field(..., description="Generated SQL query")
