# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Models for listing user tasks.

This module contains request and response models for querying the workflow API
to retrieve workflows pertaining to a specific artifact_id of a glossary object and retrieve all their user tasks.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from app.shared.models import BaseResponseModel, field_validator


class UserTask(BaseModel):
    """Model representing a glossary data class."""

    name: str = Field(..., description="User task name")  # I hope to guess approval tasks from their name, title and instruction
    task_title : Optional[str] = Field(None, description="Task title")
    task_instruction : Optional[str] = Field(None, description="Task instruction")
    state: Optional[str] = Field(None, description="User task state")   # 0 - created, 1 - assigned, 2 - completed
    assignee: Optional[str] = Field(None, description="User task assignee")
    completed_at: Optional[str] = Field(None, description="When user task has been completed")
    candidate_users: Optional[List[str]] = Field(
        ..., description="List of potential assignee names for this task"
    )


class ListUserTasksRequest(BaseModel):
    """Request model for listing user tasks."""

    artifact_id: Optional[str] = Field(None, description="Artifact ID as object of a workflow")
    draft: bool = Field(..., description="Artifact in draft or published")
    max_results: int = Field(
        50,
        description="Maximum number of user tasks to return",
        ge=1,
        le=100
    )
    format: str = Field(
        "table",
        description="Output format: 'table' for formatted markdown table, 'json' for raw data"
    )


class ListUserTasksResponse(BaseResponseModel):
    """Response model for listing user tasks."""

    user_tasks: Optional[List[UserTask]] = Field(
        None,
        description="List of user tasks (only when format='json')"
    )
    total_count: int = Field(..., description="Total number of data classes available")
    formatted_output: Optional[str] = Field(
        None,
        description="Formatted markdown table output when format='table'"
    )

