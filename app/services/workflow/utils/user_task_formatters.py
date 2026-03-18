# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Utility functions for formatting workflow user tasks into human-readable output.
"""

from datetime import datetime, timezone
from typing import List, Optional

from app.services.workflow.models.list_user_tasks_approval_data_for_artifact import UserTask
from app.services.constants import WORKFLOW_TASK_ENDPOINT
from app.services.workflow.utils.task_formatters import calculate_task_age
from app.shared.logging import LOGGER


def get_user_task_state_display(state: Optional[str]) -> str:
    """
    Convert user task state code to human-readable display string.
    
    Args:
        state: User task state code (0 - created, 1 - assigned, 2 - completed)
        
    Returns:
        Human-readable state string
    """
    if state is None:
        return "Unknown"
    
    state_map = {
        "0": "Created",
        "1": "Assigned",
        "2": "Completed"
    }
    
    return state_map.get(str(state), "Unknown")


def is_user_task_completed(state: Optional[str]) -> bool:
    """
    Check if user task is completed.
    
    Args:
        state: User task state code
        
    Returns:
        True if completed, False otherwise
    """
    if state is None:
        return False
    return str(state) == "2"


def is_user_task_assigned(state: Optional[str]) -> bool:
    """
    Check if user task is assigned.
    
    Args:
        state: User task state code
        
    Returns:
        True if assigned, False otherwise
    """
    if state is None:
        return False
    return str(state) == "1"


def format_user_task_state(state: Optional[str]) -> str:
    """
    Format user task state with appropriate icon.
    
    Args:
        state: User task state code
        
    Returns:
        Formatted state string with icon:
        - "✅ Completed" for completed
        - "👤 Assigned" for assigned
        - "📝 Created" for created
        - "❓ Unknown" for unknown
    """
    if is_user_task_completed(state):
        return "✅ Completed"
    elif is_user_task_assigned(state):
        return "👤 Assigned"
    elif state == "0":
        return "📝 Created"
    else:
        return "❓ Unknown"


def format_completed_at(completed_at: Optional[str]) -> str:
    """
    Format completed_at timestamp to human-readable string.
    
    Args:
        completed_at: Completed timestamp string
        
    Returns:
        Formatted date string or "Not completed" if None
    """
    if completed_at is None:
        return "Not completed"
    
    try:
        # Handle both ISO format and other formats
        if completed_at.endswith("Z"):
            completed_at = completed_at[:-1] + "+00:00"
        dt = datetime.fromisoformat(completed_at)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return completed_at


def format_candidate_users(candidate_users: Optional[List[str]]) -> str:
    """
    Format list of candidate users into a readable string.
    
    Args:
        candidate_users: List of user names
        
    Returns:
        Comma-separated string of user names or "No candidates" if empty
    """
    if not candidate_users or len(candidate_users) == 0:
        return "No candidates"
    
    return ", ".join(candidate_users)


def build_user_task_url(base_url: str, task_id: str) -> str:
    """
    Build the URL to access a user task instance in Workflow.
    
    Args:
        base_url: Base URL of the Data Intelligence service
        task_id: Task ID
        
    Returns:
        Complete URL to the task
    """
    # Remove trailing slash from base_url if present to avoid double slashes
    base_url = base_url.rstrip('/')
    task_link = f"{base_url}{task_id}"
    LOGGER.debug(f"Building user task URL: {task_link}")
    return task_link


def sort_user_tasks_by_state(user_tasks: List[UserTask]) -> List[UserTask]:
    """
    Sort user tasks by state: Completed > Assigned > Created.
    
    Within each category, tasks are sorted by:
    - Name (alphabetically)
    
    Args:
        user_tasks: List of UserTask objects to sort
        
    Returns:
        Sorted list of UserTask objects with the following priority order:
        1. Completed tasks
        2. Assigned tasks
        3. Created tasks
    """
    def sort_key(user_task: UserTask) -> tuple:
        """
        Generate a sort key tuple for a user task.
        
        Returns tuple: (state_priority, name)
        - state_priority: 0=completed, 1=assigned, 2=created
        - name: task name (alphabetically)
        """
        # Determine state priority
        if is_user_task_completed(user_task.state):
            state_priority = 0
        elif is_user_task_assigned(user_task.state):
            state_priority = 1
        else:  # created or unknown
            state_priority = 2
        
        # Use name for secondary sort
        name = user_task.name or ""
        
        return (state_priority, name)
    
    return sorted(user_tasks, key=sort_key)


def format_user_tasks_as_table(user_tasks: List[UserTask], base_url: str) -> str:
    """
    Convert user task list to markdown table with formatted columns.
    
    Args:
        user_tasks: List of UserTask objects
        base_url: Base URL for constructing task links
        
    Returns:
        Markdown table string with columns:
        - Task Name (hyperlinked)
        - State (with icon)
        - Assignee
        - Completed At
        - Candidate Users
    """
    if not user_tasks:
        return "No user tasks found."
    
    # Build table header
    table = "| Task Name | State | Assignee | Completed At | Candidate Users |\n"
    table += "|-----------|-------|----------|--------------|-----------------|\n"
    
    # Build table rows
    for user_task in user_tasks:
        task_url = build_user_task_url(base_url, user_task.name)
        name_link = f"[{user_task.name}]({task_url})"
        state = format_user_task_state(user_task.state)
        assignee = user_task.assignee or "Unassigned"
        completed_at = format_completed_at(user_task.completed_at)
        candidates = format_candidate_users(user_task.candidate_users)
        
        table += f"| {name_link} | {state} | {assignee} | {completed_at} | {candidates} |\n"
    
    return table


def format_user_tasks_as_list(user_tasks: List[UserTask], base_url: str) -> str:
    """
    Convert user task list to formatted list with details.
    
    Args:
        user_tasks: List of UserTask objects
        base_url: Base URL for constructing task links
        
    Returns:
        Formatted string with task details
    """
    if not user_tasks:
        return "No user tasks found."
    
    output = []
    for user_task in user_tasks:
        task_url = build_user_task_url(base_url, user_task.name)
        state = format_user_task_state(user_task.state)
        assignee = user_task.assignee or "Unassigned"
        completed_at = format_completed_at(user_task.completed_at)
        candidates = format_candidate_users(user_task.candidate_users)
        
        output.append(f"**{user_task.name}**")
        output.append(f"  - State: {state}")
        output.append(f"  - Assignee: {assignee}")
        output.append(f"  - Completed At: {completed_at}")
        output.append(f"  - Candidate Users: {candidates}")
        
        if user_task.task_title:
            output.append(f"  - Title: {user_task.task_title}")
        
        if user_task.task_instruction:
            output.append(f"  - Instruction: {user_task.task_instruction}")
        
        output.append(f"  - [View Task]({task_url})")
        output.append("")
    
    return "\n".join(output)
