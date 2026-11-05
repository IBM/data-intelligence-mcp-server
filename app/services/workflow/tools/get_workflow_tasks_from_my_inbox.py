# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from typing import Annotated, List, Optional, Tuple  # noqa: I001, UP035 # Baseline
from datetime import datetime, timezone, UTC  # noqa: F401 # Baseline
from urllib.parse import urlparse
from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import WORKFLOW_TASK_ENDPOINT
from app.services.workflow.models.get_workflow_tasks_from_my_inbox import (
    Task,
    GetMyTasksRequest,
    GetMyTasksResponse,
)
from app.services.workflow.utils.task_formatters import (
    filter_tasks_by_date_range,
    format_tasks_as_table,
    inbox_task_categorizer,
    sort_tasks_by_sort_key,
)
from app.shared.models.pagination import PageCursor
from app.shared.utils.list_strategies import build_semantic_summary
from app.services.workflow.utils.task_utils import (
    _convert_variables_to_dict,
    _parse_task_title_from_json,
)
from app.services.workflow.tools.utils import ZERO_MINUTES
from app.services.workflow.utils.user_mappers import (
    convert_iam_id_to_email,
    process_candidate_users,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.client_detection import supports_rich_text_format
from app.core.settings import settings, ENV_MODE_SAAS
from app.shared.exceptions.base import ServiceError, ExternalAPIError

from fastmcp.server.context import Context


def transform_base_url_to_ui_url(input_url: str) -> str:
    """Transform API base URL to UI URL for workflow tasks."""

    hostname = None
    if input_url is not None:
        parsed = urlparse(input_url)
        hostname = parsed.hostname

        if hostname is not None and hostname.startswith("api."):
            hostname = hostname[len("api.") :]

    if hostname is None:
        hostname = "localhost"

    if settings.di_env_mode.upper() != ENV_MODE_SAAS:
        return f"{hostname}/gov/workflow/tasks?taskId="
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


def _parse_due_date(due_date_str: str) -> Optional[datetime]:  # noqa: UP045 # Baseline
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
    claimed_at = _parse_due_date(
        entity.get("claimed_at")
    )  # Reuse _parse_due_date for datetime parsing
    due_date = _parse_due_date(entity.get("due_date"))

    # Process IAM ID to email conversions
    assignee_iam_id = entity.get("assignee")
    assignee = (
        await convert_iam_id_to_email(assignee_iam_id, "assignee")
        if assignee_iam_id
        else None
    )
    candidate_users = await process_candidate_users(entity.get("candidate_users"))

    # Parse created_at with proper null handling
    created_at_str = metadata.get("created_at")
    if created_at_str:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", ZERO_MINUTES))
    else:
        # Fallback to current time if created_at is missing
        created_at = datetime.now(UTC)
        LOGGER.warning(
            f"Task {metadata.get('task_id')} missing created_at, using current time"
        )

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
        variables=variables_dict,
    )


# Maps the logical urgency filter to the server-side `urgency` query parameter value.
# 'all' (or None) is not forwarded. Server accepts: overdue, due_soon, due_later.
_SERVER_SIDE_URGENCY_MAP: dict[str, str] = {
    "overdue": "overdue",
    "at_risk": "due_soon",
}

# Upper bound on backend requests used to fill one page when client-side filters drop items.
MAX_FILL_REQUESTS = 20


def _format_server_datetime(value: datetime) -> str:
    """Format a datetime as the UTC ISO 8601 string expected by the workflow API (e.g. 1979-01-22T01:23:45.000Z)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    value = value.astimezone(UTC)
    return f"{value:%Y-%m-%dT%H:%M:%S}.{value.microsecond // 1000:03d}Z"


def _apply_server_side_filters(
    params: dict[str, str],
    urgency: Optional[str],  # noqa: UP045 # Baseline
    due_before: Optional[datetime],  # noqa: UP045 # Baseline
) -> None:
    """Add the filters the workflow API supports natively to the query params (in place)."""
    server_urgency = _SERVER_SIDE_URGENCY_MAP.get(urgency or "")
    if server_urgency:
        params["urgency"] = server_urgency
    if due_before is not None:
        params["due_before"] = _format_server_datetime(due_before)


async def _get_total_task_count(
    urgency: Optional[str] = None,  # noqa: UP045 # Baseline
    due_before: Optional[datetime] = None,  # noqa: UP045 # Baseline
) -> int:
    """
    Fetch the total number of tasks in the workflow task inbox using count_only=true.

    Args:
        urgency: Optional urgency filter ('overdue', 'at_risk', 'all'), applied server-side.
        due_before: Optional upper due date bound, applied server-side.

    Returns:
        int: Total task count or -1 if the count could not be retrieved.
    """
    params = {
        "unassigned": "false",
        "completed": "false",
        "hide_authoring_tasks": "false",
        "count_only": "true",
    }
    _apply_server_side_filters(params, urgency, due_before)
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}",
            params=params,
        )
        # Flowable / WKC count endpoint usually returns {"total_count": N} or {"count": N} or integer
        if isinstance(response, dict):
            if "total_count" in response:
                return int(response["total_count"])
            if "count" in response:
                return int(response["count"])
            if "total" in response:
                return int(response["total"])
        elif isinstance(response, int):
            return response
        return -1
    except Exception as e:
        LOGGER.warning(f"Failed to retrieve total task count via count_only=true: {e}")
        return -1


# Maps each logical sort key to the server-side `sort` query parameter value.
# The API accepts field names optionally prefixed with '+' (asc) or '-' (desc).
# Valid server-side fields: 'created_at', 'due_date', 'completed_at'.
# 'priority' is not a server-side field — it uses client-side reordering after
# fetching the freshest tasks, so we pre-sort by '-created_at' (newest first)
# to ensure the most-recently-created tasks land in the page window.
_SERVER_SIDE_SORT_MAP: dict[str, str] = {
    "due_date": "due_date",  # soonest due date first (server ascending)
    "priority": "-created_at",  # newest tasks fetched first; client reorders by urgency
    "latest": "-created_at",  # most recently created first
    "oldest": "+created_at",  # oldest created first
}


async def _retrieve_my_tasklist_from_workflow(  # noqa: PLR0913 # Baseline
    limit: Optional[int] = None,  # noqa: UP045 # Baseline
    offset: Optional[int] = None,  # noqa: UP045 # Baseline
    sort: Optional[str] = None,  # noqa: UP045 # Baseline
    max_results: Optional[int] = None,  # noqa: UP045 # Baseline
    urgency: Optional[str] = None,  # noqa: UP045 # Baseline
    due_before: Optional[datetime] = None,  # noqa: UP045 # Baseline
) -> List[Task]:  # noqa: UP006 # Baseline
    """
    Retrieve list of tasks from workflow task inbox for a user.

    Args:
        limit: Number of items to return (maps to limit query param)
        offset: Offset to start returning items from (maps to offset query param)
        sort: Logical sort key ('due_date', 'latest', 'oldest', 'priority').
              All keys are mapped to a server-side sort param via _SERVER_SIDE_SORT_MAP
              so the API returns the right page window.  'priority' maps to '-created_at'
              (newest first) so that client-side urgency reordering works on the freshest
              tasks.
        max_results: Backward compatibility alias for limit
        urgency: Urgency filter ('overdue', 'at_risk', 'all'), applied server-side
        due_before: Upper due date bound, applied server-side

    Returns:
        List[Task]: List of task objects
    """
    effective_limit = limit if limit is not None else max_results
    params = {
        "unassigned": "false",
        "completed": "false",
        "hide_authoring_tasks": "false",
        "count_only": "false",
    }
    if effective_limit is not None:
        params["limit"] = str(effective_limit)
    if offset is not None:
        params["offset"] = str(offset)
    # Only forward sort params that the server actually accepts.
    server_sort = _SERVER_SIDE_SORT_MAP.get(sort or "")
    if server_sort:
        params["sort"] = server_sort
    _apply_server_side_filters(params, urgency, due_before)

    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}",
            params=params,
        )

        # Schema: resources[]->Items->(metadata, entity)
        item_list = response.get("resources", [])
        tasks = []
        for task_data in item_list:
            task = await _create_task_from_data(task_data)
            tasks.append(task)
        return tasks

    except KeyError as e:
        error_msg = f"Missing required field in task response: {e!s}"
        LOGGER.error(error_msg)
        raise ServiceError(
            error_msg,
            service="workflow",
            tool="get_my_workflow_inbox_tasks",
            remediation_steps="Verify the workflow task API is returning complete data. Contact support if the issue persists.",
        ) from e
    except (ConnectionError, TimeoutError) as e:
        error_msg = f"Network error while retrieving tasks from workflow inbox: {e!s}"
        LOGGER.error(error_msg)
        raise ExternalAPIError(
            error_msg,
            service="workflow",
            tool="get_my_workflow_inbox_tasks",
            remediation_steps="Check network connectivity and verify the workflow service is accessible. Retry the operation after ensuring network stability.",
        ) from e
    except Exception as e:
        error_msg = f"Unexpected error retrieving tasks from workflow inbox: {type(e).__name__}: {e!s}"
        LOGGER.error(error_msg)
        raise ServiceError(
            error_msg,
            service="workflow",
            tool="get_my_workflow_inbox_tasks",
            remediation_steps="Verify your authentication credentials are valid and you have permission to access workflow tasks. Check the service logs for more details.",
        ) from e


def _build_task_url(task_id: str) -> str:
    """
    Build the URL to access a task instance in Workflow.

    Args:
        task_id: str: Task ID

    Returns:
        str: Complete URL to the task
    """
    return f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}/{task_id}"


get_workflow_tasks_from_my_inbox_description = """
    Use this tool when you need to retrieve tasks from workflow task inbox for the current user.

    This tool fetches tasks assigned to you or tasks you are candidates for in governance workflows.
    It supports cursor-based pagination (page_size, page_token), urgency filtering ('overdue', 'at_risk', 'all'),
    due date filtering (due_before, due_after), and sorting ('due_date', 'latest', 'oldest', 'priority').
    Every response includes a semantic summary outlining category counts and navigation state.

    Sorting options:
    - 'due_date' (default): soonest due date first; tasks without a due date appear last.
    - 'priority': urgency-based ordering (overdue > at-risk > claimed > unclaimed), done client-side.
    - 'latest': newest tasks first (by creation date).
    - 'oldest': oldest tasks first (by creation date).

    Use format='json' for raw task data or format='table' (default) for formatted output.
    If you find markdown text in the result show it to the user.
    ALWAYS render the result as table if called with format='table' parameter.

    Make sure to use a request json object for the parameters.
    Returns: The list of workflow tasks assigned to the current user, total count, pagination tokens, semantic summary, and optionally a formatted markdown table for display.
"""


async def _fetch_filtered_page(
    request: GetMyTasksRequest,
    offset: int,
    total_count: int,
) -> Tuple[List[Task], int, bool]:  # noqa: UP006 # Baseline
    """
    Collect up to request.page_size tasks, starting at the given backend offset.

    Urgency and due_before are filtered server-side. due_after has no server-side
    equivalent, so when it is set the backend is read window by window until the page
    is full, the backend is exhausted, or MAX_FILL_REQUESTS is reached.

    Args:
        request: The tool request.
        offset: Backend offset to start from.
        total_count: Server-filtered total count, or -1 if unknown.

    Returns:
        Tuple of (tasks for this page, backend offset after the last consumed item,
        whether the end of the backend list was reached).
    """
    max_requests = MAX_FILL_REQUESTS if request.due_after is not None else 1
    page_size = request.page_size

    tasks: List[Task] = []  # noqa: UP006 # Baseline
    cursor = offset
    exhausted = False

    for _ in range(max_requests):
        window = await _retrieve_my_tasklist_from_workflow(
            limit=page_size,
            offset=cursor,
            sort=request.sort,
            urgency=request.urgency,
            due_before=request.due_before,
        )
        cursor = _consume_window(window, tasks, cursor, page_size, request.due_after)

        exhausted = len(window) < page_size or 0 <= total_count <= cursor
        if exhausted or len(tasks) >= page_size:
            break

    return tasks, cursor, exhausted


def _consume_window(
    window: List[Task],  # noqa: UP006 # Baseline
    tasks: List[Task],  # noqa: UP006 # Baseline
    cursor: int,
    page_size: int,
    due_after: Optional[datetime],  # noqa: UP045 # Baseline
) -> int:
    """
    Append tasks from a backend window to `tasks` until the page is full.

    Args:
        window: Tasks returned by one backend request.
        tasks: Accumulated page (modified in place).
        cursor: Backend offset of the first task in the window.
        page_size: Target page size.
        due_after: Optional client-side lower due date bound.

    Returns:
        Backend offset right after the last consumed task.
    """
    for task in window:
        cursor += 1
        if due_after is None or filter_tasks_by_date_range([task], due_after=due_after):
            tasks.append(task)
            if len(tasks) == page_size:
                break
    return cursor


def _decode_page_offset(request: GetMyTasksRequest) -> int:
    """
    Decode request.page_token into a backend offset, syncing request.page_size from the token.

    Args:
        request: The tool request (page_size may be updated).

    Returns:
        Backend offset; 0 when no token is given or it cannot be decoded.
    """
    if not request.page_token:
        return 0
    try:
        cursor = PageCursor.from_token(request.page_token)
    except Exception as e:
        LOGGER.warning(
            f"Failed to decode page_token '{request.page_token}', defaulting offset to 0: {e}"
        )
        return 0
    if cursor.limit:
        request.page_size = cursor.limit
    return cursor.offset


def _build_page_tokens(
    page_size: int,
    offset: int,
    next_offset: int,
    total_count: int,
    exhausted: bool,
) -> Tuple[bool, Optional[str], Optional[str]]:  # noqa: UP006, UP045 # Baseline
    """
    Compute has_more and the next/previous page tokens.

    Args:
        page_size: Page size encoded into the tokens.
        offset: Backend offset where this page started.
        next_offset: Backend offset right after the last item consumed for this page.
        total_count: Server-filtered total count.
        exhausted: Whether the end of the backend list was reached.

    Returns:
        Tuple of (has_more, next_page_token, prev_page_token).
    """
    has_more = not exhausted and next_offset < total_count
    next_page_token = (
        PageCursor(limit=page_size, offset=next_offset).to_token() if has_more else None
    )
    prev_page_token = (
        PageCursor(limit=page_size, offset=max(0, offset - page_size)).to_token()
        if offset > 0
        else None
    )
    return has_more, next_page_token, prev_page_token


def _build_active_filters(request: GetMyTasksRequest) -> dict[str, Optional[str]]:  # noqa: UP045 # Baseline
    """Describe the active filters for the semantic summary."""
    return {
        "urgency": request.urgency,
        "sort": request.sort,
        "due_before": request.due_before.isoformat() if request.due_before else None,
        "due_after": request.due_after.isoformat() if request.due_after else None,
    }


async def _get_workflow_tasks_from_my_inbox(
    request: GetMyTasksRequest,
    ctx: Context,
) -> GetMyTasksResponse:
    """
    Get tasks from workflow task inbox for the current user.

    Args:
        request: GetMyTasksRequest object containing filter parameters

    Returns:
        GetMyTasksResponse object containing list of tasks, total count, pagination tokens, semantic summary, and optional formatted output
    """
    LOGGER.info(
        f"Calling get_my_workflow_inbox_tasks with "
        f"page_size: {request.page_size}, "
        f"urgency: {request.urgency}, "
        f"sort: {request.sort}, "
        f"format: {request.format}"
    )

    offset = _decode_page_offset(request)

    # Auto-detect clients that don't support rich text and switch to JSON format if needed
    if not supports_rich_text_format(ctx) and request.format == "table":
        LOGGER.info(
            "Client without rich text support detected: switching format from 'table' to 'json'"
        )
        request.format = "json"

    # Fetch total task count (urgency and due_before are applied server-side)
    total_count = await _get_total_task_count(
        urgency=request.urgency,
        due_before=request.due_before,
    )

    # Fetch a full page; due_after has no server-side equivalent and is applied client-side
    tasks, next_offset, exhausted = await _fetch_filtered_page(
        request, offset, total_count
    )

    # Fallback total_count if count_only failed or returned invalid value
    if total_count < 0:
        total_count = next_offset

    # In-memory sorting
    tasks = sort_tasks_by_sort_key(tasks, sort=request.sort)
    LOGGER.info(f"Processed {len(tasks)} tasks after filtering and sorting")

    has_more, next_page_token, prev_page_token = _build_page_tokens(
        request.page_size, offset, next_offset, total_count, exhausted
    )

    semantic_summary = build_semantic_summary(
        items=tasks,
        total_count=total_count,
        page_offset=offset,
        page_limit=request.page_size,
        item_categorizer=inbox_task_categorizer,
        active_filters=_build_active_filters(request),
    )

    # Generate output based on format
    formatted_output = None
    if request.format == "table":
        formatted_output = format_tasks_as_table(
            tasks=tasks,
            base_url=transform_base_url_to_ui_url(tool_helper_service.base_url),
        )
        LOGGER.info(f"Generated formatted table for {len(tasks)} tasks")

    return GetMyTasksResponse(
        tasks=tasks,
        total_count=total_count,
        formatted_output=formatted_output,
        next_page_token=next_page_token,
        prev_page_token=prev_page_token,
        has_more=has_more,
        semantic_summary=semantic_summary,
    )


@service_registry.tool(
    name="get_my_workflow_inbox_tasks",
    annotations={
        "readOnlyHint": True,
        "title": "Get Workflow Tasks Assigned to Me from My Inbox",
    },
    description=get_workflow_tasks_from_my_inbox_description,
    tags={
        "workflow",
        "flowable",
        "tasks",
        "governance",
        "glossary",
        "metadata_management_and_governance",
    },
    meta={"version": "2.0", "service": "task_inbox"},
)
@auto_context
async def get_my_workflow_inbox_tasks(  # noqa: PLR0913 # Baseline
    page_size: Annotated[
        int, Field(description="Number of tasks to return per page (1-50)")
    ] = 10,
    page_token: Annotated[
        Optional[str],  # noqa: UP045 # Baseline
        Field(description="Opaque pagination cursor token from previous response"),
    ] = None,
    urgency: Annotated[
        Optional[str],  # noqa: UP045 # Baseline
        Field(
            description="Filter tasks by urgency status ('overdue', 'at_risk', 'all')"
        ),
    ] = "all",
    sort: Annotated[
        Optional[str],  # noqa: UP045 # Baseline
        Field(description="Sort order ('due_date', 'latest', 'oldest', 'priority')"),
    ] = "due_date",
    due_before: Annotated[
        Optional[datetime],  # noqa: UP045 # Baseline
        Field(description="Filter tasks due before this ISO 8601 datetime"),
    ] = None,
    due_after: Annotated[
        Optional[datetime],  # noqa: UP045 # Baseline
        Field(description="Filter tasks due after this ISO 8601 datetime"),
    ] = None,
    max_results: Annotated[
        Optional[int],  # noqa: UP045 # Baseline
        Field(
            description="[Deprecated: use page_size] Maximum number of tasks to return"
        ),
    ] = None,
    format: Annotated[  # noqa: A002 # Baseline
        str,
        Field(
            description="Output format: 'table' for formatted markdown table, 'json' for raw task data"
        ),
    ] = "table",
    ctx: Context = None,
) -> GetMyTasksResponse:
    """Wrapper version of get_my_workflow_inbox_tasks."""
    request = GetMyTasksRequest(
        page_size=page_size if max_results is None else max_results,
        max_results=max_results,
        page_token=page_token,
        urgency=urgency,  # type: ignore[arg-type]
        sort=sort,  # type: ignore[arg-type]
        due_before=due_before,
        due_after=due_after,
        format=format,
    )

    return await _get_workflow_tasks_from_my_inbox(request, ctx)
