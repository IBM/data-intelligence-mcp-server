# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.shared.models import BaseResponseModel, field_validator


class Workflow(BaseModel):
    """Basic workflow information from workflow API (light mode)."""

    workflow_id: str = Field(..., description="Unique identifier of the workflow")
    name: str = Field(..., description="Name of the workflow")
    description: Optional[str] = Field(None, description="Description of the workflow")
    workflow_template_id: str = Field(..., description="Workflow template ID")
    state: str = Field(..., description="Current state of the workflow (active, completed, etc.)")
    created_at: datetime = Field(..., description="When the workflow was created")
    created_by: Optional[str] = Field(None, description="User who created the workflow")
    business_key: Optional[str] = Field(None, description="Business key associated with the workflow")
    variables: Optional[dict] = Field(None, description="Process variables")


class TaskDetail(BaseModel):
    """Detailed information about a task within a workflow (deep dive mode)."""
    
    task_id: str = Field(..., description="Unique task identifier")
    task_title: str = Field(..., description="Formatted task title")
    task_name: str = Field(..., description="Task name")
    state: str = Field(..., description="Task state: 0=created, 1=assigned, 2=completed")
    assignee: Optional[str] = Field(None, description="Current assignee (user ID or email)")
    created_at: datetime = Field(..., description="When the task was created")
    completed_at: Optional[datetime] = Field(None, description="When the task was completed")
    days_in_current_state: int = Field(..., description="Number of days task has been in current state")


class WorkflowRequest(BaseModel):
    """Detailed workflow information with analysis (deep dive mode)."""
    
    workflow_id: str = Field(..., description="Unique workflow identifier")
    name: str = Field(..., description="Workflow name/title")
    description: Optional[str] = Field(None, description="Workflow description")
    workflow_template_id: str = Field(..., description="Workflow template ID")
    state: str = Field(..., description="Current workflow state (active, completed, suspended)")
    created_at: datetime = Field(..., description="When the workflow was created")
    created_by: Optional[str] = Field(None, description="User who created the workflow")
    
    # Activity tracking
    last_activity_at: Optional[datetime] = Field(
        None, 
        description="Timestamp of last task action (most recent task state change)"
    )
    days_since_activity: Optional[int] = Field(
        None,
        description="Number of days since last activity"
    )
    is_stalled: bool = Field(
        False,
        description="True if workflow has no activity beyond stalled_days threshold"
    )
    
    # Task summary statistics
    total_tasks: int = Field(0, description="Total number of tasks in workflow")
    completed_tasks: int = Field(0, description="Number of completed tasks")
    in_progress_tasks: int = Field(0, description="Number of tasks in progress (assigned)")
    pending_tasks: int = Field(0, description="Number of pending tasks (created but not assigned)")
    
    # Current assignees
    current_assignees: List[str] = Field(
        default_factory=list,
        description="List of users currently assigned to active tasks"
    )
    
    # Completion metrics (for completed workflows)
    completed_at: Optional[datetime] = Field(None, description="When workflow was completed")
    duration_days: Optional[int] = Field(None, description="How many days workflow took to complete")
    
    # Detailed tasks (optional, included when include_tasks=True)
    tasks: Optional[List[TaskDetail]] = Field(
        None,
        description="Detailed task information (only included if requested)"
    )


class GetMyWorkflowsRequest(BaseModel):
    """Request model for get_my_workflows."""

    max_results: int = Field(
        50, description="Maximum number of workflows to return", ge=1, le=200
    )
    state: Optional[str] = Field(
        None, description="Filter by workflow state (active, completed, suspended, etc.)"
    )
    deep_dive: bool = Field(
        False,
        description="When True, performs comprehensive analysis with task details, activity tracking, and metrics. When False, returns basic workflow information only."
    )
    include_tasks: bool = Field(
        False,
        description="Include detailed task information for each workflow (only applicable when deep_dive=True)"
    )
    stalled_days: Optional[int] = Field(
        14,
        description="Threshold for considering a workflow stalled (no activity in X days). Set to None to disable stalled detection (only applicable when deep_dive=True).",
        ge=1
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Get details for a specific workflow by ID (ignores other filters)"
    )
    format: str = Field(
        "json",
        description="Output format: 'table' for formatted markdown tables, 'json' for raw data (only applicable when deep_dive=True)"
    )


class GetMyWorkflowsResponse(BaseResponseModel):
    """Response model for get_my_workflows."""

    # Light mode: basic workflows
    workflows: Optional[List[Workflow]] = Field(
        None,
        description="List of workflows with basic information (only when deep_dive=False and format='json')"
    )
    
    # Deep dive mode: detailed workflows
    workflow_requests: Optional[List[WorkflowRequest]] = Field(
        None,
        description="List of workflows with detailed analysis (only when deep_dive=True and format='json')"
    )
    
    total_count: int = Field(..., description="Total number of workflows returned")
    
    # Summary statistics (only when deep_dive=True and format='json')
    active_count: Optional[int] = Field(
        None,
        description="Number of active/in-progress workflows (only when deep_dive=True and format='json')"
    )
    
    completed_count: Optional[int] = Field(
        None,
        description="Number of completed workflows (only when deep_dive=True and format='json')"
    )
    
    stalled_count: Optional[int] = Field(
        None,
        description="Number of stalled workflows (no activity beyond threshold) (only when deep_dive=True and format='json')"
    )
    
    at_risk_count: Optional[int] = Field(
        None,
        description="Number of at-risk workflows (approaching stalled threshold) (only when deep_dive=True and format='json')"
    )
    
    # Formatted output (only when deep_dive=True and format='table')
    formatted_output: Optional[str] = Field(
        None,
        description="Formatted markdown output when deep_dive=True and format='table'"
    )
