# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing user tasks based on artifact id as object of a task.

This module provides functionality to query workflow API for user tasks.
"""

from typing import Any, Dict, List, Optional, cast
from app.core.registry import service_registry
from app.services.constants import WORKFLOW_BASE_ENDPOINT, WORKFLOW_TASK_ENDPOINT
from app.services.workflow.utils.task_utils import _parse_task_title_from_json
from app.services.workflow.models.list_user_tasks_approval_data_for_artifact import (
    ListUserTasksRequest,
    ListUserTasksResponse,
    UserTask
)
from app.services.workflow.utils.user_task_formatters import (
    format_user_tasks_as_table,
    format_user_tasks_as_list
)
from app.services.workflow.tools.utils import ZERO_MINUTES
from app.services.workflow.utils.user_mappers import convert_iam_id_to_email, process_candidate_users
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from app.shared.utils.client_detection import supports_rich_text_format


async def _retrieve_my_tasklist_from_workflow_inbox(
    max_results: int,
) -> List[UserTask]:
    """
    Retrieve list of tasks from workflow task inbox for a user.

    Args:
        max_results: int: Maximum number of tasks to return

    Returns:
        List[UserTask]: List of task objects
    """

    params = {}
    if max_results is not None:
        params['limit'] = max_results

    usertasks: List[UserTask] = []

    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}",
            params=params,
        )

        # Schema: data->resources[]->Items->(metadata, entity)
        response_data = cast(Dict[str, Any], response)
        item_list = cast(List[Dict[str, Any]], response_data.get("data", {}).get("resources", []))
        for user_task in item_list:
            usertask_metadata = user_task.get("metadata", {})
            usertask_entity = user_task.get("entity", {})
            
            # Process IAM ID to email conversions
            assignee_iam_id = usertask_entity.get("assignee")
            assignee = await convert_iam_id_to_email(assignee_iam_id, "assignee") if assignee_iam_id else None
            candidate_users = await process_candidate_users(usertask_entity.get("candidate_users"))
            
            task_title_raw = usertask_entity.get("task_title", "")
            task_title = _parse_task_title_from_json(task_title_raw) if task_title_raw else None

            user_task = UserTask(
                task_id=usertask_metadata.get("task_id"),
                name=usertask_metadata.get("name"),
                task_title=task_title or usertask_metadata.get("name"),
                task_instruction=usertask_entity.get("task_instruction"),
                state=usertask_entity.get("state"),  # state is in entity, not metadata
                assignee=assignee,
                claimed_at=usertask_entity.get("claimed_at"),
                completed_at=usertask_entity.get("completed"),
                candidate_users=candidate_users
            )
            usertasks.append(user_task)

        return usertasks

    except Exception as e:
        LOGGER.error(f"Error retrieving tasks from workflow inbox: {str(e)}")
        #raise ServiceError(f"Failed to retrieve tasks from workflow: {str(e)}")
        # return an empty list instead
        return usertasks


async def _query_user_tasks_by_artifact(artifact_id: str, draft: bool, max_results: int) -> List[UserTask]:
    """
    Query workflow API for user tasks.

    Args:
        artifact_id: str: artifact_id as search term
        draft: bool: true for artifacts in draft, false otherwise
        max_results: int: Maximum number of data classes to return

    Returns:
        List[UserTask]: List of user tasks related to specified artifact_id
    """

    params = {
       "artifact_id": artifact_id,
       "limit": max_results,
       "include_user_tasks": True,
    }
    if draft:
        params['return_active_workflows'] = True
        params['return_completed_workflows'] = False
    else:
        params['return_active_workflows'] = False
        params['return_completed_workflows'] = True

    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_BASE_ENDPOINT}",
            params=params
        )

        # Schema: { "offset": 3, "resources": [ { "metadata": { "name": "...", ...
        response_data = cast(Dict[str, Any], response)
        user_tasks: List[UserTask] = []
        workflows = cast(List[Dict[str, Any]], response_data.get("resources", []))

        for workflow in workflows:
            # ignore workflows whose last_action is not "update" (2) or "publish" (3)
            last_action = workflow.get("last_action")

            entity = workflow.get("entity", {})
            user_tasks_in = entity.get("user_tasks", [])
            for user_task_in in user_tasks_in:
                usertask_metadata = user_task_in.get("metadata", {})
                usertask_entity = user_task_in.get("entity", {})
                
                # Process IAM ID to email conversions
                assignee_iam_id = usertask_entity.get("assignee")
                assignee = await convert_iam_id_to_email(assignee_iam_id, "assignee") if assignee_iam_id else None
                candidate_users = await process_candidate_users(usertask_entity.get("candidate_users"))
                
                task_title_raw = usertask_entity.get("task_title", "")
                task_title = _parse_task_title_from_json(task_title_raw) if task_title_raw else None

                user_task = UserTask(
                    task_id=usertask_metadata.get("task_id"),
                    name=usertask_metadata.get("name"),
                    task_title=task_title or usertask_metadata.get("name"),
                    task_instruction=usertask_entity.get("task_instruction"),
                    state=usertask_metadata.get("state"),
                    assignee=assignee,
                    claimed_at=usertask_entity.get("claimed_at"),
                    completed_at=usertask_entity.get("completed"),
                    candidate_users=candidate_users
                )
                user_tasks.append(user_task)

        return user_tasks 

    except Exception as e:
        LOGGER.error(f"Error querying workflow user tasks: {str(e)}")
        return []

list_user_tasks_approval_data_for_artifact_description="""
list_user_tasks_approval_data_for_artifact returns a list user tasks in a data governance workflow for a specific artifact id along with
final state of the workflow to find out approvers in user task data.
ALWAYS define draft parameter: if text refers to future approvals set it true, otherwise false.

Use format='json' for raw task data or format='table' (default) for formatted output.
If you find markdown text in the result show it to the user.
ALWAYS render the result as table if called with format='table' parameter
"""


async def _list_user_tasks_approval_data_for_artifact(
    request: ListUserTasksRequest,
    ctx: Optional[Context]
) -> ListUserTasksResponse:
    """
    List workflow user tasks.

    Args:
        request: ListUserTasksRequest object with filter parameters

    Returns:
        ListUserTasksResponse object containing list of user tasks, total count
    """
    LOGGER.info(
        f"Listing user tasks with max_results: {request.max_results}, "
        f"format: {request.format}"
    )
    
    # Auto-detect Claude Code and switch to JSON format if needed
    # Some clients don't handle markdown tables well, so we default to JSON
    if ctx is not None and not supports_rich_text_format(ctx) and request.format == "table":
        LOGGER.info("Client without rich text support detected: switching format from 'table' to 'json'")
        request.format = "json"
    
    # Handle global artifact IDs (format: global_uuid_artifact_id)
    artifact_id = request.artifact_id
    if '_' in artifact_id:
        LOGGER.info(f"Global artifact ID detected: {artifact_id}")
        parts = artifact_id.split('_', 1)
        if len(parts) == 2:
            artifact_id = parts[1]
            LOGGER.info(f"Extracted artifact ID from global ID: {artifact_id}")
        else:
            LOGGER.warning(f"Unexpected global ID format: {artifact_id}")
    
    # Validate artifact_id length (should be 35 characters)
    if len(artifact_id) != 35:
        LOGGER.warning(
            f"Artifact ID length is {len(artifact_id)} characters, expected 35. "
            f"Proceeding with artifact_id: {artifact_id}"
        )
    
    # Query user tasks by artifact_id (now required parameter)
    user_tasks = await _query_user_tasks_by_artifact(
        artifact_id=artifact_id,
        draft=request.draft,
        max_results=request.max_results
    )

    # Generate output based on format
    if request.format == "table":
        formatted_output = format_user_tasks_as_table(
            user_tasks=user_tasks,
            base_url=str(tool_helper_service.base_url)
        )
        LOGGER.info(f"Generated formatted table for {len(user_tasks)} user tasks")
        # Always include both raw data and formatted output
        return ListUserTasksResponse(
            user_tasks=user_tasks,
            total_count=len(user_tasks),
            formatted_output=formatted_output
        )
    elif request.format == "list":
        formatted_output = format_user_tasks_as_list(
            user_tasks=user_tasks,
            base_url=str(tool_helper_service.base_url)
        )
        LOGGER.info(f"Generated formatted list for {len(user_tasks)} user tasks")
        # Always include both raw data and formatted output
        return ListUserTasksResponse(
            user_tasks=user_tasks,
            total_count=len(user_tasks),
            formatted_output=formatted_output
        )
    else:
        # format='json' - return raw data only (already includes user_tasks)
        return ListUserTasksResponse(
            user_tasks=user_tasks,
            total_count=len(user_tasks),
            formatted_output=None
        )


@service_registry.tool(
    name="list_user_tasks_approval_data_for_artifact",
    annotations={
        "readOnlyHint": True,
        "title": "List User Task Approval History and Data for Specific Artifacts"
    },
    description=list_user_tasks_approval_data_for_artifact_description,
    tags={"workflow", "glossary", "user_tasks", "governance"},
    meta={"version": "1.0", "service": "workflow"},
)
@auto_context
async def list_user_tasks_approval_data_for_artifact(
    artifact_id: str,
    max_results: int = 50,
    draft: bool = False,
    format: str = "table",
    ctx: Optional[Context] = None,
) -> ListUserTasksResponse:
    """Wrapper version of list_user_tasks_approval_data_for_artifact."""
    
    request = ListUserTasksRequest(
        artifact_id=artifact_id,
        max_results=max_results,
        draft=draft,
        format=format
    )
    
    return await _list_user_tasks_approval_data_for_artifact(request, ctx)
