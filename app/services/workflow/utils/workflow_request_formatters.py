# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Utility functions for formatting workflow requests into human-readable output.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict

from app.services.workflow.models.get_my_workflows import WorkflowRequest
from app.services.workflow.utils.task_formatters import calculate_task_age
from app.services.constants import WORKFLOW_BASE_ENDPOINT
from app.shared.logging import LOGGER


def get_activity_status(days_since_activity: Optional[int], stalled_days: Optional[int]) -> str:
    """
    Determine activity status based on days since last activity.
    
    Args:
        days_since_activity: Days since last activity
        stalled_days: Threshold for stalled status
        
    Returns:
        Status string: "normal", "at_risk", or "stalled"
    """
    if days_since_activity is None or stalled_days is None:
        return "normal"
    
    if days_since_activity >= stalled_days:
        return "stalled"
    elif days_since_activity >= (stalled_days // 2):  # At risk at 50% of stalled threshold
        return "at_risk"
    else:
        return "normal"


def format_last_activity(last_activity_at: Optional[datetime], days_since_activity: Optional[int], stalled_days: Optional[int]) -> str:
    """
    Format last activity timestamp with status indicator.
    
    Args:
        last_activity_at: Last activity timestamp
        days_since_activity: Days since last activity
        stalled_days: Threshold for stalled detection
        
    Returns:
        Formatted string with icon (e.g., "🛑 14 days ago", "⚠️ 7 days ago", "2 days ago")
    """
    if last_activity_at is None:
        return "No activity"
    
    age_str = calculate_task_age(last_activity_at)
    status = get_activity_status(days_since_activity, stalled_days)
    
    if status == "stalled":
        return f"🛑 {age_str}"
    elif status == "at_risk":
        return f"⚠️ {age_str}"
    else:
        return age_str


def format_progress(completed: int, total: int) -> str:
    """
    Format task progress as a ratio.
    
    Args:
        completed: Number of completed tasks
        total: Total number of tasks
        
    Returns:
        Formatted string (e.g., "2/3 tasks")
    """
    if total == 0:
        return "No tasks"
    return f"{completed}/{total} tasks"


def format_assignees(assignees: List[str]) -> str:
    """
    Format list of assignees.
    
    Args:
        assignees: List of assignee names/emails
        
    Returns:
        Comma-separated string or "-" if empty
    """
    if not assignees:
        return "-"
    return ", ".join(assignees)


def _format_task_state(state: str) -> str:
    """
    Format task state as human-readable string.
    
    Args:
        state: Task state code (0=created, 1=assigned, 2=completed)
        
    Returns:
        Formatted state string
    """
    state_map = {
        "0": "Created",
        "1": "In Progress",
        "2": "Completed"
    }
    return state_map.get(state, "Unknown")


def build_workflow_url(base_url: str, workflow_id: str) -> str:
    """
    Build URL to access a workflow.
    
    Args:
        base_url: Base URL of the service
        workflow_id: Workflow ID
        
    Returns:
        Complete URL to the workflow
    """
    return f"{base_url}{WORKFLOW_BASE_ENDPOINT}/{workflow_id}"


def _format_task_row(task) -> str:
    """
    Format a single task row for extended tables.
    
    Args:
        task: Task object with task_id, task_title, state, assignee, days_in_current_state
        
    Returns:
        Formatted table row string
    """
    task_state_str = _format_task_state(task.state)
    task_assignee = task.assignee or "-"
    return f"| | | | | | | | {task.task_id} | {task.task_title} | {task_state_str} | {task_assignee} | {task.days_in_current_state} |\n"


def _format_in_progress_compact_row(workflow: WorkflowRequest, base_url: str, stalled_days: Optional[int] = None) -> str:
    """
    Format a single in-progress workflow row for compact table.
    
    Args:
        workflow: WorkflowRequest object
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection (optional, defaults to None)
        
    Returns:
        Formatted table row string
    """
    workflow_url = build_workflow_url(base_url, workflow.workflow_id)
    title_link = f"[{workflow.name}]({workflow_url})"
    created_by = workflow.created_by or "-"
    last_activity = format_last_activity(workflow.last_activity_at, workflow.days_since_activity, stalled_days)
    progress = format_progress(workflow.completed_tasks, workflow.total_tasks)
    assignees = format_assignees(workflow.current_assignees)
    
    return f"| {title_link} | {created_by} | {last_activity} | {progress} | {assignees} |\n"


def _format_in_progress_extended_row(workflow: WorkflowRequest, base_url: str, stalled_days: Optional[int] = None) -> str:
    """
    Format a single in-progress workflow row for extended table.
    
    Args:
        workflow: WorkflowRequest object
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection (optional, defaults to None)
        
    Returns:
        Formatted table row string
    """
    workflow_url = build_workflow_url(base_url, workflow.workflow_id)
    title_link = f"[{workflow.name}]({workflow_url})"
    created_by = workflow.created_by or "-"
    last_activity = format_last_activity(workflow.last_activity_at, workflow.days_since_activity, stalled_days)
    progress = format_progress(workflow.completed_tasks, workflow.total_tasks)
    assignees = format_assignees(workflow.current_assignees)
    
    return f"| {workflow.workflow_id} | {title_link} | {workflow.state} | {created_by} | {last_activity} | {progress} | {assignees} | | | | | |\n"


def _add_list_exceeded_row(table: str, base_url: str, link_text: str, column_count: int) -> str:
    """
    Add a row indicating the list length was exceeded.
    
    Args:
        table: Existing table string
        base_url: Base URL for constructing links
        link_text: Text to display in the link
        column_count: Number of columns in the table (for proper spacing)
        
    Returns:
        Table string with the additional row
    """
    workflows_url = f"{base_url}{WORKFLOW_BASE_ENDPOINT}"
    empty_cells = " | " * (column_count - 1)
    return table + f"| [{link_text}]({workflows_url}) (list length exceeded) |{empty_cells}\n"


def _get_in_progress_table_headers(include_tasks: bool) -> str:
    """
    Get the table headers for in-progress workflows.
    
    Args:
        include_tasks: Whether to include task columns
        
    Returns:
        Header and separator rows
    """
    if include_tasks:
        headers = "| Workflow ID | Name | State | Created By | Last Activity | Progress | Current Assignees | Task ID | Task Title | Task State | Assignee | Days in State |"
        separator = "|-------------|------|-------|------------|---------------|----------|-------------------|---------|------------|------------|----------|---------------|"
    else:
        headers = "| Workflow Request | Created By | Last Activity | Progress | Current Assignees |"
        separator = "|------------------|------------|---------------|----------|-------------------|"
    
    return headers + "\n" + separator + "\n"


def _get_completed_table_headers(include_tasks: bool) -> str:
    """
    Get the table headers for completed workflows.
    
    Args:
        include_tasks: Whether to include task columns
        
    Returns:
        Header and separator rows
    """
    if include_tasks:
        headers = "| Workflow ID | Name | State | Created By | Completed At | Duration | Total Tasks | Task ID | Task Title | Task State | Assignee | Days in State |"
        separator = "|-------------|------|-------|------------|-------------|----------|-------------|---------|------------|------------|----------|---------------|"
    else:
        headers = "| Workflow Request | Created By | Completed | Duration | Total Tasks |"
        separator = "|------------------|------------|-----------|----------|-------------|"
    
    return headers + "\n" + separator + "\n"


def _format_workflow_row(workflow: WorkflowRequest, row_formatter, base_url: str, stalled_days: Optional[int]) -> str:
    """
    Format a single workflow row with appropriate parameters.
    
    Args:
        workflow: WorkflowRequest object
        row_formatter: Function to format the row
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection (optional)
        
    Returns:
        Formatted table row string
    """
    if stalled_days is not None:
        return row_formatter(workflow, base_url, stalled_days)
    else:
        return row_formatter(workflow, base_url)


def _format_workflow_with_tasks(workflow: WorkflowRequest, row_formatter, base_url: str, stalled_days: Optional[int], include_tasks: bool) -> str:
    """
    Format a workflow row with optional task rows.
    
    Args:
        workflow: WorkflowRequest object
        row_formatter: Function to format the workflow row
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection (optional)
        include_tasks: Whether to include task information
        
    Returns:
        Formatted workflow row and optional task rows
    """
    rows = _format_workflow_row(workflow, row_formatter, base_url, stalled_days)
    
    if include_tasks and workflow.tasks:
        task_rows = [_format_task_row(task) for task in workflow.tasks]
        rows += "".join(task_rows)
    
    return rows


def _add_exceeded_link_if_needed(table: str, workflows: List[WorkflowRequest], title: str, base_url: str, include_tasks: bool) -> str:
    """
    Add "list length exceeded" link if workflow count exceeds threshold.
    
    Args:
        table: Current table string
        workflows: List of workflows
        title: Table title
        base_url: Base URL for constructing links
        include_tasks: Whether table includes task columns
        
    Returns:
        Table string with optional exceeded link
    """
    if len(workflows) <= 20:
        return table
    
    column_count = 11 if include_tasks else 5
    workflow_type = title.lower().replace("## ", "").split(" ")[0]
    link_text = f"View all {workflow_type} requests"
    return _add_list_exceeded_row(table, base_url, link_text, column_count)


def _build_workflow_table(
    workflows: List[WorkflowRequest],
    title: str,
    row_formatter,
    base_url: str,
    stalled_days: Optional[int] = None,
    include_tasks: bool = False,
    header_getter = None,
    empty_message: str = None
) -> str:
    """
    Build a workflow table with given formatter and header getter.
    
    Args:
        workflows: List of WorkflowRequest objects
        title: Table title
        row_formatter: Function to format individual rows
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection (optional)
        include_tasks: Whether to include task information
        header_getter: Function to get table headers
        empty_message: Custom message for empty list (optional)
        
    Returns:
        Complete markdown table string
    """
    if not workflows:
        return empty_message if empty_message else title.replace("## ", "").replace(" Requests", ": No requests found.")
    
    # Build table header
    table = f"{title} ({len(workflows)})\n\n"
    table += header_getter(include_tasks)
    
    # Add workflow rows
    for workflow in workflows:
        table += _format_workflow_with_tasks(workflow, row_formatter, base_url, stalled_days, include_tasks)
    
    # Add exceeded link if needed
    return _add_exceeded_link_if_needed(table, workflows, title, base_url, include_tasks)


def format_in_progress_workflows_table(workflows: List[WorkflowRequest], base_url: str, stalled_days: Optional[int], include_tasks: bool = False) -> str:
    """
    Format in-progress workflows as a markdown table.
    
    Args:
        workflows: List of in-progress WorkflowRequest objects
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection
        include_tasks: Whether to include detailed task information
        
    Returns:
        Markdown table string
        
    Note:
        If more than 20 in-progress requests are returned, a link to the full workflow list
        is appended with a "list length exceeded" message.
    """
    row_formatter = _format_in_progress_extended_row if include_tasks else _format_in_progress_compact_row
    return _build_workflow_table(
        workflows,
        "## In-Progress Requests",
        row_formatter,
        base_url,
        stalled_days,
        include_tasks,
        _get_in_progress_table_headers,
        "No in-progress requests found."
    )


def _format_completed_compact_row(workflow: WorkflowRequest, base_url: str) -> str:
    """
    Format a single completed workflow row for compact table.
    
    Args:
        workflow: WorkflowRequest object
        base_url: Base URL for constructing links
        
    Returns:
        Formatted table row string
    """
    workflow_url = build_workflow_url(base_url, workflow.workflow_id)
    title_link = f"[{workflow.name}]({workflow_url})"
    created_by = workflow.created_by or "-"
    completed_str = calculate_task_age(workflow.completed_at) if workflow.completed_at else "Unknown"
    duration_str = f"{workflow.duration_days} days" if workflow.duration_days is not None else "Unknown"
    total_tasks_str = f"{workflow.total_tasks} tasks"
    
    return f"| {title_link} | {created_by} | {completed_str} | {duration_str} | {total_tasks_str} |\n"


def _format_completed_extended_row(workflow: WorkflowRequest, base_url: str) -> str:
    """
    Format a single completed workflow row for extended table.
    
    Args:
        workflow: WorkflowRequest object
        base_url: Base URL for constructing links
        
    Returns:
        Formatted table row string
    """
    workflow_url = build_workflow_url(base_url, workflow.workflow_id)
    title_link = f"[{workflow.name}]({workflow_url})"
    created_by = workflow.created_by or "-"
    completed_str = calculate_task_age(workflow.completed_at) if workflow.completed_at else "Unknown"
    duration_str = f"{workflow.duration_days} days" if workflow.duration_days is not None else "Unknown"
    total_tasks_str = f"{workflow.total_tasks} tasks"
    
    return f"| {workflow.workflow_id} | {title_link} | {workflow.state} | {created_by} | {completed_str} | {duration_str} | {total_tasks_str} | | | | | |\n"


def format_completed_workflows_table(workflows: List[WorkflowRequest], base_url: str, include_tasks: bool = False) -> str:
    """
    Format completed workflows as a markdown table.
    
    Args:
        workflows: List of completed WorkflowRequest objects
        base_url: Base URL for constructing links
        include_tasks: Whether to include detailed task information
        
    Returns:
        Markdown table string
        
    Note:
        If more than 20 completed requests are returned, a link to the full workflow list
        is appended with a "list length exceeded" message.
    """
    row_formatter = _format_completed_extended_row if include_tasks else _format_completed_compact_row
    return _build_workflow_table(
        workflows,
        "## Completed Requests",
        row_formatter,
        base_url,
        include_tasks=include_tasks,
        header_getter=_get_completed_table_headers,
        empty_message="No completed requests found."
    )


def format_workflow_requests_as_tables(workflows: List[WorkflowRequest], base_url: str, stalled_days: Optional[int], include_tasks: bool = False) -> str:
    """
    Format workflow requests as markdown tables (separate tables for in-progress and completed).
    
    Args:
        workflows: List of WorkflowRequest objects
        Canbase_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection
        include_tasks: Whether to include detailed task information
        
    Returns:
        Formatted markdown string with tables and insights
    """
    if not workflows:
        return "No workflow requests found."
    
    # Separate workflows by state
    in_progress = [w for w in workflows if w.state != "completed"]
    completed = [w for w in workflows if w.state == "completed"]
    
    # Build output
    output = []
    
    # In-progress table
    if in_progress:
        output.append(format_in_progress_workflows_table(in_progress, base_url, stalled_days, include_tasks))
    
    # Completed table
    if completed:
        if in_progress:
            output.append("\n")  # Add spacing between tables
        output.append(format_completed_workflows_table(completed, base_url, include_tasks))
    
    # Add insights
    insights = generate_workflow_insights(workflows, stalled_days)
    if insights:
        output.append("\n")
        output.append(insights)
    
    return "\n".join(output)


def generate_workflow_insights(workflows: List[WorkflowRequest], stalled_days: Optional[int]) -> str:
    """
    Generate summary insights about workflow requests.
    
    Args:
        workflows: List of WorkflowRequest objects
        stalled_days: Threshold for stalled detection
        
    Returns:
        Formatted insights string
    """
    if not workflows:
        return ""
    
    # Calculate statistics
    active = [w for w in workflows if w.state != "completed"]
    completed = [w for w in workflows if w.state == "completed"]
    stalled = [w for w in active if w.is_stalled]
    at_risk = [w for w in active if not w.is_stalled and get_activity_status(w.days_since_activity, stalled_days) == "at_risk"]
    
    insights = ["## Key Insights\n"]
    
    # Summary counts
    insights.append(f"- **{len(active)} active requests** ({len(stalled)} stalled, {len(at_risk)} at risk)")
    insights.append(f"- **{len(completed)} completed requests**")
    
    # Stalled requests detail
    if stalled:
        insights.append(f"\n### Stalled Requests (No activity in {stalled_days}+ days)")
        for i, workflow in enumerate(sorted(stalled, key=lambda w: w.days_since_activity or 0, reverse=True)[:5], 1):
            insights.append(f"{i}. {workflow.name} - {workflow.days_since_activity} days idle")
    
    # Assignee summary
    assignee_counts: Dict[str, int] = {}
    for workflow in active:
        for assignee in workflow.current_assignees:
            assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
    
    if assignee_counts:
        insights.append("\n### Current Assignees")
        for assignee, count in sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            insights.append(f"- {assignee}: {count} active task{'s' if count != 1 else ''}")
    
    return "\n".join(insights)


def calculate_workflow_statistics(workflows: List[WorkflowRequest], stalled_days: Optional[int]) -> Dict[str, int]:
    """
    Calculate summary statistics for workflows.
    
    Args:
        workflows: List of WorkflowRequest objects
        stalled_days: Threshold for stalled detection
        
    Returns:
        Dictionary with counts
    """
    active_count = sum(1 for w in workflows if w.state != "completed")
    completed_count = sum(1 for w in workflows if w.state == "completed")
    stalled_count = sum(1 for w in workflows if w.is_stalled)
    at_risk_count = sum(1 for w in workflows if not w.is_stalled and get_activity_status(w.days_since_activity, stalled_days) == "at_risk")
    
    return {
        "active_count": active_count,
        "completed_count": completed_count,
        "stalled_count": stalled_count,
        "at_risk_count": at_risk_count
    }
