# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Utility functions for formatting workflow tasks into human-readable output.
"""

from datetime import datetime, timezone, UTC  # noqa: F401, I001 # Baseline
from typing import List, Optional, Tuple  # noqa: UP035 # Baseline

from app.services.workflow.models.get_workflow_tasks_from_my_inbox import Task
from app.services.constants import WORKFLOW_TASK_ENDPOINT
from app.shared.logging import LOGGER
from app.core.settings import settings

# Constants
AT_RISK_THRESHOLD_HOURS = (
    48  # Tasks due within this many hours are considered "at risk"
)


def calculate_task_age(created_at: datetime) -> str:
    """
    Calculate human-readable task age with 'ago' suffix.

    Args:
        created_at: Task creation timestamp

    Returns:
        Human-readable age string (e.g., "2 days ago", "3 hours ago")
    """
    now = datetime.now(UTC)
    delta = now - created_at

    if delta.days > 0:
        return f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
    if delta.seconds >= 3600:  # noqa: PLR2004 # Baseline
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    minutes = max(1, delta.seconds // 60)  # Show at least 1 minute
    return f"{minutes} minute{'s' if minutes != 1 else ''} ago"


def get_due_date_status(due_date: Optional[datetime]) -> str:  # noqa: UP045 # Baseline
    """
    Determine due date status based on time until due.

    Args:
        due_date: Task due date timestamp

    Returns:
        Status string: "normal", "at_risk", "overdue", or "none"
    """
    if due_date is None:
        return "none"

    now = datetime.now(UTC)
    time_until_due = due_date - now

    if time_until_due.total_seconds() < 0:
        return "overdue"
    if time_until_due.total_seconds() < (AT_RISK_THRESHOLD_HOURS * 3600):
        return "at_risk"
    return "normal"


def format_due_date_with_status(due_date: Optional[datetime]) -> str:  # noqa: UP045 # Baseline
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
    if status == "at_risk":
        return f"⚠️ {date_str}"
    return date_str


def is_task_claimed(assignee: Optional[str]) -> str:  # noqa: UP045 # Baseline
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


def format_candidates_with_limit(candidates: Optional[List[str]]) -> str:  # noqa: UP006, UP045 # Baseline
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
    if len(candidates) > 3:  # noqa: PLR2004 # Baseline
        result += "..."

    return result


def format_assignees(
    candidate_users: Optional[List[str]],  # noqa: UP006, UP045 # Baseline
    candidate_groups: Optional[List[str]],  # noqa: UP006, UP045 # Baseline
) -> str:
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

    if len(merged) > 3:  # noqa: PLR2004 # Baseline
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


def filter_tasks_by_urgency(
    tasks: List[Task],  # noqa: UP006 # Baseline
    urgency: Optional[str] = "all",  # noqa: UP006, UP045 # Baseline
) -> List[Task]:  # noqa: UP006 # Baseline
    """
    Filter tasks by urgency status ('overdue', 'at_risk', 'all' or None).

    Args:
        tasks: List of Task objects.
        urgency: Urgency filter string ('overdue', 'at_risk', 'all', or None).

    Returns:
        Filtered list of Task objects.
    """
    if not urgency or urgency == "all":
        return tasks

    return [t for t in tasks if get_due_date_status(t.due_date) == urgency]


def _align_tz_with_bound(bound: datetime, value: datetime) -> Tuple[datetime, datetime]:  # noqa: UP006 # Baseline
    """
    Align tz-awareness between a filter bound and a task due date.

    Naive values are interpreted as UTC so the pair becomes comparable
    without shifting wall-clock values.

    Args:
        bound: Range bound (due_before or due_after).
        value: Task due date.

    Returns:
        The (possibly re-based) (bound, value) pair.
    """
    if bound.tzinfo is not None and value.tzinfo is None:
        return bound, value.replace(tzinfo=UTC)
    if bound.tzinfo is None and value.tzinfo is not None:
        return bound.replace(tzinfo=UTC), value
    return bound, value


def _task_is_due_in_range(
    task_due: datetime,
    due_before: Optional[datetime],  # noqa: UP045 # Baseline
    due_after: Optional[datetime],  # noqa: UP045 # Baseline
) -> bool:
    """
    Check a single due date against the inclusive range bounds.

    Args:
        task_due: Task due date (non-None).
        due_before: Optional upper bound.
        due_after: Optional lower bound.

    Returns:
        True when the due date lies within the bounds.
    """
    if due_before is not None:
        due_before, task_due = _align_tz_with_bound(due_before, task_due)
        if task_due > due_before:
            return False
    if due_after is not None:
        due_after, task_due = _align_tz_with_bound(due_after, task_due)
        if task_due < due_after:
            return False
    return True


def filter_tasks_by_date_range(
    tasks: List[Task],  # noqa: UP006 # Baseline
    due_before: Optional[datetime] = None,  # noqa: UP045 # Baseline
    due_after: Optional[datetime] = None,  # noqa: UP045 # Baseline
) -> List[Task]:  # noqa: UP006 # Baseline
    """
    Filter tasks by due date range (inclusive).
    Tasks with no due_date are excluded if either due_before or due_after is set.

    Args:
        tasks: List of Task objects.
        due_before: Optional upper bound datetime for task due date.
        due_after: Optional lower bound datetime for task due date.

    Returns:
        Filtered list of Task objects.
    """
    if due_before is None and due_after is None:
        return tasks

    return [
        t
        for t in tasks
        if t.due_date is not None
        and _task_is_due_in_range(t.due_date, due_before, due_after)
    ]


def sort_tasks_by_sort_key(
    tasks: List[Task],  # noqa: UP006 # Baseline
    sort: Optional[str] = "due_date",  # noqa: UP006, UP045 # Baseline
) -> List[Task]:  # noqa: UP006 # Baseline
    """
    Sort tasks according to the requested sort key ('due_date', 'latest', 'oldest', 'priority').

    Args:
        tasks: List of Task objects to sort.
        sort: Sort mode ('due_date', 'latest', 'oldest', 'priority', defaults to 'due_date').
              'due_date': soonest due date first; tasks without a due date are placed last.
              'latest': newest created_at first.
              'oldest': oldest created_at first.
              'priority': urgency-based ordering (overdue > at-risk > claimed > unclaimed).

    Returns:
        Sorted list of Task objects.
    """
    if sort == "latest":
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    if sort == "oldest":
        return sorted(tasks, key=lambda t: t.created_at, reverse=False)
    if sort == "priority":
        return sort_tasks_by_priority(tasks)
    # "due_date" or default
    _far_future = datetime.max.replace(tzinfo=UTC)
    return sorted(
        tasks,
        key=lambda t: t.due_date if t.due_date is not None else _far_future,
    )


def inbox_task_categorizer(task: Task) -> Optional[str]:  # noqa: UP045 # Baseline
    """
    Maps an inbox task to a semantic category string for summary reporting.

    Args:
        task: Task object.

    Returns:
        Category string: 'Overdue', 'At-Risk', 'Claimed', 'Unclaimed'.
    """
    due_status = get_due_date_status(task.due_date)
    if due_status == "overdue":
        return "Overdue"
    if due_status == "at_risk":
        return "At-Risk"
    if task.assignee and task.assignee.strip():
        return "Claimed"
    return "Unclaimed"


def sort_tasks_by_priority(tasks: List[Task]) -> List[Task]:  # noqa: UP006 # Baseline
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
        due_date_sort = (
            task.due_date if task.due_date else datetime.max.replace(tzinfo=UTC)
        )

        return (due_status_priority, claimed_priority, due_date_sort, task.created_at)

    return sorted(tasks, key=sort_key)


def format_tasks_as_table(tasks: List[Task], base_url: str) -> str:  # noqa: UP006 # Baseline
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
        if task.claimed_at:  # noqa: SIM108 # Baseline
            claimed_at = task.claimed_at.strftime("%Y-%m-%d")
        else:
            claimed_at = "-"

        # Get assignee (empty if unclaimed)
        claimed = is_task_claimed(task.assignee)

        # Format due date
        due_date = format_due_date_with_status(task.due_date)

        # Merge candidate users and groups
        assignees = format_assignees(task.candidate_users, task.candidate_groups)

        table += (
            f"| {title_link} | {claimed_at} | {claimed} | {due_date} | {assignees} |\n"
        )

    # Add link to task inbox if more than 20 tasks
    if len(tasks) > 20:  # noqa: PLR2004 # Baseline
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
    if settings.di_env_mode == "CPD":  # noqa: SIM108 # Baseline
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
        LOGGER.warning(
            f"Unknown artifact type '{artifact_type}', using fallback URL format"
        )
        return f"{ui_base_url}/artifacts/{artifact_id}"

    return f"{ui_base_url}/{gov_prefix}/{artifact_path}/{artifact_id}"


def _format_artifact_name_link(artifact, ui_base_url: str) -> str:  # noqa: ANN001 # Baseline
    """
    Build a formatted name link for an artifact.

    Args:
        artifact: Artifact object (BusinessTerm or DataClass)
        ui_base_url: UI base URL for constructing artifact links

    Returns:
        Formatted name link (hyperlinked if artifact_id exists, plain text otherwise)
    """
    if (
        artifact.artifact_id
        and hasattr(artifact, "artifact_type")
        and artifact.artifact_type
    ):
        return f"[{artifact.name}]({build_artifact_url(artifact.artifact_id, artifact.artifact_type, ui_base_url)})"
    if artifact.artifact_id:
        # Fallback to old format if artifact_type is not available
        return f"[{artifact.name}]({ui_base_url}/artifacts/{artifact.artifact_id})"
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
        return description[: max_length - 3] + "..."
    return description


def format_artifacts_as_table(artifacts: List, base_url: str) -> str:  # noqa: UP006 # Baseline
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


def workflow_artifact_categorizer(artifact) -> Optional[str]:  # noqa: ANN001, UP045 # Baseline
    """
    Maps a glossary artifact (BusinessTerm or DataClass) to a semantic category
    string suitable for use with build_semantic_summary.

    Categories are based on the artifact's ``state`` field:
    - "Draft"            — artifact state is DRAFT / draft
    - "Published"        — artifact state is PUBLISHED / published / ACTIVE / active
    - "Steward-Assigned" — artifact has a workflow_id but is not yet published
    - "Other"            — any other non-None state

    Args:
        artifact: Artifact-like object with at least a ``state`` attribute and
                  optionally a ``workflow_id`` attribute.

    Returns:
        Category string, or ``None`` if the state cannot be determined.
    """
    state = getattr(artifact, "state", None)
    workflow_id = getattr(artifact, "workflow_id", None)

    if state is None:
        return None

    state_upper = state.upper()

    if state_upper in ("DRAFT",):
        return "Draft"
    if state_upper in ("PUBLISHED", "ACTIVE"):
        return "Published"
    if workflow_id:
        return "Steward-Assigned"
    return "Other"


def prompt_user_for_artifact_selection(artifacts: List, base_url: str) -> str:  # noqa: UP006 # Baseline
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
