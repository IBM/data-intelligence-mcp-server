# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.shared.models import BaseResponseModel, field_validator


class Task(BaseModel):
    """Task information from workflow task inbox."""

    task_id: str = Field(..., description="Unique identifier of the task")
    task_name: str = Field(..., description="Name/title of the task")
    task_title: Optional[str] = Field(None, description="Formatted task title as displayed in UI")
    workflow_id: str = Field(..., description="Workflow ID")
    workflow_template_id: str = Field(..., description="Workflow template ID")
    created_at: datetime = Field(..., description="When the task was created")
    due_date: Optional[datetime] = Field(None, description="Task due date if applicable")
    priority: Optional[int] = Field(None, description="Task priority (0-100)")
    assignee: Optional[str] = Field(None, description="Current assignee of the task")
    form_key: Optional[str] = Field(None, description="Form key for task form")
    state: Optional[str] = Field(None, description="Current state of the task")
    candidate_users: Optional[List[str]] = Field(None, description="List of candidate users who can claim the task")
    candidate_groups: Optional[List[str]] = Field(None, description="List of candidate groups who can claim the task")
    variables: Optional[dict] = Field(None, description="Process variables relevant to the task")



class GetMyTasksRequest(BaseModel):
    """Request model for get_my_tasks."""

    max_results: int = Field(
        50, description="Maximum number of tasks to return", ge=1, le=100
    )
    format: str = Field(
        "table",
        description="Output format: 'table' for formatted markdown table, 'json' for raw task data"
    )


class GetMyTasksResponse(BaseResponseModel):
    """Response model for get_my_tasks."""

    tasks: Optional[List[Task]] = Field(
        None,
        description="List of tasks from the user's inbox (only when format='json')"
    )
    total_count: int = Field(..., description="Total number of tasks available")
    formatted_output: Optional[str] = Field(
        None,
        description="Formatted markdown table output when format='table'"
    )
