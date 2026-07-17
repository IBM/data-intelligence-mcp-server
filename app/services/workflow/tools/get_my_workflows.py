# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for retrieving workflows initiated by current user.

This module provides functionality to monitor workflows you've created, with two modes:
- Light mode (deep_dive=False): Returns basic workflow information for quick overview
- Deep dive mode (deep_dive=True): Returns comprehensive analysis with task details, activity tracking, and metrics
"""

from typing import Annotated, List, Optional
from datetime import datetime, timezone
import json
from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import WORKFLOW_BASE_ENDPOINT, WORKFLOW_TASK_ENDPOINT
from app.services.workflow.models.get_my_workflows import (
    GetMyWorkflowsRequest,
    GetMyWorkflowsResponse,
    Workflow,
    WorkflowRequest,
    TaskDetail
)
from app.services.workflow.tools.utils import ZERO_MINUTES
from app.services.workflow.utils.task_utils import _convert_variables_to_dict
from app.services.workflow.utils.user_mappers import convert_iam_id_to_email
from app.services.workflow.utils.workflow_request_formatters import (
    format_workflow_requests_as_tables,
    calculate_workflow_statistics
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.client_detection import supports_rich_text_format
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

# Constants for workflow name parsing
PLACEHOLDER_ARTIFACT_TYPE = "{artifactType}"
PLACEHOLDER_ARTIFACT_NAME = "{artifactName}"
PLACEHOLDER_DRAFT_MODE = "{draft_mode}"
DEFAULT_WORKFLOW_NAME = "Untitled Workflow"

# Task state constants
TASK_STATE_CREATED = "0"
TASK_STATE_ASSIGNED = "1"
TASK_STATE_COMPLETED = "2"


def _parse_workflow_name(workflow_name_raw: str) -> Optional[str]:
    """
    Parse workflow name from JSON template format.
    
    Args:
        workflow_name_raw: Raw workflow name string in JSON format from metadata.name
        
    Returns:
        Parsed workflow name or None if parsing fails
        
    Example:
        Input: '{"defaultMessage":"{draft_mode} {artifactType} {artifactName}",
                "artifactName":"Comps", "§draft_mode":"...CREATE"}'
        Output: "Create Business term Comps"
    """
    try:
        workflow_name_json = json.loads(workflow_name_raw.strip())
        default_message = workflow_name_json.get("defaultMessage", "")
        artifact_name = workflow_name_json.get("artifactName")
        artifact_type_key = workflow_name_json.get("§artifactType", "")
        draft_mode_key = workflow_name_json.get("§draft_mode", "")
        
        # Extract artifact type from the translation key
        artifact_type = "artifact"
        if "glossary_term" in artifact_type_key:
            artifact_type = "Business term"
        elif "data_class" in artifact_type_key:
            artifact_type = "Data class"
        elif "category" in artifact_type_key:
            artifact_type = "Category"
        
        # Extract draft mode action from the translation key
        draft_mode = "Workflow"
        if "CREATE" in draft_mode_key:
            draft_mode = "Create"
        elif "UPDATE" in draft_mode_key:
            draft_mode = "Update"
        elif "DELETE" in draft_mode_key:
            draft_mode = "Delete"
        
        # Replace placeholders in the template
        result = default_message.replace(PLACEHOLDER_DRAFT_MODE, draft_mode)
        result = result.replace(PLACEHOLDER_ARTIFACT_TYPE, artifact_type)
        result = result.replace(PLACEHOLDER_ARTIFACT_NAME, artifact_name or "")
        
        return result.strip()
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        LOGGER.debug(f"Failed to parse workflow name JSON: {e}")
        return None


def _parse_task_title(task_title_raw: str) -> Optional[str]:
    """
    Parse task title from JSON template format.
    
    Args:
        task_title_raw: Raw task title string in JSON format
        
    Returns:
        Parsed task title or None if parsing fails
    """
    try:
        task_title_json = json.loads(task_title_raw.strip())
        default_message = task_title_json.get("defaultMessage", "")
        artifact_name = task_title_json.get("artifactName")
        artifact_type_key = task_title_json.get("§artifactType")
        
        # If artifact fields are missing, replace placeholders with empty strings
        if not artifact_name or not artifact_type_key:
            return default_message.replace(PLACEHOLDER_ARTIFACT_TYPE, "").replace(PLACEHOLDER_ARTIFACT_NAME, "")
        
        # Extract artifact type from the translation key
        artifact_type = "artifact"
        if "glossary_term" in artifact_type_key:
            artifact_type = "Business term"
        elif "data_class" in artifact_type_key:
            artifact_type = "Data class"
        elif "category" in artifact_type_key:
            artifact_type = "Category"
        
        # Replace placeholders in the template
        return default_message.replace(PLACEHOLDER_ARTIFACT_TYPE, artifact_type).replace(PLACEHOLDER_ARTIFACT_NAME, artifact_name)
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        LOGGER.debug(f"Failed to parse task_title JSON: {e}")
        return None


async def _create_workflow_from_data(
    workflow_data: dict,
    workflow_title: Optional[str] = None,
    tasks: Optional[List[TaskDetail]] = None
) -> Workflow:
    """
    Create a Workflow object from raw workflow data.
    
    Args:
        workflow_data: Raw workflow data from API
        workflow_title: Parsed workflow title (optional, for backward compatibility)
        tasks: List of task details (optional, included when include_tasks=True)
        
    Returns:
        Workflow object
    """
    metadata = workflow_data.get("metadata", {})
    entity = workflow_data.get("entity", {})
    
    # Convert variables list to dict
    variables_list = entity.get("variables", [])
    variables_dict = _convert_variables_to_dict(variables_list)
    
    # Get workflow ID
    workflow_id = metadata.get("workflow_id")
    
    # Parse workflow name from metadata.name JSON field
    workflow_name = DEFAULT_WORKFLOW_NAME
    workflow_name_raw = metadata.get("name")
    if workflow_name_raw:
        parsed_name = _parse_workflow_name(workflow_name_raw)
        if parsed_name:
            workflow_name = parsed_name
    
    # Fall back to provided title or entity name if parsing failed
    if workflow_name == DEFAULT_WORKFLOW_NAME:
        workflow_name = workflow_title if workflow_title else entity.get("name", DEFAULT_WORKFLOW_NAME)
    
    # Replace IAM ID with email address if available
    created_by_iam_id = metadata.get("created_by")
    created_by = await convert_iam_id_to_email(created_by_iam_id, "created_by") if created_by_iam_id else None
    
    # Use workflow_state from entity (business state) instead of metadata.state (engine state)
    # entity.workflow_state contains values like "Not started", "Rejected", etc.
    # metadata.state contains engine states like "running", "completed", etc.
    workflow_state = entity.get("workflow_state", metadata.get("state", "unknown"))
    
    return Workflow(
        workflow_id=workflow_id,
        name=workflow_name,
        description=entity.get("description"),
        workflow_template_id=metadata.get("workflow_type_id", ""),
        state=workflow_state,
        created_at=datetime.fromisoformat(metadata.get("created_at").replace("Z", ZERO_MINUTES)),
        created_by=created_by,
        business_key=entity.get("business_key"),
        variables=variables_dict,
        tasks=tasks
    )


async def _retrieve_my_workflows(
    max_results: int,
    state: Optional[str] = None,
    include_tasks: bool = False,
    workflow_id: Optional[str] = None,
) -> List[Workflow]:
    """
    Retrieve list of workflows initiated by current user.

    Args:
        max_results: Maximum number of workflows to return
        state: Optional state filter (active, completed, suspended, etc.)
        include_tasks: Whether to include detailed task information for each workflow
        workflow_id: Optional specific workflow ID to retrieve (ignores other filters)

    Returns:
        List[Workflow]: List of workflow objects
    """
    params = {}
    
    url=f"{tool_helper_service.base_url}{WORKFLOW_BASE_ENDPOINT}"

    params['include_user_tasks'] = include_tasks

    # When workflow_id is specified, ignore other filters
    if workflow_id:
        url=f"{tool_helper_service.base_url}{WORKFLOW_BASE_ENDPOINT}/{workflow_id}"
    else:
        if max_results is not None:
            params['limit'] = str(max_results)
        if state is not None:
            params['state'] = state

    try:
        response = await tool_helper_service.execute_get_request(
            url=url,
            params=params,
        )

        workflow_list = None
        # Parse response
        if workflow_id:
            workflow_list = [response]
        else:
            workflow_list = response.get('resources', [])

        LOGGER.info(f"Retrieved {len(workflow_list)} workflows from API")
        workflows = []
        
        for idx, workflow_data in enumerate(workflow_list):
            metadata = workflow_data.get("metadata", {})
            wf_id = metadata.get("workflow_id")
            LOGGER.info(f"Processing workflow {idx+1}/{len(workflow_list)}: {wf_id}")
            
            # Get tasks if requested
            tasks = None
            if include_tasks:
                task_list = workflow_data.get("entity", {}).get("user_tasks", [])

                tasks = []
                for task_data in task_list:
                    task = await _create_task_detail(task_data)
                    tasks.append(task)

                LOGGER.info(f"  Retrieved {len(tasks)} tasks")
            
            # Create workflow object with parsed name and optional tasks
            workflow = await _create_workflow_from_data(workflow_data, tasks=tasks)
            LOGGER.info(f"  Created workflow object with id: {workflow.workflow_id}, name: {workflow.name}")
            workflows.append(workflow)

        LOGGER.info(f"Returning {len(workflows)} workflow objects")
        return workflows

    except Exception as e:
        LOGGER.error(f"Error retrieving workflows: {str(e)}")
        return []


def _calculate_days_in_state(created_at: datetime) -> int:
    """
    Calculate number of days a task has been in its current state.
    
    Args:
        created_at: Task creation timestamp
        
    Returns:
        Number of days in current state
    """
    now = datetime.now(timezone.utc)
    return (now - created_at).days


def _parse_completed_timestamp(completed_str: Optional[str]) -> Optional[datetime]:
    """
    Parse completed timestamp from string.
    
    Args:
        completed_str: Completed timestamp string
        
    Returns:
        Parsed datetime or None if parsing fails
    """
    if not completed_str:
        return None
    try:
        return datetime.fromisoformat(completed_str.replace("Z", ZERO_MINUTES))
    except Exception:
        return None


async def _create_task_detail(task_data: dict) -> TaskDetail:
    """
    Create a TaskDetail object from raw task data.
    
    Args:
        task_data: Raw task data from API
        
    Returns:
        TaskDetail object
    """
    metadata = task_data.get("metadata", {})
    entity = task_data.get("entity", {})
    
    # Parse task title
    task_title_raw = entity.get("task_title", "")
    task_title = metadata.get("name", "Untitled Task")
    
    if task_title_raw:
        parsed_title = _parse_task_title(task_title_raw)
        if parsed_title:
            task_title = parsed_title
    
    # Parse timestamps
    created_at = datetime.fromisoformat(metadata.get("created_at").replace("Z", ZERO_MINUTES))
    state = metadata.get("state", "0")
    
    # Get completed timestamp if available
    completed_at = None
    if state == TASK_STATE_COMPLETED:
        completed_at = _parse_completed_timestamp(entity.get("completed"))
    
    # Replace IAM ID with email address for assignee if available
    assignee_iam_id = entity.get("assignee")
    assignee = await convert_iam_id_to_email(assignee_iam_id, "assignee") if assignee_iam_id else None
    
    return TaskDetail(
        task_id=metadata.get("task_id"),
        task_title=task_title,
        task_name=metadata.get("name", "Untitled Task"),
        state=state,
        assignee=assignee,
        created_at=created_at,
        completed_at=completed_at,
        days_in_current_state=_calculate_days_in_state(created_at)
    )


async def _get_tasks_for_workflow(workflow_id: str) -> List[TaskDetail]:
    """
    Retrieve all tasks for a specific workflow (deep dive mode).
    
    Args:
        workflow_id: Workflow ID
        
    Returns:
        List of TaskDetail objects
    """
    try:
        params = {
            'workflow_id': workflow_id,
            'limit': '100'  # Get all tasks
        }
        
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}",
            params=params,
        )
        
        task_list = response.get('resources', [])
        tasks = []
        for task_data in task_list:
            task = await _create_task_detail(task_data)
            tasks.append(task)
        return tasks
        
    except Exception as e:
        LOGGER.error(f"Error retrieving tasks for workflow {workflow_id}: {str(e)}")
        return []


def _count_tasks_by_state(tasks: List[TaskDetail]) -> dict:
    """
    Count tasks by their state.
    
    Args:
        tasks: List of task details
        
    Returns:
        Dictionary with task counts by state
    """
    return {
        "total_tasks": len(tasks),
        "completed_tasks": sum(1 for t in tasks if t.state == TASK_STATE_COMPLETED),
        "in_progress_tasks": sum(1 for t in tasks if t.state == TASK_STATE_ASSIGNED),
        "pending_tasks": sum(1 for t in tasks if t.state == TASK_STATE_CREATED)
    }


def _extract_current_assignees(tasks: List[TaskDetail]) -> List[str]:
    """
    Extract unique assignees from non-completed tasks.
    
    Args:
        tasks: List of task details
        
    Returns:
        List of unique assignee names
    """
    assignees = []
    for task in tasks:
        if task.state != TASK_STATE_COMPLETED and task.assignee and task.assignee not in assignees:
            assignees.append(task.assignee)
    return assignees


def _calculate_last_activity(workflow_data: dict, tasks: List[TaskDetail]) -> Optional[datetime]:
    """
    Calculate last activity timestamp for a workflow.
    
    Args:
        workflow_data: Raw workflow data from API
        tasks: List of task details
        
    Returns:
        Last activity datetime or None
    """
    if tasks:
        # For completed tasks, use completion time; for others, use creation time
        task_timestamps = [
            task.completed_at if task.completed_at else task.created_at
            for task in tasks
        ]
        if task_timestamps:
            return max(task_timestamps)
    
    # If no task activity, use workflow creation time
    metadata = workflow_data.get("metadata", {})
    created_at_str = metadata.get("created_at")
    if created_at_str:
        return datetime.fromisoformat(created_at_str.replace("Z", ZERO_MINUTES))
    
    return None


def _calculate_stalled_status(
    last_activity_at: Optional[datetime],
    stalled_days: Optional[int]
) -> tuple[Optional[int], bool]:
    """
    Calculate days since activity and stalled status.
    
    Args:
        last_activity_at: Last activity timestamp
        stalled_days: Threshold for stalled detection
        
    Returns:
        Tuple of (days_since_activity, is_stalled)
    """
    if not last_activity_at:
        return None, False
    
    days_since_activity = (datetime.now(timezone.utc) - last_activity_at).days
    is_stalled = stalled_days is not None and days_since_activity >= stalled_days
    
    return days_since_activity, is_stalled


def _calculate_completion_metrics(
    workflow_data: dict,
    tasks: List[TaskDetail]
) -> tuple[Optional[datetime], Optional[int]]:
    """
    Calculate completion timestamp and duration for completed workflows.
    
    Args:
        workflow_data: Raw workflow data from API
        tasks: List of task details
        
    Returns:
        Tuple of (completed_at, duration_days)
    """
    metadata = workflow_data.get("metadata", {})
    state = metadata.get("state", "unknown")
    
    if state != "completed":
        return None, None
    
    # Find completion time from last completed task
    completed_tasks_list = [t for t in tasks if t.completed_at]
    if not completed_tasks_list:
        return None, None
    
    completion_times = [t.completed_at for t in completed_tasks_list if t.completed_at is not None]
    if not completion_times:
        return None, None
    
    completed_at = max(completion_times)
    created_at_str = metadata.get("created_at")
    
    if created_at_str and completed_at:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", ZERO_MINUTES))
        duration_days = (completed_at - created_at).days
        return completed_at, duration_days
    
    return None, None


def _calculate_workflow_metrics(workflow_data: dict, tasks: List[TaskDetail], stalled_days: Optional[int]) -> dict:
    """
    Calculate activity metrics and statistics for a workflow (deep dive mode).
    
    Args:
        workflow_data: Raw workflow data from API
        tasks: List of tasks for this workflow
        stalled_days: Threshold for stalled detection
        
    Returns:
        Dictionary with calculated metrics
    """
    # Count tasks by state
    task_counts = _count_tasks_by_state(tasks)
    
    # Get current assignees
    current_assignees = _extract_current_assignees(tasks)
    
    # Calculate last activity
    last_activity_at = _calculate_last_activity(workflow_data, tasks)
    
    # Calculate stalled status
    days_since_activity, is_stalled = _calculate_stalled_status(last_activity_at, stalled_days)
    
    # Calculate completion metrics
    completed_at, duration_days = _calculate_completion_metrics(workflow_data, tasks)
    
    return {
        "total_tasks": task_counts["total_tasks"],
        "completed_tasks": task_counts["completed_tasks"],
        "in_progress_tasks": task_counts["in_progress_tasks"],
        "pending_tasks": task_counts["pending_tasks"],
        "current_assignees": current_assignees,
        "last_activity_at": last_activity_at,
        "days_since_activity": days_since_activity,
        "is_stalled": is_stalled,
        "completed_at": completed_at,
        "duration_days": duration_days
    }


def _build_workflow_query_params(
    max_results: Optional[int],
    state: Optional[str],
    include_tasks: Optional[bool],
    workflow_id: Optional[str]
) -> dict:
    """
    Build query parameters for workflow API request.
    
    Args:
        max_results: Maximum number of workflows to return
        state: Filter by state
        include_tasks: Include user task data
        workflow_id: Specific workflow ID to query
        
    Returns:
        Dictionary of query parameters
    """
    params = {}

    params['include_user_tasks'] = include_tasks
    
    if workflow_id:
        params['workflow_id'] = workflow_id
    else:
        if max_results is not None:
            params['limit'] = str(max_results)
        if state is not None:
            params['state'] = state
    
    return params


async def _create_workflow_request(
    workflow_data: dict,
    include_tasks: bool,
    stalled_days: Optional[int]
) -> WorkflowRequest:
    """
    Create a WorkflowRequest object from raw workflow data.
    
    Args:
        workflow_data: Raw workflow data from API
        include_tasks: Whether to include detailed task information
        stalled_days: Threshold for stalled detection
        
    Returns:
        WorkflowRequest object
    """
    metadata = workflow_data.get("metadata", {})
    entity = workflow_data.get("entity", {})
    wf_id = metadata.get("workflow_id")
    
    # Parse workflow name from metadata.name JSON field
    workflow_name = DEFAULT_WORKFLOW_NAME
    workflow_name_raw = metadata.get("name")
    if workflow_name_raw:
        parsed_name = _parse_workflow_name(workflow_name_raw)
        if parsed_name:
            workflow_name = parsed_name
    
    # Fall back to entity name if parsing failed
    if workflow_name == DEFAULT_WORKFLOW_NAME:
        workflow_name = entity.get("name", DEFAULT_WORKFLOW_NAME)
    
    # Get tasks from workflow data
    task_list = workflow_data.get("entity", {}).get("user_tasks", [])

    tasks = []
    for task_data in task_list:
        task = await _create_task_detail(task_data)
        tasks.append(task)

    LOGGER.info(f"  Retrieved {len(tasks)} tasks")
        
    # Create workflow object with parsed name and optional tasks
    
    # Calculate metrics
    metrics = _calculate_workflow_metrics(workflow_data, tasks, stalled_days)
    
    # Replace IAM ID with email address for created_by if available
    created_by_iam_id = metadata.get("created_by")
    created_by = await convert_iam_id_to_email(created_by_iam_id, "created_by") if created_by_iam_id else None
    
    # Use workflow_state from entity (business state) instead of metadata.state (engine state)
    workflow_state = entity.get("workflow_state", metadata.get("state", "unknown"))
    
    return WorkflowRequest(
        workflow_id=wf_id,
        name=workflow_name,
        description=entity.get("description"),
        workflow_template_id=metadata.get("workflow_type_id", ""),
        state=workflow_state,
        created_at=datetime.fromisoformat(metadata.get("created_at").replace("Z", ZERO_MINUTES)),
        created_by=created_by,
        last_activity_at=metrics["last_activity_at"],
        days_since_activity=metrics["days_since_activity"],
        is_stalled=metrics["is_stalled"],
        total_tasks=metrics["total_tasks"],
        completed_tasks=metrics["completed_tasks"],
        in_progress_tasks=metrics["in_progress_tasks"],
        pending_tasks=metrics["pending_tasks"],
        current_assignees=metrics["current_assignees"],
        completed_at=metrics["completed_at"],
        duration_days=metrics["duration_days"],
        tasks=tasks if include_tasks else None
    )


async def _retrieve_my_workflows_deep_dive(
    max_results: int,
    state: Optional[str],
    include_tasks: bool,
    stalled_days: Optional[int],
    workflow_id: Optional[str]
) -> List[WorkflowRequest]:
    """
    Retrieve workflow requests initiated by current user with detailed analysis (deep dive mode).
    
    Args:
        max_results: Maximum number of workflows to return
        state: Filter by state (active, completed, or None for all)
        include_tasks: Whether to include detailed task information
        stalled_days: Threshold for stalled detection
        workflow_id: Specific workflow ID to query
        
    Returns:
        List of WorkflowRequest objects
    """
    params = _build_workflow_query_params(max_results, state, True, workflow_id) # always include task data
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_BASE_ENDPOINT}",
            params=params,
        )
        
        workflow_list = response.get('resources', [])
        
        # Process workflows concurrently for better performance
        workflows = []
        for workflow_data in workflow_list:
            workflow = await _create_workflow_request(workflow_data, include_tasks, stalled_days)
            workflows.append(workflow)
        
        return workflows
        
    except Exception as e:
        LOGGER.error(f"Error retrieving workflow requests: {str(e)}")
        return []


def _calculate_task_counts(tasks: List[TaskDetail]) -> tuple[int, int, int, int]:
    """
    Calculate task counts by state.
    
    Args:
        tasks: List of task details
        
    Returns:
        Tuple of (total, completed, in_progress, pending)
    """
    total = len(tasks)
    completed = sum(1 for t in tasks if t.state == TASK_STATE_COMPLETED)
    in_progress = sum(1 for t in tasks if t.state == TASK_STATE_ASSIGNED)
    pending = sum(1 for t in tasks if t.state == TASK_STATE_CREATED)
    return total, completed, in_progress, pending


def _format_workflow_row_basic(wf: Workflow, base_url: str) -> str:
    """
    Format a workflow row for basic table (without tasks).
    
    Args:
        wf: Workflow object
        base_url: Base URL for constructing workflow links
        
    Returns:
        Formatted table row string
    """
    from app.services.workflow.utils.workflow_request_formatters import build_workflow_url
    from app.services.workflow.utils.task_formatters import calculate_task_age
    
    workflow_url = build_workflow_url(base_url, wf.workflow_id)
    workflow_link = f"[{wf.name}]({workflow_url})"
    created_by = wf.created_by or "-"
    age = calculate_task_age(wf.created_at)
    created_on = wf.created_at.strftime("%Y-%m-%d")
    return f"| {workflow_link} | {wf.state} | {created_by} | {age} | {created_on} |\n"


def _format_workflow_row_with_tasks(wf: Workflow, base_url: str) -> str:
    """
    Format a workflow row for extended table (with task statistics).
    
    Args:
        wf: Workflow object
        base_url: Base URL for constructing workflow links
        
    Returns:
        Formatted table row string
    """
    from app.services.workflow.utils.workflow_request_formatters import build_workflow_url
    from app.services.workflow.utils.task_formatters import calculate_task_age
    
    workflow_url = build_workflow_url(base_url, wf.workflow_id)
    workflow_link = f"[{wf.name}]({workflow_url})"
    created_by = wf.created_by or "-"
    age = calculate_task_age(wf.created_at)
    
    if wf.tasks:
        total, completed, in_progress, pending = _calculate_task_counts(wf.tasks)
    else:
        total, completed, in_progress, pending = 0, 0, 0, 0
    
    created_on = wf.created_at.strftime("%Y-%m-%d")
    return f"| {workflow_link} | {wf.state} | {created_by} | {age} | {created_on} | {total} | {completed} | {in_progress} | {pending} |\n"


def _build_light_mode_response(workflows: List[Workflow]) -> GetMyWorkflowsResponse:
    """
    Build response for light mode (basic workflow information).
    
    Args:
        workflows: List of workflow objects
        
    Returns:
        GetMyWorkflowsResponse for light mode
    """
    formatted_output = None
    base_url = str(tool_helper_service.base_url)
    
    if workflows:
        # Check if any workflow has tasks to determine table format
        has_tasks = any(wf.tasks is not None and len(wf.tasks) > 0 for wf in workflows)
        
        if has_tasks:
            # Extended table with task information
            header = "## Workflows\n\n| Workflow Request | State | Created By | Age | Created On | Total Tasks | Completed | In Progress | Pending |\n"
            separator = "|------------------|-------|------------|-----|------------|-------------|-----------|-------------|----------|\n"
            rows = "".join(_format_workflow_row_with_tasks(wf, base_url) for wf in workflows)
        else:
            # Simple table without tasks
            header = "## Workflows\n\n| Workflow Request | State | Created By | Age | Created On |\n"
            separator = "|------------------|-------|------------|-----|------------|\n"
            rows = "".join(_format_workflow_row_basic(wf, base_url) for wf in workflows)
        
        formatted_output = f"{header}{separator}{rows}\nTotal: {len(workflows)} workflow(s)"
    
    return GetMyWorkflowsResponse(
        workflows=workflows,
        workflow_requests=None,
        total_count=len(workflows),
        active_count=None,
        completed_count=None,
        stalled_count=None,
        at_risk_count=None,
        formatted_output=formatted_output
    )


def _build_deep_dive_table_response(
    workflow_requests: List[WorkflowRequest],
    stalled_days: Optional[int],
    include_tasks: bool
) -> GetMyWorkflowsResponse:
    """
    Build response for deep dive mode with table format.
    
    Args:
        workflow_requests: List of workflow request objects
        stalled_days: Threshold for stalled detection
        include_tasks: Whether to include detailed task information in table
        
    Returns:
        GetMyWorkflowsResponse for deep dive table format
    """
    formatted_output = format_workflow_requests_as_tables(
        workflows=workflow_requests,
        base_url=str(tool_helper_service.base_url),
        stalled_days=stalled_days,
        include_tasks=include_tasks
    )
    LOGGER.info(f"Generated formatted tables for {len(workflow_requests)} workflows (include_tasks={include_tasks})")
    
    # Calculate summary statistics
    stats = calculate_workflow_statistics(workflow_requests, stalled_days)
    
    return GetMyWorkflowsResponse(
        workflows=None,
        workflow_requests=workflow_requests,  # Always include raw data
        total_count=len(workflow_requests),
        active_count=stats["active_count"],
        completed_count=stats["completed_count"],
        stalled_count=stats["stalled_count"],
        at_risk_count=stats["at_risk_count"],
        formatted_output=formatted_output  # Also include formatted output
    )


def _build_deep_dive_json_response(
    workflow_requests: List[WorkflowRequest],
    stats: dict
) -> GetMyWorkflowsResponse:
    """
    Build response for deep dive mode with JSON format.
    
    Args:
        workflow_requests: List of workflow request objects
        stats: Summary statistics dictionary
        
    Returns:
        GetMyWorkflowsResponse for deep dive JSON format
    """
    return GetMyWorkflowsResponse(
        workflows=None,
        workflow_requests=workflow_requests,
        total_count=len(workflow_requests),
        active_count=stats["active_count"],
        completed_count=stats["completed_count"],
        stalled_count=stats["stalled_count"],
        at_risk_count=stats["at_risk_count"],
        formatted_output=None
    )

get_my_workflows_description="""
    Use this tool when you need to retrieve workflows initiated by current user.

    This tool fetches workflow instances that you have created/initiated, with two modes:
    - Light mode (deep_dive=False): Returns basic workflow information for quick overview. If called in light mode, ask the user whether he would like to see the details.
    - Deep dive mode (deep_dive=True): Returns comprehensive analysis with task details, activity tracking, and metrics
    If you find markdown text in the result show it to the user.

    This is different from get_my_workflow_inbox_tasks which shows tasks assigned to you by others.

    Make sure to use a request json object for the parameters.
    """


async def _get_my_workflows(
    request: GetMyWorkflowsRequest,
    ctx: Optional[Context]
) -> GetMyWorkflowsResponse:
    """
    Get workflows initiated by current user.

    Args:
        request: GetMyWorkflowsRequest object containing filter parameters

    Returns:
        GetMyWorkflowsResponse object with workflows or workflow_requests based on deep_dive mode
    """
    LOGGER.info(
        f"Calling get_my_workflows with "
        f"max_results: {request.max_results}, "
        f"state: {request.state}, "
        f"deep_dive: {request.deep_dive}"
    )

    # Auto-detect clients that don't support rich text and switch to JSON format if needed
    # Some clients don't handle markdown tables well, so we default to JSON
    if (ctx is None or not supports_rich_text_format(ctx)) and request.deep_dive and request.format == "table":
        LOGGER.info("Client without rich text support detected: switching format from 'table' to 'json'")
        request.format = "json"

    if not request.deep_dive:
        # Light mode: return basic workflow information
        workflows = await _retrieve_my_workflows(
            max_results=request.max_results,
            state=request.state,
            include_tasks=request.include_tasks,
            workflow_id=request.workflow_id,
        )
        return _build_light_mode_response(workflows)
    
    # Deep dive mode: return comprehensive analysis
    LOGGER.info(
        f"Deep dive mode: include_tasks={request.include_tasks}, "
        f"stalled_days={request.stalled_days}, "
        f"workflow_id={request.workflow_id}, "
        f"format={request.format}"
    )
    
    workflow_requests = await _retrieve_my_workflows_deep_dive(
        max_results=request.max_results,
        state=request.state,
        include_tasks=request.include_tasks,
        stalled_days=request.stalled_days,
        workflow_id=request.workflow_id
    )
    
    # Calculate summary statistics
    stats = calculate_workflow_statistics(workflow_requests, request.stalled_days)
    
    # Generate output based on format
    if request.format == "table":
        return _build_deep_dive_table_response(workflow_requests, request.stalled_days, request.include_tasks)
    elif request.format == "json":
        return _build_deep_dive_json_response(workflow_requests, stats)
    else:
        raise ToolError("Invalid output format")


@service_registry.tool(
    name="get_my_workflows",
    annotations={
        "readOnlyHint": True,
        "title": "Get and Monitor My Initiated Workflows with Comprehensive Analytics"
    },
    description=get_my_workflows_description,
    tags={"workflow", "flowable", "governance", "glossary", "my_workflows"},
    meta={"version": "2.0", "service": "workflows"},
)
@auto_context
async def get_my_workflows(
    max_results: Annotated[int, Field(description="Maximum number of workflows to return")] = 50,
    state: Annotated[Optional[str], Field(description="Filter by workflow state (active, completed, suspended, etc.)")] = None,
    deep_dive: Annotated[bool, Field(description="When True, performs comprehensive analysis with task details, activity tracking, and metrics. When False, returns basic workflow information only.")] = False,
    include_tasks: Annotated[bool, Field(description="Include detailed task information for each workflow (only applicable when deep_dive=True)")] = True,
    stalled_days: Annotated[Optional[int], Field(description="Threshold for considering a workflow stalled (no activity in X days). Set to None to disable stalled detection (only applicable when deep_dive=True).")] = None,
    workflow_id: Annotated[Optional[str], Field(description="Get details for a specific workflow by ID (ignores other filters)")] = None,
    format: Annotated[str, Field(description="Output format: 'table' for formatted markdown tables, 'json' for raw data (only applicable when deep_dive=True)")] = "table",
    ctx: Optional[Context] = None
) -> GetMyWorkflowsResponse:
    """Wrapper version of get_my_workflows."""
    
    request = GetMyWorkflowsRequest(
        max_results=max_results,
        state=state,
        deep_dive=deep_dive,
        include_tasks=include_tasks,
        stalled_days=stalled_days,
        workflow_id=workflow_id,
        format=format
    )
    
    return await _get_my_workflows(request, ctx)
