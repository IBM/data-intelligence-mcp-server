# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import List, Optional
from datetime import datetime
from urllib.parse import urlparse
import warnings
import json

from app.core.registry import service_registry
from app.services.constants import WORKFLOW_TASK_ENDPOINT
from app.services.workflow.models.get_workflow_tasks_from_my_inbox import Task, GetMyTasksRequest, GetMyTasksResponse
from app.services.workflow.utils.task_formatters import format_tasks_as_table, sort_tasks_by_priority
from app.services.workflow.tools.utils import ZERO_MINUTES
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service

from fastmcp.exceptions import ToolError

def transform_base_url_to_ui_url(input_url: str) -> str:
    """Transform API base URL to UI URL for workflow tasks."""
    hostname = None
    if input_url is not None:
        parsed = urlparse(input_url)
        hostname = parsed.hostname

        if hostname is not None and hostname.startswith("api."):
            hostname = hostname[len("api."):]

    if hostname is None:
        hostname = 'localhost'
    
    return f"https://{hostname}/governance/workflow/tasks?taskId="

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


def _parse_task_title_from_json(task_title_raw: str) -> Optional[str]:
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
        
        # Extract artifact type from the translation key
        artifact_type = "artifact"
        if "glossary_term" in artifact_type_key:
            artifact_type = "Business term"
        elif "data_class" in artifact_type_key:
            artifact_type = "Data class"
        elif "category" in artifact_type_key:
            artifact_type = "Category"
        
        # Replace placeholders in the template
        return default_message.replace("{artifactType}", artifact_type).replace("{artifactName}", artifact_name)
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        LOGGER.debug(f"Failed to parse task_title JSON: {e}")
        return task_title_raw


def _create_task_from_data(task_data: dict) -> Task:
    """
    Create a Task object from raw task data.
    
    Args:
        task_data: Raw task data from API
        
    Returns:
        Task object
    """
    metadata = task_data.get("metadata", {})
    entity = task_data.get("entity", {})
    
    # Convert variables list to dict
    variables_list = entity.get("variables", [])
    variables_dict = _convert_variables_to_dict(variables_list)
    
    # Parse task_title to extract the formatted title
    task_title_raw = entity.get("task_title", "")
    task_title = _parse_task_title_from_json(task_title_raw) if task_title_raw else None
    
    # If task_title is still None, fall back to task_name
    if task_title is None:
        task_title = metadata.get("name", "Untitled Task")
    
    # Parse due_date if present
    due_date = None
    if entity.get("due_date"):
        due_date = datetime.fromisoformat(entity.get("due_date").replace("Z", ZERO_MINUTES))
    
    return Task(
        task_id=metadata.get("task_id"),
        task_name=metadata.get("name", "Untitled Task"),
        task_title=task_title,
        workflow_id=metadata.get("workflow_id", ""),
        workflow_template_id=metadata.get("workflow_type_id", ""),
        created_at=datetime.fromisoformat(metadata.get("created_at").replace("Z", ZERO_MINUTES)),
        due_date=due_date,
        priority=entity.get("priority"),
        assignee=entity.get("assignee"),
        form_key=entity.get("form_key"),
        state=metadata.get("state"),
        variables=variables_dict
    )


async def _retrieve_my_tasklist_from_workflow(
    max_results: int,
) -> List[Task]:
    """
    Retrieve list of tasks from workflow task inbox for a user.

    Args:
        max_results: Maximum number of tasks to return

    Returns:
        List[Task]: List of task objects
    """
    params = {
        'unassigned': 'false',
        'completed': 'false',
        'hide_authoring_tasks': 'false',
        'count_only': 'false'
    }
    if max_results is not None:
        params['limit'] = str(max_results)

    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}",
            params=params,
        )

        # Schema: resources[]->Items->(metadata, entity)
        item_list = response.get('resources', [])
        return [_create_task_from_data(task_data) for task_data in item_list]

    except Exception as e:
        LOGGER.error(f"Error retrieving tasks from workflow: {str(e)}")
        return []


def _build_task_url(task_id: str) -> str:
    """
    Build the URL to access a task instance in Workflow.

    Args:
        task_id: str: Task ID

    Returns:
        str: Complete URL to the task
    """
    return f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}/{task_id}"


@service_registry.tool(
    name="get_workflow_tasks_from_my_inbox",
    description="""
    Retrieve tasks from workflow task inbox for the current user.

    This tool fetches tasks assigned to you or tasks you are candidates for in governance workflows.
    
    Use format='json' for raw task data or format='table' (default) for formatted output.
    ALWAYS render the result as table if called with format='table' parameter

    Make sure to use a request json object for the parameters.
    """,
    tags={"workflow", "flowable", "tasks", "governance", "glossary"},
    meta={"version": "2.0", "service": "task_inbox"},
)

@auto_context
async def get_workflow_tasks_from_my_inbox(
    request: GetMyTasksRequest,
) -> GetMyTasksResponse:
    """
    Get tasks from workflow task inbox for the current user.

    Args:
        request: GetMyTasksRequest object containing filter parameters

    Returns:
        GetMyTasksResponse object containing list of tasks, total count, and optional formatted output
    """
    LOGGER.info(
        f"Calling get_workflow_tasks_from_my_inbox with "
        f"max_results: {request.max_results}, "
        f"format: {request.format}"
    )

    tasks = await _retrieve_my_tasklist_from_workflow(
        max_results=request.max_results,
    )

    # Sort tasks by priority: Overdue > At Risk > Claimed > Unclaimed
    tasks = sort_tasks_by_priority(tasks)
    LOGGER.info(f"Sorted {len(tasks)} tasks by priority")

    # Generate output based on format
    if request.format == "table":
        formatted_output = format_tasks_as_table(
            tasks=tasks,
            base_url=transform_base_url_to_ui_url(tool_helper_service.base_url)  # api.xxxxx.com/v3 ... -> xxxxx.com/governance/workflow
        )
        LOGGER.info(f"Generated formatted table for {len(tasks)} tasks")
        return GetMyTasksResponse(
            tasks=None,
            total_count=len(tasks),
            formatted_output=formatted_output
        )
    else:
        # format='json' - return raw data only
        return GetMyTasksResponse(
            tasks=tasks,
            total_count=len(tasks),
            formatted_output=None
        )


@service_registry.tool(
    name="get_workflow_tasks_from_my_inbox",
    description="""Watsonx Orchestrator compatible wrapper for get_workflow_tasks_from_my_inbox
    Retrieve tasks from workflow task inbox for the current user.

    This tool fetches tasks assigned to you or tasks you are candidates for in governance workflows.
    
    Returns tasks in a formatted table showing:
    - Task Title (clickable link to task)
    - Claimed status (shows "Yes" if you've claimed the task, empty if unclaimed)
    - Assigned time (how long ago the task was created, e.g., "2 days ago")
    - Due date with status indicators:
      * Normal: "YYYY-MM-DD" (due date more than 48 hours away)
      * At Risk: "⚠️ YYYY-MM-DD" (due within 48 hours)
      * Overdue: "❌ YYYY-MM-DD" (past due date)
    
    Use format='json' for raw task data or format='table' (default) for formatted output.

    Make sure to use a request json object for the parameters.
    """,
    tags={"wxo", "workflow", "flowable", "tasks", "governance", "glossary"},
    meta={"version": "2.0", "service": "task_inbox"},
)
@auto_context
async def wxo_get_workflow_tasks_from_my_inbox(
    max_results: int = 50,
    format: str = "table",
) -> GetMyTasksResponse:
    """Watsonx Orchestrator compatible version of get_workflow_tasks_from_my_inbox."""
    
    request = GetMyTasksRequest(
        max_results=max_results,
        format=format
    )
    
    return await get_workflow_tasks_from_my_inbox(request)
