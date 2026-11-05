# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from datetime import datetime  # noqa: I001 # Baseline
from typing import List, Literal, Optional  # noqa: UP035 # Baseline
from pydantic import BaseModel, Field, model_validator
from app.shared.models import BaseResponseModel


class Task(BaseModel):
    """Task information from workflow task inbox."""

    task_id: str = Field(..., description="Unique identifier of the task")
    task_name: str = Field(..., description="Name/title of the task")
    task_title: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="Formatted task title as displayed in UI"
    )
    workflow_id: str = Field(..., description="Workflow ID")
    workflow_template_id: str = Field(..., description="Workflow template ID")
    created_at: datetime = Field(..., description="When the task was created")
    claimed_at: Optional[datetime] = Field(  # noqa: UP045 # Baseline
        None, description="When the task was claimed"
    )
    due_date: Optional[datetime] = Field(  # noqa: UP045 # Baseline
        None, description="Task due date if applicable"
    )
    priority: Optional[int] = Field(None, description="Task priority (0-100)")  # noqa: UP045 # Baseline
    assignee: Optional[str] = Field(None, description="Current assignee of the task")  # noqa: UP045 # Baseline
    form_key: Optional[str] = Field(None, description="Form key for task form")  # noqa: UP045 # Baseline
    state: Optional[str] = Field(None, description="Current state of the task")  # noqa: UP045 # Baseline
    candidate_users: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        None, description="List of candidate users who can claim the task"
    )
    candidate_groups: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        None, description="List of candidate groups who can claim the task"
    )
    variables: Optional[dict] = Field(  # noqa: UP045 # Baseline
        None, description="Process variables relevant to the task"
    )


class GetMyTasksRequest(BaseModel):
    """Request model for get_my_tasks."""

    max_results: Optional[int] = Field(  # noqa: UP045 # Baseline
        None,
        description="[Deprecated: use page_size] Maximum number of tasks to return",
        ge=1,
        le=100,
    )
    page_size: int = Field(
        10,
        description="Number of tasks to return per page (1-50)",
        ge=1,
        le=50,
    )
    format: str = Field(
        "table",
        description="Output format: 'table' for formatted markdown table, 'json' for raw task data",
    )
    urgency: Optional[Literal["overdue", "at_risk", "all"]] = Field(  # noqa: UP045 # Baseline
        "all",
        description="Filter tasks by urgency status ('overdue', 'at_risk', 'all')",
    )
    sort: Optional[Literal["due_date", "latest", "oldest", "priority"]] = Field(  # noqa: UP045 # Baseline
        "due_date",
        description="Sort order ('due_date', 'latest', 'oldest', 'priority')",
    )
    due_before: Optional[datetime] = Field(  # noqa: UP045 # Baseline
        None,
        description="Filter tasks due before this ISO 8601 datetime",
    )
    due_after: Optional[datetime] = Field(  # noqa: UP045 # Baseline
        None,
        description="Filter tasks due after this ISO 8601 datetime",
    )
    page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Opaque pagination cursor token from a previous response",
    )

    @model_validator(mode="after")
    def validate_and_compat(self) -> "GetMyTasksRequest":
        # Backward compatibility: if max_results was explicitly passed, override page_size
        if self.max_results is not None:
            self.page_size = self.max_results

        # Validate date range
        if self.due_before is not None and self.due_after is not None:  # noqa: SIM102 # Baseline
            if self.due_before < self.due_after:
                raise ValueError("due_before must be after or equal to due_after")

        return self


class GetMyTasksResponse(BaseResponseModel):
    """Response model for get_my_tasks."""

    tasks: Optional[List[Task]] = Field(  # noqa: UP006, UP045 # Baseline
        None,
        description="List of tasks from the user's inbox (only when format='json')",
    )
    total_count: int = Field(..., description="Total number of tasks available")
    formatted_output: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Formatted markdown table output when format='table'",
    )
    next_page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Opaque token to fetch the next page of results",
    )
    prev_page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Opaque token to fetch the previous page of results",
    )
    has_more: bool = Field(
        False,
        description="Whether more items exist beyond this page",
    )
    semantic_summary: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Human-readable summary of the tasks and current page view",
    )
