# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field


class GenerateSqlQueryRequest(BaseModel):
    """Request model for generating SQL query."""

    project_name: str = Field(
        ..., description="The name of the project which is used to find a project id."
    )
    connection_name: str = Field(
        ...,
        description="The name of the connection which is used to find a connection id.",
    )
    request: str = Field(..., description="The question the user raised.")


class GenerateSqlQueryResponse(BaseModel):
    project_id: str = Field(..., description="Unique id of the project.")
    connection_id: str = Field(..., description="Unique id of the connection.")
    generated_sql_query: str = Field(..., description="Generated SQL query")
