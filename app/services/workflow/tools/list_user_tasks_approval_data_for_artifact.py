# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing user tasks based on artifact id as object of the task.

This module provides functionality to query the workflow API for user tasks.
"""

from typing import List, Dict
from app.core.registry import service_registry
from app.services.constants import WORKFLOW_BASE_ENDPOINT, WORKFLOW_TASK_ENDPOINT
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
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError
from fastmcp.exceptions import ToolError

async def _retrieve_my_tasklist_from_workflow_inbox(
    #include_assigned: bool,
    #include_candidate: bool,
    max_results: int,
) -> List[UserTask]:
    """
    Retrieve list of tasks from workflow task inbox for a user.

    Args:
        user_id: str: User ID to retrieve tasks for
        max_results: int: Maximum number of tasks to return

    Returns:
        List[UserTask]: List of task objects
    """

    params = {}
    if max_results is not None:
        params['limit'] = max_results

    #"userId": user_id,
    #sort=created_at&unassigned=false&completed=false&hide_authoring_tasks=false&count_only=false

    usertasks = []

    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}",
            params=params,
        )

        # Schema: data->resources[]->Items->(metadata, entity)
        item_list = []
        if response.get("data", None) is not None:
            item_list = response['data'].get('resources', [])
        for user_task in item_list:
            usertask_metadata = user_task.get("metadata", {})
            usertask_entity = user_task.get("entity", {})
            user_task = UserTask(
                name=usertask_metadata.get("name"),
                task_title=usertask_entity.get("task_title"),
                task_instruction=usertask_entity.get("task_instruction"),
                state=usertask_entity.get("state"),  # state is in entity, not metadata
                assignee=usertask_entity.get("assignee"),
                completed_at=usertask_entity.get("completed"),
                candidate_users=usertask_entity.get("candidate_users")
            )
            print("TASK", user_task)
            usertasks.append(user_task)

        return usertasks

    except Exception as e:
        LOGGER.error(f"Error retrieving tasks from workflow inbox: {str(e)}")
        #raise ServiceError(f"Failed to retrieve tasks from workflow: {str(e)}")
        # return an empty list instead
        return usertasks


async def _query_user_tasks_by_artifact(artifact_id: str, draft: bool, max_results: int) -> List[UserTask]:
    """
    Query the workflow API for user tasks.

    Args:
        artifact_id: str: artifact_id as search term
        draft: bool: true for artifacts in draft, false otherwise
        max_results: int: Maximum number of data classes to return

    Returns:
        List[UserTask]: List of user tasks related to the specified artifact_id
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
        user_tasks = []
        if response.get("resources", None) is not None:
            workflows = response['resources'] #.get('resources', [])

        print("WORKFLOWS", workflows)
        for workflow in workflows:

            # ignore workflows whose last_action is not "update" (2) or "publish" (3)
            last_action = workflow.get("last_action")
            print("WORKFLOW LAST ACTION", last_action)

            entity = workflow.get("entity", {})
            user_tasks_in = entity.get("user_tasks", [])
            for user_task_in in user_tasks_in:
                usertask_metadata = user_task_in.get("metadata", {})
                usertask_entity = user_task_in.get("entity", {})
                user_task = UserTask(
                    name=usertask_metadata.get("name"),
                    task_title=usertask_entity.get("task_title"),
                    task_instruction=usertask_entity.get("task_instruction"),
                    state=usertask_metadata.get("state"),
                    assignee=usertask_entity.get("assignee"),
                    completed_at=usertask_entity.get("completed"),
                    candidate_users=usertask_entity.get("candidate_users")
                )
                user_tasks.append(user_task)

        return user_tasks 

    except Exception as e:
        LOGGER.error(f"Error querying workflow user tasks: {str(e)}")
        return []


@service_registry.tool(
    name="list_user_tasks_approval_data_for_artifact",
    description="""
list_user_tasks_approval_data_for_artifact returns a list user tasks in a data governance workflow for a specific artifact id along with the
final state of the workflow to find out approvers in user task data.
If you find markdown text in the result show it to the user.
Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.

Use the formatted output in your answer.
    """,
    tags={"workflow", "glossary", "user_tasks", "governance"},
    meta={"version": "1.0", "service": "workflow"},
)
@auto_context
async def list_user_tasks_approval_data_for_artifact(
    request: ListUserTasksRequest
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
    print("Listing user tasks with max_results:", request.max_results, ", format", request.format)

    user_tasks = []
    if request.artifact_id is not None:
        user_tasks = await _query_user_tasks_by_artifact(
            artifact_id=request.artifact_id,
            draft=request.draft,
            max_results=request.max_results
        )
    else:
        user_tasks = await _retrieve_my_tasklist_from_workflow_inbox(
            max_results=request.max_results
        )
    
    print("ALL USER TASKS\n", user_tasks)
        

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
    description="""Watsonx Orchestrator compatible wrapper list_user_tasks_approval_data_for_artifact.
list_user_tasks_approval_data_for_artifact returns a list user tasks in a data governance workflow for a specific artifact id along with the
final state of the workflow to find out approvers in user task data.
Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.

Use the formatted output in your answer.
    """,
    tags={"workflow", "wxo", "glossary", "user_tasks", "governance"},
    meta={"version": "1.0", "service": "workflow"},
)
@auto_context
async def wxo_list_user_tasks_approval_data_for_artifact(
    artifact_id: str = None,
    max_results: int = 50,
    draft: bool = False,
    format: str = "table",
) -> ListUserTasksResponse:
    """Watsonx Orchestrator compatible version of list_user_tasks_approval_data_for_artifact."""
    
    request = ListUserTasksRequest(
        artifact_id=artifact_id,
        max_results=max_results,
        draft=draft,
        format=format
    )
    
    return await list_user_tasks_approval_data_for_artifact(request)
