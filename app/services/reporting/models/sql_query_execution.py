# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.Apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Any, Dict, List
from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class SqlQueryExecutionRequest(BaseModel):
    """Request model for executing SQL query."""

    sql_query: str = Field(
        ...,
        description="The SQL SELECT query to execute. Must be a syntactically valid and read-only query.",
    )


class SqlResult(BaseModel):
    """Model for SQL execution result."""

    sql_query: str = Field(..., description="The SQL query that was executed")
    rows: List[Dict[str, Any]] = Field(
        ..., description="Array of result rows with column names as keys"
    )


class SqlQueryExecutionResponse(BaseResponseModel):
    """Response model for SQL query execution."""

    status: str = Field(
        ..., description="Status of the execution: 'success' or 'failed'"
    )
    sql_result: SqlResult | None = Field(
        None, description="SQL execution result (present on success)"
    )
    message: str | None = Field(
        None, description="Error message (present on failure)"
    )