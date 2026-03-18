# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for retrieving workflows initiated by the current user.

This module provides functionality to monitor workflows you've created, with two modes:
- Light mode (deep_dive=False): Returns basic workflow information for quick overview
- Deep dive mode (deep_dive=True): Returns comprehensive analysis with task details, activity tracking, and metrics
"""

from typing import List, Optional
from datetime import datetime, timezone
import json

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
from app.services.workflow.utils.workflow_request_formatters import (
    format_workflow_requests_as_tables,
    calculate_workflow_statistics
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from fastmcp.exceptions import ToolError


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
        artifact_name = task_title_json.get("artifactName", "")
        artifact_type_key = task_title_json.get("§artifactType", "")
        
        # Extract artifact type
        artifact_type = "artifact"
        if "glossary_term" in artifact_type_key:
            artifact_type = "Business term"
        elif "data_class" in artifact_type_key:
            artifact_type = "Data class"
        elif "category" in artifact_type_key:
            artifact_type = "Category"
        
        # Replace placeholders to get the full title
        title = default_message.replace("{artifactType}", artifact_type).replace("{artifactName}", artifact_name)
        return title
    except (json.JSONDecodeError, KeyError, AttributeError):
        return None


async def _get_workflow_title_from_tasks(workflow_id: str) -> Optional[str]:
    """
    Get the workflow title by querying the first task associated with this workflow.
    The task_title contains the user-friendly name like "Update Business term Address Line".
    """
    params = {
        'workflow_id': workflow_id,
        'limit': '1'
    }
        
    response = []
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}",
            params=params,
        )
    except Exception as e:
        raise ToolError(f"Could not fetch workflow title for {workflow_id}: {e}")

        
    tasks = response.get('resources', [])
    if tasks:
        task = tasks[0]
        entity = task.get("entity", {})
        if entity is not None:
            task_title_raw = entity.get("task_title", "")
            
            if task_title_raw:
                return _parse_task_title(task_title_raw)
        
    return None
        

def _convert_variables_to_dict(variables_list) -> dict:
    """
    Convert variables from list format to dictionary.
    
    Args:
        variables_list: Variables in list or dict format
        
    Returns:
        Dictionary mapping variable names to values
    """
    if isinstance(variables_list, dict):
        return variables_list
    
    variables_dict = {}
    if isinstance(variables_list, list):
        for var in variables_list:
            if isinstance(var, dict) and 'name' in var and 'value' in var:
                variables_dict[var['name']] = var['value']
    return variables_dict


def _create_workflow_from_data(workflow_data: dict, workflow_title: Optional[str]) -> Workflow:
    """
    Create a Workflow object from raw workflow data.
    
    Args:
        workflow_data: Raw workflow data from API
        workflow_title: Parsed workflow title from tasks (optional)
        
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
    
    # Use the title from tasks if available, otherwise fall back to entity name
    workflow_name = workflow_title if workflow_title else entity.get("name", "Untitled Workflow")
    
    return Workflow(
        workflow_id=workflow_id,
        name=workflow_name,
        description=entity.get("description"),
        workflow_template_id=metadata.get("workflow_type_id", ""),
        state=metadata.get("state", "unknown"),
        created_at=datetime.fromisoformat(metadata.get("created_at").replace("Z", ZERO_MINUTES)),
        created_by=metadata.get("created_by"),
        business_key=entity.get("business_key"),
        variables=variables_dict
    )


async def _retrieve_my_workflows(
    max_results: int,
    state: Optional[str] = None,
) -> List[Workflow]:
    """
    Retrieve list of workflows initiated by the current user.

    Args:
        max_results: Maximum number of workflows to return
        state: Optional state filter (active, completed, suspended, etc.)

    Returns:
        List[Workflow]: List of workflow objects
    """
    params = {}
    if max_results is not None:
        params['limit'] = str(max_results)
    
    if state is not None:
        params['state'] = state

    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_BASE_ENDPOINT}",
            params=params,
        )

        # Parse the response
        workflow_list = response.get('resources', [])
        workflows = []
        
        for workflow_data in workflow_list:
            metadata = workflow_data.get("metadata", {})
            workflow_id = metadata.get("workflow_id")
            
            # Get the workflow title from associated tasks
            workflow_title = await _get_workflow_title_from_tasks(workflow_id)
            
            # Create workflow object
            workflow = _create_workflow_from_data(workflow_data, workflow_title)
            workflows.append(workflow)

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


def _create_task_detail(task_data: dict) -> TaskDetail:
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
    if state == "2":  # Completed
        completed_at = _parse_completed_timestamp(entity.get("completed"))
    
    return TaskDetail(
        task_id=metadata.get("task_id"),
        task_title=task_title,
        task_name=metadata.get("name", "Untitled Task"),
        state=state,
        assignee=entity.get("assignee"),
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
        return [_create_task_detail(task_data) for task_data in task_list]
        
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
        "completed_tasks": sum(1 for t in tasks if t.state == "2"),
        "in_progress_tasks": sum(1 for t in tasks if t.state == "1"),
        "pending_tasks": sum(1 for t in tasks if t.state == "0")
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
        if task.state != "2" and task.assignee and task.assignee not in assignees:
            assignees.append(task.assignee)
    return assignees


def _calculate_last_activity(workflow_data: dict, tasks: List[TaskDetail]) -> Optional[datetime]:
    """
    Calculate the last activity timestamp for a workflow.
    
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
    workflow_id: Optional[str]
) -> dict:
    """
    Build query parameters for workflow API request.
    
    Args:
        max_results: Maximum number of workflows to return
        state: Filter by state
        workflow_id: Specific workflow ID to query
        
    Returns:
        Dictionary of query parameters
    """
    params = {}
    
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
    
    # Get workflow title
    workflow_title = await _get_workflow_title_from_tasks(wf_id)
    workflow_name = workflow_title if workflow_title else entity.get("name", "Untitled Workflow")
    
    # Get tasks for this workflow
    tasks = await _get_tasks_for_workflow(wf_id)
    
    # Calculate metrics
    metrics = _calculate_workflow_metrics(workflow_data, tasks, stalled_days)
    
    return WorkflowRequest(
        workflow_id=wf_id,
        name=workflow_name,
        description=entity.get("description"),
        workflow_template_id=metadata.get("workflow_type_id", ""),
        state=metadata.get("state", "unknown"),
        created_at=datetime.fromisoformat(metadata.get("created_at").replace("Z", ZERO_MINUTES)),
        created_by=metadata.get("created_by"),
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
    Retrieve workflow requests initiated by the current user with detailed analysis (deep dive mode).
    
    Args:
        max_results: Maximum number of workflows to return
        state: Filter by state (active, completed, or None for all)
        include_tasks: Whether to include detailed task information
        stalled_days: Threshold for stalled detection
        workflow_id: Specific workflow ID to query
        
    Returns:
        List of WorkflowRequest objects
    """
    params = _build_workflow_query_params(max_results, state, workflow_id)
    
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


def _build_light_mode_response(workflows: List[Workflow]) -> GetMyWorkflowsResponse:
    """
    Build response for light mode (basic workflow information).
    
    Args:
        workflows: List of workflow objects
        
    Returns:
        GetMyWorkflowsResponse for light mode
    """
    return GetMyWorkflowsResponse(
        workflows=workflows,
        workflow_requests=None,
        total_count=len(workflows),
        active_count=None,
        completed_count=None,
        stalled_count=None,
        at_risk_count=None,
        formatted_output=None
    )


def _build_deep_dive_table_response(
    workflow_requests: List[WorkflowRequest],
    stalled_days: Optional[int]
) -> GetMyWorkflowsResponse:
    """
    Build response for deep dive mode with table format.
    
    Args:
        workflow_requests: List of workflow request objects
        stalled_days: Threshold for stalled detection
        
    Returns:
        GetMyWorkflowsResponse for deep dive table format
    """
    formatted_output = format_workflow_requests_as_tables(
        workflows=workflow_requests,
        base_url=str(tool_helper_service.base_url),
        stalled_days=stalled_days
    )
    LOGGER.info(f"Generated formatted tables for {len(workflow_requests)} workflows")
    
    return GetMyWorkflowsResponse(
        workflows=None,
        workflow_requests=None,
        total_count=len(workflow_requests),
        active_count=None,
        completed_count=None,
        stalled_count=None,
        at_risk_count=None,
        formatted_output=formatted_output
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


@service_registry.tool(
    name="get_my_workflows",
    description="""
    Retrieve workflows initiated by the current user.

    This tool fetches workflow instances that you have created/initiated, with two modes:
    - Light mode (deep_dive=False): Returns basic workflow information for quick overview
    - Deep dive mode (deep_dive=True): Returns comprehensive analysis with task details, activity tracking, and metrics

    This is different from get_workflow_tasks_from_my_inbox which shows tasks assigned to you by others.

    Make sure to use a request json object for the parameters.
    """,
    tags={"workflow", "flowable", "governance", "glossary", "my_workflows"},
    meta={"version": "2.0", "service": "workflows"},
)

@auto_context
async def get_my_workflows(
    request: GetMyWorkflowsRequest,
) -> GetMyWorkflowsResponse:
    """
    Get workflows initiated by the current user.

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

    if not request.deep_dive:
        # Light mode: return basic workflow information
        workflows = await _retrieve_my_workflows(
            max_results=request.max_results,
            state=request.state,
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
        return _build_deep_dive_table_response(workflow_requests, request.stalled_days)
    elif request.format == "json":
        return _build_deep_dive_json_response(workflow_requests, stats)
    else:
        raise ToolError("Invalid output format")


@service_registry.tool(
    name="get_my_workflows",
    description="""Watsonx Orchestrator compatible wrapper for get_my_workflows.
    Retrieve workflows initiated by the current user.

    This tool fetches workflow instances that you have created/initiated, with two modes:
    - Light mode (deep_dive=False): Returns basic workflow information for quick overview
    - Deep dive mode (deep_dive=True): Returns comprehensive analysis with task details, activity tracking, and metrics

    This is different from get_workflow_tasks_from_my_inbox which shows tasks assigned to you by others.

    Make sure to use a request json object for the parameters.

    """,
    tags={"wxo", "workflow", "flowable", "governance", "glossary", "my_workflows"},
    meta={"version": "2.0", "service": "workflows"},
)
@auto_context
async def wxo_get_my_workflows(
    max_results: int = 50,
    state: str = None,
    deep_dive: bool = False,
    include_tasks: bool = True,
    stalled_days: int = None,
    workflow_id: str = None,
    format: str = "table",
) -> GetMyWorkflowsResponse:
    """Watsonx Orchestrator compatible version of get_my_workflows."""
    
    request = GetMyWorkflowsRequest(
        max_results=max_results,
        state=state,
        deep_dive=deep_dive,
        include_tasks=include_tasks,
        stalled_days=stalled_days,
        workflow_id=workflow_id,
        format=format
    )
    
    return await get_my_workflows(request)
