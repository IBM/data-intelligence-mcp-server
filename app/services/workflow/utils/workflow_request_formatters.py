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


def format_in_progress_workflows_table(workflows: List[WorkflowRequest], base_url: str, stalled_days: Optional[int]) -> str:
    """
    Format in-progress workflows as a markdown table.
    
    Args:
        workflows: List of in-progress WorkflowRequest objects
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection
        
    Returns:
        Markdown table string
        
    Note:
        If more than 20 in-progress requests are returned, a link to the full workflow list
        is appended with a "list length exceeded" message.
    """
    if not workflows:
        return "No in-progress requests found."
    
    table = f"## In-Progress Requests ({len(workflows)})\n\n"
    table += "| Workflow Request | Last Activity | Progress | Current Assignees |\n"
    table += "|------------------|---------------|----------|-------------------|\n"
    
    for workflow in workflows:
        workflow_url = build_workflow_url(base_url, workflow.workflow_id)
        title_link = f"[{workflow.name}]({workflow_url})"
        last_activity = format_last_activity(workflow.last_activity_at, workflow.days_since_activity, stalled_days)
        progress = format_progress(workflow.completed_tasks, workflow.total_tasks)
        assignees = format_assignees(workflow.current_assignees)
        
        table += f"| {title_link} | {last_activity} | {progress} | {assignees} |\n"
    
    # Add link to workflow list if more than 20 in-progress requests
    if len(workflows) > 20:
        workflows_url = f"{base_url}{WORKFLOW_BASE_ENDPOINT}"
        table += f"| [View all in-progress requests]({workflows_url}) (list length exceeded) | | | |\n"
    
    return table


def format_completed_workflows_table(workflows: List[WorkflowRequest], base_url: str) -> str:
    """
    Format completed workflows as a markdown table.
    
    Args:
        workflows: List of completed WorkflowRequest objects
        base_url: Base URL for constructing links
        
    Returns:
        Markdown table string
        
    Note:
        If more than 20 completed requests are returned, a link to the full workflow list
        is appended with a "list length exceeded" message.
    """
    if not workflows:
        return "No completed requests found."
    
    table = f"## Completed Requests ({len(workflows)})\n\n"
    table += "| Workflow Request | Completed | Duration | Total Tasks |\n"
    table += "|------------------|-----------|----------|-------------|\n"
    
    for workflow in workflows:
        workflow_url = build_workflow_url(base_url, workflow.workflow_id)
        title_link = f"[{workflow.name}]({workflow_url})"
        
        completed_str = calculate_task_age(workflow.completed_at) if workflow.completed_at else "Unknown"
        duration_str = f"{workflow.duration_days} days" if workflow.duration_days is not None else "Unknown"
        total_tasks_str = f"{workflow.total_tasks} tasks"
        
        table += f"| {title_link} | {completed_str} | {duration_str} | {total_tasks_str} |\n"
    
    # Add link to workflow list if more than 20 completed requests
    if len(workflows) > 20:
        workflows_url = f"{base_url}{WORKFLOW_BASE_ENDPOINT}"
        table += f"| [View all completed requests]({workflows_url}) (list length exceeded) | | | |\n"
    
    return table


def format_workflow_requests_as_tables(workflows: List[WorkflowRequest], base_url: str, stalled_days: Optional[int]) -> str:
    """
    Format workflow requests as markdown tables (separate tables for in-progress and completed).
    
    Args:
        workflows: List of WorkflowRequest objects
        base_url: Base URL for constructing links
        stalled_days: Threshold for stalled detection
        
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
        output.append(format_in_progress_workflows_table(in_progress, base_url, stalled_days))
    
    # Completed table
    if completed:
        if in_progress:
            output.append("\n")  # Add spacing between tables
        output.append(format_completed_workflows_table(completed, base_url))
    
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
