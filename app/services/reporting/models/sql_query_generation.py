# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List
from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class SqlQueryGenerationRequest(BaseModel):
    """Request model for generating SQL query from natural language."""

    project_name: str = Field(
        ...,
        description="Name of the project containing the data model for SQL generation.",
    )
    query: str = Field(
        ...,
        description="Natural language request to convert to SQL.",
    )
    instructions: List[str] = Field(
        default_factory=list,
        description="Instructions for SQL generation. Example: ['Do not use tech_start, tech_end, ts_id in the output column.']",
    )
    raw_output: bool = Field(
        default=False,
        description="Whether to return raw output from the model.",
    )


class SqlQueryGenerationResponse(BaseResponseModel):
    """Response model for SQL query generation."""

    status: str = Field(
        ..., description="Status of the generation: 'success' or 'failed'"
    )
    project_id: str | None = Field(
        None, description="Unique identifier of the project (present on success)"
    )
    generated_sql_query: str | None = Field(
        None, description="The generated SQL query (present on success)"
    )
    dialect: str | None = Field(
        None,
        description="The SQL dialect used for generation: 'postgresql', 'mssql', 'oracle', or 'db2' (present on success)",
    )
    message: str | None = Field(
        None, description="Error message (present on failure)"
    )