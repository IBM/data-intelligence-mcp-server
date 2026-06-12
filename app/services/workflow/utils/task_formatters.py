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
from app.core.settings import settings

# Constants
AT_RISK_THRESHOLD_HOURS = 48  # Tasks due within this many hours are considered "at risk"


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
    elif time_until_due.total_seconds() < (AT_RISK_THRESHOLD_HOURS * 3600):
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
    Get the assignee for display in the Claimed column.
    
    Args:
        assignee: Task assignee (user ID or email)
        
    Returns:
        Assignee string if claimed, empty string if unclaimed
    """
    if assignee is not None and assignee.strip() != "":
        return assignee
    return ""


def format_candidates_with_limit(candidates: Optional[List[str]]) -> str:
    """
    Format list of candidates with limit of 3 items and ellipsis for more.
    
    Args:
        candidates: List of candidate names (users or groups)
        
    Returns:
        Formatted string with:
        - First 3 candidates joined by commas
        - "..." appended if more than 3 candidates
        - "N/A" if list is empty or None
    """
    if not candidates or len(candidates) == 0:
        return "N/A"
    
    # Take first 3 candidates
    displayed_candidates = candidates[:3]
    result = ", ".join(displayed_candidates)
    
    # Add ellipsis if there are more candidates
    if len(candidates) > 3:
        result += "..."
    
    return result


def format_assignees(candidate_users: Optional[List[str]], candidate_groups: Optional[List[str]]) -> str:
    """
    Merge candidate users and groups into a single list, marking groups with '(g)'.
    
    Args:
        candidate_users: List of candidate user names
        candidate_groups: List of candidate group names
        
    Returns:
        Formatted string with:
        - Users and groups merged, groups suffixed with '(g)'
        - First 3 items joined by commas
        - "..." appended if more than 3 items total
        - "N/A" if both lists are empty or None
    """
    # Build merged list
    merged = []
    
    # Add users (without suffix)
    if candidate_users:
        for user in candidate_users:
            if user:  # Skip empty strings
                merged.append(user)
    
    # Add groups (with '(g)' suffix)
    if candidate_groups:
        for group in candidate_groups:
            if group:  # Skip empty strings
                merged.append(f"{group} (g)")
    
    # Handle empty case
    if not merged:
        return "N/A"
    
    # Apply 3-item limit with ellipsis
    displayed = merged[:3]
    result = ", ".join(displayed)
    
    if len(merged) > 3:
        result += "..."
    
    return result


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
        - Claimed at (date when claimed, or "-")
        - Claimed (assignee email/id, or empty if unclaimed)
        - Due Date (with status icons)
        - Assignees (merged candidate users and groups, groups marked with '(g)')
        
    Note:
        If more than 20 tasks are returned, a link to the full task inbox
        is appended with a "list length exceeded" message.
    """
    if not tasks:
        return "No tasks found in your inbox."
    
    # Build table header
    table = "| Task Title | Claimed at | Claimed | Due Date | Assignees |\n"
    table += "|------------|------------|---------|----------|-----------|\n"
    
    # Build table rows
    for task in tasks:
        task_url = build_task_url(base_url, task.task_id)
        title_link = f"[{task.task_title}]({task_url})"
        
        # Format claimed_at date or show "-"
        if task.claimed_at:
            claimed_at = task.claimed_at.strftime("%Y-%m-%d")
        else:
            claimed_at = "-"
        
        # Get assignee (empty if unclaimed)
        claimed = is_task_claimed(task.assignee)
        
        # Format due date
        due_date = format_due_date_with_status(task.due_date)
        
        # Merge candidate users and groups
        assignees = format_assignees(task.candidate_users, task.candidate_groups)
        
        table += f"| {title_link} | {claimed_at} | {claimed} | {due_date} | {assignees} |\n"
    
    # Add link to task inbox if more than 20 tasks
    if len(tasks) > 20:
        inbox_url = f"{base_url}{WORKFLOW_TASK_ENDPOINT}"
        table += f"| [View all tasks in your inbox]({inbox_url}) (list length exceeded) | | | | |\n"
    
    return table


def build_artifact_url(artifact_id: str, artifact_type: str, ui_base_url: str) -> str:
    """
    Build the proper URL for an artifact based on its type and environment.
    
    Args:
        artifact_id: The artifact ID
        artifact_type: Type of artifact ('data_class' or 'glossary_term')
        ui_base_url: Base URL for the UI
        
    Returns:
        Full URL to the artifact in the governance UI
        
    Examples:
        SaaS data class: https://dai.dev.cloud.ibm.com/governance/data-classes/{artifact_id}
        CPD data class: https://cpd.example.com/gov/data-classes/{artifact_id}
        SaaS business term: https://dai.dev.cloud.ibm.com/governance/terms/{artifact_id}
        CPD business term: https://cpd.example.com/gov/terms/{artifact_id}
    """
    # Determine the governance path prefix based on environment
    if settings.di_env_mode == "CPD":
        gov_prefix = "gov"
    else:
        gov_prefix = "governance"
    
    # Determine the artifact path based on type
    if artifact_type == "data_class":
        artifact_path = "data-classes"
    elif artifact_type == "glossary_term":
        artifact_path = "terms"
    else:
        # Fallback to old format if artifact type is unknown
        LOGGER.warning(f"Unknown artifact type '{artifact_type}', using fallback URL format")
        return f"{ui_base_url}/artifacts/{artifact_id}"
    
    return f"{ui_base_url}/{gov_prefix}/{artifact_path}/{artifact_id}"


def _format_artifact_name_link(artifact, ui_base_url: str) -> str:
    """
    Build a formatted name link for an artifact.
    
    Args:
        artifact: Artifact object (BusinessTerm or DataClass)
        ui_base_url: UI base URL for constructing artifact links
        
    Returns:
        Formatted name link (hyperlinked if artifact_id exists, plain text otherwise)
    """
    if artifact.artifact_id and hasattr(artifact, 'artifact_type') and artifact.artifact_type:
        return f"[{artifact.name}]({build_artifact_url(artifact.artifact_id, artifact.artifact_type, ui_base_url)})"
    elif artifact.artifact_id:
        # Fallback to old format if artifact_type is not available
        return f"[{artifact.name}]({ui_base_url}/artifacts/{artifact.artifact_id})"
    else:
        return artifact.name


def _truncate_description(description: str, max_length: int = 100) -> str:
    """
    Truncate description if it exceeds max_length.
    
    Args:
        description: Description text to truncate
        max_length: Maximum length before truncation (default: 100)
        
    Returns:
        Truncated description with "..." suffix if needed, or original if within limit
    """
    description = description or ""
    if len(description) > max_length:
        return description[:max_length - 3] + "..."
    return description


def format_artifacts_as_table(artifacts: List, base_url: str) -> str:
    """
    Convert artifact list (business terms or data classes) to markdown table with formatted columns.
    
    Args:
        artifacts: List of Artifact objects (BusinessTerm or DataClass)
        base_url: Base URL for constructing artifact links (API base URL, will be converted to UI URL)
        
    Returns:
        Markdown table string with columns:
        - Name (hyperlinked to artifact)
        - Description (truncated if too long)
        - State
        - Modified By
        - Created At
    """
    if not artifacts:
        return "No artifacts found."
    
    # Get UI base URL from settings
    ui_base_url = str(settings.ui_url) if settings.ui_url else base_url
    
    # Build table header
    table = "| Name | Description | State | Modified By | Created At |\n"
    table += "|------|-------------|-------|-------------|------------|\n"
    
    # Build table rows
    for artifact in artifacts:
        name_link = _format_artifact_name_link(artifact, ui_base_url)
        description = _truncate_description(artifact.description)
        created_at = artifact.created_at or "N/A"
        
        table += f"| {name_link} | {description} | {artifact.state or 'N/A'} | {artifact.modified_by or 'N/A'} | {created_at} |\n"
    
    return table


def prompt_user_for_artifact_selection(artifacts: List, base_url: str) -> str:
    """
    Prompt user to select an artifact when multiple artifacts are returned.
    
    Args:
        artifacts: List of Artifact objects (BusinessTerm or DataClass)
        base_url: Base URL for constructing artifact links (API base URL, will be converted to UI URL)
        
    Returns:
        Formatted string prompting user to select an artifact
    """
    if not artifacts:
        return "No artifacts found."
    
    if len(artifacts) == 1:
        return f"Found 1 artifact: {artifacts[0].name}"
    
    # Get UI base URL from settings
    ui_base_url = str(settings.ui_url) if settings.ui_url else base_url
    
    # Build numbered list of artifacts
    output = f"Found {len(artifacts)} artifacts. Please select the artifact you want to work with:\n\n"
    
    for i, artifact in enumerate(artifacts, 1):
        name_link = _format_artifact_name_link(artifact, ui_base_url)
        description = _truncate_description(artifact.description)
        created_at = artifact.created_at or "N/A"
        
        output += f"{i}. {name_link}\n"
        output += f"   Description: {description}\n"
        output += f"   State: {artifact.state or 'N/A'}\n"
        output += f"   Modified By: {artifact.modified_by or 'N/A'}\n"
        output += f"   Created At: {created_at}\n\n"
    
    output += "Please provide the number of the artifact you want to select."
    
    return output
