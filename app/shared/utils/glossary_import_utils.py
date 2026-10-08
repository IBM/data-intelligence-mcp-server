# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Shared utility functions for glossary import status handling.

These helpers are used by both the glossary_generation internal service and the
import_glossary_status service to inspect and report on the outcome of a glossary
CSV import operation.
"""

from typing import Any, Dict, List

from app.core.settings import settings
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service


def check_import_timeout(
    elapsed_time: float,
    timeout_seconds: float,
    artifact_type: str,
    process_id: str,
    last_step_number: int | None,
    total_steps: int | None,
) -> None:
    """Check if import has timed out."""
    if elapsed_time >= timeout_seconds:
        raise ServiceError(
            f"{artifact_type.capitalize()} import timed out after 55 minutes.",
            remediation_steps=(
                "Please use the process_id with the import_glossary_status tool to check the status of the import. "
                f"Process ID: {process_id}. Last known status: Step {last_step_number}/{total_steps}"
            ),
        )


def log_children_statuses(children_statuses: List[Dict[str, Any]]) -> None:
    """Log details of child process statuses."""
    for child_status in children_statuses:
        child_type = child_status.get("type", "Unknown")
        child_name = child_status.get("name", "Unknown")
        child_status_val = child_status.get("status", "Unknown")
        child_percentage = child_status.get("percentage", 0)
        LOGGER.info(
            f"Child process: {child_name} (Type: {child_type}) - "
            f"Status: {child_status_val}, Progress: {child_percentage}%"
        )


def count_operations(operations_count: dict[str, Any], artifact_type: str) -> dict[str, dict[str, int]]:
    """Log operations count details and return per-type breakdown.

    Returns:
        A dict mapping each artifact type to its ``{"created": N, "modified": M}`` counts.
    """
    LOGGER.info(f"Operations count for {artifact_type}:")
    result: dict[str, dict[str, int]] = {}
    for op_type, op_counts in operations_count.items():
        if isinstance(op_counts, dict):
            created = op_counts.get("IMPORT_CREATE", 0)
            modified = op_counts.get("IMPORT_MODIFY", 0)
            result[op_type] = {"created": created, "modified": modified}
            LOGGER.info(f"{op_type}: Created={created}, Modified={modified}")
    return result


def check_operations_empty(operations_count: Dict[str, Any]) -> bool:
    """Check if operations_count indicates no items were imported."""
    if not operations_count:
        return True

    return all(
        not op_counts
        or (
            op_counts.get("IMPORT_CREATE", 0) == 0
            and op_counts.get("IMPORT_MODIFY", 0) == 0
        )
        for op_counts in operations_count.values()
        if isinstance(op_counts, dict)
    )


def construct_import_status_url(process_id: str) -> str:
    """
    Construct URL to check import status in the governance UI.

    Args:
        process_id: The process ID from the import operation

    Returns:
        The constructed URL to check import status
    """
    ui_base_url = str(tool_helper_service.ui_base_url)
    env_mode = settings.di_env_mode.upper()

    if env_mode == "CPD":
        return f"{ui_base_url}/gov/knowledge-accelerators?processid={process_id}"
    else:
        return f"{ui_base_url}/governance/knowledge-accelerators?processid={process_id}"


def build_import_warning_message(
    artifact_type: str,
    process_id: str,
    is_operations_empty: bool,
    has_errors: bool,
    message_resources: List[Dict[str, Any]],
) -> List[str]:
    """Build warning message for import issues."""
    import_status_url = construct_import_status_url(process_id)

    warning_msg = [
        f"WARNING: {artifact_type.capitalize()} import completed with status SUCCEEDED, but encountered issues:"
    ]

    if is_operations_empty:
        warning_msg.append(f"  - No {artifact_type}s were actually imported (operations_count is empty)")

    if has_errors and message_resources:
        warning_msg.append(f"  - Found {len(message_resources)} error/warning messages in import log")
        for i, msg in enumerate(message_resources[:5]):
            code = msg.get("code", "Unknown")
            message = msg.get("message", "No message")
            warning_msg.append(f"    {i+1}. [{code}] {message}")
        if len(message_resources) > 5:
            warning_msg.append(f"    ... and {len(message_resources) - 5} more messages")

    warning_msg.extend([
        "",
        "Import Details:",
        f"  - Process ID: {process_id}",
        f"  - Import Status URL: {import_status_url}",
        "  - Note: You may need appropriate permissions to access the import status logs",
        "",
        "This may indicate:",
        "  - CSV file is corrupted or has invalid data",
        "  - Category IDs in the CSV don't exist in the glossary",
        "  - CSV format issues (invalid headers, missing required fields)",
        "",
        "Recommended actions:",
        "  1. Check the import status logs using the URL above for detailed error messages",
        "  2. If CSV is corrupted, delete the CSV files and re-run review mode",
        "  3. If category IDs are invalid, ensure categories were created in review mode first",
        "  4. Verify CSV file format matches the expected schema",
    ])

    LOGGER.warning("\n".join(warning_msg))
    return warning_msg


def build_warning_messages(
    artifact_type: str,
    process_id: str,
    operations_count: Dict[str, Any],
    messages: Dict[str, Any],
) -> List[str]:
    """Build warning messages for a successful import with issues."""
    message_resources = messages.get("resources", [])
    has_errors = any(
        msg.get("code", "").startswith("GIM") and "E" in msg.get("code", "")
        for msg in message_resources
    )
    is_operations_empty = check_operations_empty(operations_count)

    if has_errors or is_operations_empty:
        return build_import_warning_message(
            artifact_type, process_id, is_operations_empty, has_errors, message_resources
        )

    return []


def handle_succeeded_status(
    artifact_type: str,
    process_id: str,
    operations_count: Dict[str, Any],
    messages: Dict[str, Any],
) -> List[str]:
    """Handle SUCCEEDED status with validation."""
    warning_msg = build_warning_messages(
        artifact_type, process_id, operations_count, messages
    )
    if warning_msg:
        raise ServiceError("\n".join(warning_msg))

    LOGGER.info(f"{artifact_type.capitalize()} import completed successfully.")
    if operations_count:
        LOGGER.info(f"Final import summary for {artifact_type}:")
        for op_type, op_counts in operations_count.items():
            if isinstance(op_counts, dict):
                created = op_counts.get("IMPORT_CREATE", 0)
                modified = op_counts.get("IMPORT_MODIFY", 0)
                LOGGER.info(f"{op_type}: {created} created, {modified} modified")
    return warning_msg


def build_failed_error_message(
    artifact_type: str,
    step_number: int,
    step_message: str,
    children_statuses: List[Dict[str, Any]],
    operations_count: Dict[str, Any],
) -> str:
    """Build an error message for a failed import."""
    error_details = [
        f"{artifact_type.capitalize()} import failed at step {step_number}: {step_message}"
    ]

    if children_statuses:
        failed_children = [c for c in children_statuses if c.get("status") == "FAILED"]
        if failed_children:
            error_details.append("Failed child processes:")
            for child in failed_children:
                error_details.append(
                    f"  - {child.get('name', 'Unknown')}: {child.get('status', 'Unknown')}"
                )

    if operations_count:
        error_details.append("Operations attempted:")
        for op_type, op_counts in operations_count.items():
            if isinstance(op_counts, dict):
                created = op_counts.get("IMPORT_CREATE", 0)
                modified = op_counts.get("IMPORT_MODIFY", 0)
                error_details.append(f"{op_type}: {created} created, {modified} modified")

    return "\n".join(error_details)


def handle_failed_status(
    artifact_type: str,
    step_number: int,
    step_message: str,
    children_statuses: List[Dict[str, Any]],
    operations_count: Dict[str, Any],
) -> None:
    """Handle FAILED status."""
    raise ServiceError(
        build_failed_error_message(
            artifact_type,
            step_number,
            step_message,
            children_statuses,
            operations_count,
        )
    )
