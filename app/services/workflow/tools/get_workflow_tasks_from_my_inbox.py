# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Annotated, List, Optional
from datetime import datetime, timezone
from urllib.parse import urlparse
import warnings
from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import WORKFLOW_TASK_ENDPOINT
from app.services.workflow.models.get_workflow_tasks_from_my_inbox import Task, GetMyTasksRequest, GetMyTasksResponse
from app.services.workflow.utils.task_formatters import format_tasks_as_table, sort_tasks_by_priority
from app.services.workflow.utils.task_utils import _convert_variables_to_dict, _parse_task_title_from_json
from app.services.workflow.tools.utils import ZERO_MINUTES
from app.services.workflow.utils.user_mappers import convert_iam_id_to_email, process_candidate_users
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.client_detection import supports_rich_text_format
from app.core.settings import settings, ENV_MODE_SAAS

from fastmcp.server.context import Context
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

    if settings.di_env_mode.upper() != ENV_MODE_SAAS:
        return f"{hostname}/gov/workflow/tasks?taskId="
    else:
        return f"{hostname}/governance/workflow/tasks?taskId="

def _extract_task_title(metadata: dict, entity: dict) -> str:
    """
    Extract and format task title from metadata and entity.
    
    Args:
        metadata: Task metadata dictionary
        entity: Task entity dictionary
        
    Returns:
        Formatted task title
    """
    task_title_raw = entity.get("task_title", "")
    task_title = _parse_task_title_from_json(task_title_raw) if task_title_raw else None
    
    if task_title is None:
        task_title = metadata.get("name", "Untitled Task")
    
    return task_title


def _parse_due_date(due_date_str: str) -> Optional[datetime]:
    """
    Parse due date string to datetime object.
    
    Args:
        due_date_str: Due date string from API
        
    Returns:
        datetime object if parsing succeeds, None otherwise
    """
    if not due_date_str:
        return None
    return datetime.fromisoformat(due_date_str.replace("Z", ZERO_MINUTES))


async def _create_task_from_data(task_data: dict) -> Task:
    """
    Create a Task object from raw task data.
    
    Args:
        task_data: Raw task data from API
        
    Returns:
        Task object
    """
    metadata = task_data.get("metadata", {})
    entity = task_data.get("entity", {})
    
    # Extract and process data
    variables_dict = _convert_variables_to_dict(entity.get("variables", []))
    task_title = _extract_task_title(metadata, entity)
    claimed_at = _parse_due_date(entity.get("claimed_at"))  # Reuse _parse_due_date for datetime parsing
    due_date = _parse_due_date(entity.get("due_date"))
    
    # Process IAM ID to email conversions
    assignee_iam_id = entity.get("assignee")
    assignee = await convert_iam_id_to_email(assignee_iam_id, "assignee") if assignee_iam_id else None
    candidate_users = await process_candidate_users(entity.get("candidate_users"))
    
    # Parse created_at with proper null handling
    created_at_str = metadata.get("created_at")
    if created_at_str:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", ZERO_MINUTES))
    else:
        # Fallback to current time if created_at is missing
        created_at = datetime.now(timezone.utc)
        LOGGER.warning(f"Task {metadata.get('task_id')} missing created_at, using current time")
    
    # Build and return Task object
    return Task(
        task_id=metadata.get("task_id"),
        task_name=metadata.get("name", "Untitled Task"),
        task_title=task_title,
        workflow_id=metadata.get("workflow_id", ""),
        workflow_template_id=metadata.get("workflow_type_id", ""),
        created_at=created_at,
        claimed_at=claimed_at,
        due_date=due_date,
        priority=entity.get("priority"),
        assignee=assignee,
        form_key=entity.get("form_key"),
        state=metadata.get("state"),
        candidate_users=candidate_users,
        candidate_groups=entity.get("candidate_groups"),
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
        tasks = []
        for task_data in item_list:
            task = await _create_task_from_data(task_data)
            tasks.append(task)
        return tasks

    except Exception as e:
        # Log the exception type and details for debugging
        LOGGER.error(f"Error retrieving tasks from workflow: {type(e).__name__}: {str(e)}")
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

get_workflow_tasks_from_my_inbox_description="""
    Use this tool when you need to retrieve tasks from workflow task inbox for the current user.

    This tool fetches tasks assigned to you or tasks you are candidates for in governance workflows.
    
    Use format='json' for raw task data or format='table' (default) for formatted output.
    If you find markdown text in the result show it to the user.
    ALWAYS render the result as table if called with format='table' parameter

    Make sure to use a request json object for the parameters.
    Returns: The list of workflow tasks assigned to the current user, total count, and optionally a formatted markdown table for display.
    """

async def _get_workflow_tasks_from_my_inbox(
    request: GetMyTasksRequest,
    ctx: Context
) -> GetMyTasksResponse:
    """
    Get tasks from workflow task inbox for the current user.

    Args:
        request: GetMyTasksRequest object containing filter parameters

    Returns:
        GetMyTasksResponse object containing list of tasks, total count, and optional formatted output
    """
    LOGGER.info(
        f"Calling get_my_workflow_inbox_tasks with "
        f"max_results: {request.max_results}, "
        f"format: {request.format}"
    )
    
    # Auto-detect clients that don't support rich text and switch to JSON format if needed
    # Some clients don't handle markdown tables well, so we default to JSON
    if not supports_rich_text_format(ctx) and request.format == "table":
        LOGGER.info("Client without rich text support detected: switching format from 'table' to 'json'")
        request.format = "json"

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
        # Always include both raw data and formatted output
        return GetMyTasksResponse(
            tasks=tasks,
            total_count=len(tasks),
            formatted_output=formatted_output
        )
    else:
        # format='json' - return raw data only (already includes tasks)
        return GetMyTasksResponse(
            tasks=tasks,
            total_count=len(tasks),
            formatted_output=None
        )


@service_registry.tool(
    name="get_my_workflow_inbox_tasks",
    annotations={
        "readOnlyHint": True,
        "title": "Get Workflow Tasks Assigned to Me from My Inbox"
    },
    description=get_workflow_tasks_from_my_inbox_description,
    tags={"workflow", "flowable", "tasks", "governance", "glossary"},
    meta={"version": "2.0", "service": "task_inbox"},
)
@auto_context
async def get_my_workflow_inbox_tasks(
    max_results: Annotated[int, Field(description="Maximum number of tasks to return")] = 50,
    format: Annotated[str, Field(description="Output format: 'table' for formatted markdown table, 'json' for raw task data")] = "table",
    ctx: Context = None,
) -> GetMyTasksResponse:
    """Wrapper version of get_my_workflow_inbox_tasks."""
    
    request = GetMyTasksRequest(
        max_results=max_results,
        format=format
    )
    
    return await _get_workflow_tasks_from_my_inbox(request, ctx)
