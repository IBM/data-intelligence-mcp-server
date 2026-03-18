# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Utility functions for formatting workflow tasks into human-readable output.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.services.workflow.models.get_workflow_tasks_from_my_inbox import Task
from app.services.constants import WORKFLOW_TASK_ENDPOINT
from app.shared.logging import LOGGER


def calculate_task_age(created_at: datetime) -> str:
    """
    Calculate human-readable task age with 'ago' suffix.
    
    Args:
        created_at: Task creation timestamp
        
    Returns:
        Human-readable age string (e.g., "2 days ago", "3 hours ago")
    """
    now = datetime.now(timezone.utc)
    delta = now - created_at
    
    if delta.days > 0:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        minutes = max(1, delta.seconds // 60)  # Show at least 1 minute
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"


def get_due_date_status(due_date: Optional[datetime]) -> str:
    """
    Determine due date status based on time until due.
    
    Args:
        due_date: Task due date timestamp
        
    Returns:
        Status string: "normal", "at_risk", "overdue", or "none"
    """
    if due_date is None:
        return "none"
    
    now = datetime.now(timezone.utc)
    time_until_due = due_date - now
    
    if time_until_due.total_seconds() < 0:
        return "overdue"
    elif time_until_due.total_seconds() < (48 * 3600):  # 48 hours in seconds
        return "at_risk"
    else:
        return "normal"


def format_due_date_with_status(due_date: Optional[datetime]) -> str:
    """
    Format due date with appropriate status indicator.
    
    Args:
        due_date: Task due date timestamp
        
    Returns:
        Formatted date string with icon:
        - "YYYY-MM-DD" for normal
        - "⚠️ YYYY-MM-DD" for at risk (within 48 hours)
        - "🛑 YYYY-MM-DD" for overdue
        - "No due date" if None
    """
    if due_date is None:
        return "No due date"
    
    status = get_due_date_status(due_date)
    date_str = due_date.strftime("%Y-%m-%d")
    
    if status == "overdue":
        return f"🛑 {date_str}"
    elif status == "at_risk":
        return f"⚠️ {date_str}"
    else:
        return date_str


def is_task_claimed(assignee: Optional[str]) -> str:
    """
    Check if task is claimed and return display string.
    
    Args:
        assignee: Task assignee (user ID or email)
        
    Returns:
        "Yes" if claimed, empty string if unclaimed
    """
    if assignee is not None and assignee.strip() != "":
        return "Yes"
    return ""


def build_task_url(base_url: str, task_id: str) -> str:
    """
    Build the URL to access a task instance in Workflow.
    
    Args:
        base_url: Base URL of the Data Intelligence service
        task_id: Task ID
        
    Returns:
        Complete URL to the task
    """
    LOGGER.debug(f"Building task URL: {base_url}{task_id}")
    return f"{base_url}{task_id}"


def sort_tasks_by_priority(tasks: List[Task]) -> List[Task]:
    """
    Sort tasks by priority: Overdue > At Risk > Claimed > Unclaimed.
    
    Within each category, tasks are sorted by:
    - Due date (soonest first, None values last)
    - Creation date (oldest first)
    
    Args:
        tasks: List of Task objects to sort
        
    Returns:
        Sorted list of Task objects with the following priority order:
        1. Overdue tasks (past due date)
        2. At Risk tasks (due within 48 hours)
        3. Claimed tasks with normal/no due dates
        4. Unclaimed tasks with normal/no due dates
    """
    def sort_key(task: Task) -> tuple:
        """
        Generate a sort key tuple for a task.
        
        Returns tuple: (due_status_priority, claimed_priority, due_date_sort, created_at)
        - due_status_priority: 0=overdue, 1=at_risk, 2=normal/none
        - claimed_priority: 0=claimed, 1=unclaimed
        - due_date_sort: datetime or max datetime for None values (sorts None to end)
        - created_at: datetime (oldest first)
        """
        # Determine due date status priority
        due_status = get_due_date_status(task.due_date)
        if due_status == "overdue":
            due_status_priority = 0
        elif due_status == "at_risk":
            due_status_priority = 1
        else:  # "normal" or "none"
            due_status_priority = 2
        
        # Determine claimed priority (0 = claimed, 1 = unclaimed)
        claimed_priority = 0 if (task.assignee and task.assignee.strip()) else 1
        
        # For due date sorting: None values should sort to the end
        # Use a far future date for None values
        due_date_sort = task.due_date if task.due_date else datetime.max.replace(tzinfo=timezone.utc)
        
        return (due_status_priority, claimed_priority, due_date_sort, task.created_at)
    
    return sorted(tasks, key=sort_key)


def format_tasks_as_table(tasks: List[Task], base_url: str) -> str:
    """
    Convert task list to markdown table with formatted columns.
    
    Args:
        tasks: List of Task objects
        base_url: Base URL for constructing task links
        
    Returns:
        Markdown table string with columns:
        - Task Title (hyperlinked)
        - Claimed (Yes or empty)
        - Assigned (time ago)
        - Due Date (with status icons)
        
    Note:
        If more than 20 tasks are returned, a link to the full task inbox
        is appended with a "list length exceeded" message.
    """
    if not tasks:
        return "No tasks found in your inbox."
    
    # Build table header
    table = "| Task Title | Claimed | Assigned | Due Date |\n"
    table += "|------------|---------|----------|----------|\n"
    
    # Build table rows
    for task in tasks:
        task_url = build_task_url(base_url, task.task_id)
        title_link = f"[{task.task_title}]({task_url})"
        claimed = is_task_claimed(task.assignee)
        assigned = calculate_task_age(task.created_at)
        due_date = format_due_date_with_status(task.due_date)
        
        table += f"| {title_link} | {claimed} | {assigned} | {due_date} |\n"
    
    # Add link to task inbox if more than 20 tasks
    if len(tasks) > 20:
        inbox_url = f"{base_url}{WORKFLOW_TASK_ENDPOINT}"
        table += f"| [View all tasks in your inbox]({inbox_url}) (list length exceeded) | | | |\n"
    
    return table


def format_artefacts_as_table(artefacts: List, base_url: str) -> str:
    """
    Convert artefact list (business terms or data classes) to markdown table with formatted columns.
    
    Args:
        artefacts: List of Artefact objects (BusinessTerm or DataClass)
        base_url: Base URL for constructing artifact links
        
    Returns:
        Markdown table string with columns:
        - Name (hyperlinked to artifact)
        - Description (truncated if too long)
        - State
        - Modified By
        - Created At
    """
    if not artefacts:
        return "No artefacts found."
    
    # Build table header
    table = "| Name | Description | State | Modified By | Created At |\n"
    table += "|------|-------------|-------|-------------|------------|\n"
    
    # Build table rows
    for artefact in artefacts:
        # Build name link if artifact_id exists
        if artefact.artifact_id:
            name_link = f"[{artefact.name}]({base_url}/artefacts/{artefact.artifact_id})"
        else:
            name_link = artefact.name
        
        # Truncate description if too long
        description = artefact.description or ""
        if len(description) > 100:
            description = description[:97] + "..."
        
        # Format created_at if available
        created_at = artefact.created_at or "N/A"
        
        table += f"| {name_link} | {description} | {artefact.state or 'N/A'} | {artefact.modified_by or 'N/A'} | {created_at} |\n"
    
    return table


def prompt_user_for_artifact_selection(artefacts: List, base_url: str) -> str:
    """
    Prompt user to select an artifact when multiple artifacts are returned.
    
    Args:
        artefacts: List of Artefact objects (BusinessTerm or DataClass)
        base_url: Base URL for constructing artifact links
        
    Returns:
        Formatted string prompting user to select an artifact
    """
    if not artefacts:
        return "No artefacts found."
    
    if len(artefacts) == 1:
        return f"Found 1 artifact: {artefacts[0].name}"
    
    # Build numbered list of artifacts
    output = f"Found {len(artefacts)} artifacts. Please select the artifact you want to work with:\n\n"
    
    for i, artefact in enumerate(artefacts, 1):
        # Build name link if artifact_id exists
        if artefact.artifact_id:
            name_link = f"[{artefact.name}]({base_url}/artefacts/{artefact.artifact_id})"
        else:
            name_link = artefact.name
        
        # Truncate description if too long
        description = artefact.description or ""
        if len(description) > 100:
            description = description[:97] + "..."
        
        # Format created_at if available
        created_at = artefact.created_at or "N/A"
        
        output += f"{i}. {name_link}\n"
        output += f"   Description: {description}\n"
        output += f"   State: {artefact.state or 'N/A'}\n"
        output += f"   Modified By: {artefact.modified_by or 'N/A'}\n"
        output += f"   Created At: {created_at}\n\n"
    
    output += "Please provide the number of the artifact you want to select."
    
    return output
