# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Tool for performing actions on workflow tasks.

This module provides functionality to claim, complete, or unclaim workflow tasks by:
1. Retrieving task details and form properties (for claim/complete)
2. Creating an MCP elicitation request for user input (for complete only)
3. Performing the specified action on the task
"""

import json
import re
from enum import Enum
from typing import List, Dict, Optional, Any, Type, Literal
from pydantic import BaseModel, Field, create_model
from app.core.registry import service_registry
from app.core.auth import get_user_identifier
from app.services.constants import WORKFLOW_TASK_ENDPOINT
from app.services.workflow.models.task_action import (
    TaskActionRequest,
    TaskActionResponse,
    FormProperty
)
from app.services.workflow.utils.task_utils import _parse_task_title_from_json
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.llm_utils import client_supports_elicitation
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.client_detection import MinimalContext

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context


class ElicitationNotSupportedError(Exception):
    """Raised when the MCP client does not support elicitation."""
    pass


REJECTION_COMMENT_MIN_LENGTH = 4
_PENDING_REJECTION_ACTIONS: Dict[str, str] = {}

def _get_task_display_name(task_data: Dict[str, Any]) -> str:
    """
    Extract the best display name for a task, preferring title over name.
    
    Args:
        task_data: Task data dictionary from API response
        
    Returns:
        Task display name (title if available, otherwise name, otherwise "Unknown Task")
    """
    entity = task_data.get("entity", {})
    metadata = task_data.get("metadata", {})
    
    # Try to get task_title from entity first
    task_title_raw = entity.get("task_title", "")
    if task_title_raw:
        task_title = _parse_task_title_from_json(task_title_raw)
        if task_title:
            return task_title
    
    # Fall back to metadata name
    return metadata.get("name", "Unknown Task")



async def _get_task_details(task_id: str) -> Dict[str, Any]:
    """
    Retrieve task details from the workflow API.
    
    Args:
        task_id: Unique identifier of the task
        
    Returns:
        Dictionary containing task details including form properties
        
    Raises:
        ToolError: If the request fails
    """
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}/{task_id}",
            tool_name="perform_workflow_task_action"
        )
        return response
    except Exception as e:
        LOGGER.error(f"Failed to retrieve task details for task_id {task_id}: {str(e)}")
        raise ToolError(f"Failed to retrieve task details: {str(e)}")


def _is_task_already_claimed(task_data: Dict[str, Any]) -> bool:
    """
    Check if a task is already claimed.
    
    Args:
        task_data: Task data dictionary from API response
        
    Returns:
        True if task is claimed, False otherwise
    """
    entity = task_data.get("entity", {})
    claimed_at = entity.get("claimed_at")
    
    if claimed_at:
        LOGGER.info(f"Task is already claimed (claimed_at: {claimed_at})")
        return True
    
    return False


def _transform_form_properties(form_properties: List[Dict[str, Any]]) -> List[FormProperty]:
    """
    Transform raw form properties into simplified format.
    
    Args:
        form_properties: List of raw form property dictionaries from API
        
    Returns:
        List of FormProperty objects with id and value populated
    """
    simplified_properties = []
    
    for prop in form_properties:
        # Skip non-dictionary elements
        if not isinstance(prop, dict):
            LOGGER.warning(f"Skipping non-dictionary form property during transformation: {prop} (type: {type(prop).__name__})")
            continue
        
        # Extract basic properties
        prop_id = prop.get("id")
        prop_value = prop.get("value", "")
        
        if prop_id is None:
            LOGGER.warning(f"Skipping form property without id: {prop}")
            continue
        
        # Create simplified form property
        # For now, only populate id and value as strings, leave others empty
        form_prop = FormProperty(
            id=prop_id,
            value=str(prop_value) if prop_value is not None else "",
            date_value=None,
            period_value=None,
            long_value=None,
            list_value=None
        )
        
        simplified_properties.append(form_prop)
    
    LOGGER.info(f"Transformed {len(simplified_properties)} form properties")
    return simplified_properties


def _sanitize_enum_member_name(enum_value_id: str, index: int) -> str:
    """Create a valid, stable Enum member name for a runtime-generated choice."""
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", enum_value_id).strip("_").upper()
    if not sanitized:
        sanitized = f"VALUE_{index}"
    elif sanitized[0].isdigit():
        sanitized = f"VALUE_{sanitized}"
    return sanitized


def _build_runtime_multi_select_type(field_name: str, enum_ids: List[str]) -> Any:
    """
    Build a runtime enum class for elicitation schema generation.

    Returns a dynamically created enum class object (typed as `type`), not an
    enum instance. Using `Enum(...)` instead of a dynamically constructed
    Literal produces a stable JSON schema with explicit enum choices for MCP
    clients.
    """
    members: Dict[str, str] = {}
    for index, enum_id in enumerate(enum_ids):
        member_name = _sanitize_enum_member_name(enum_id, index)
        while member_name in members:
            member_name = f"{member_name}_{index}"
        members[member_name] = enum_id

    enum_type = Enum(f"{field_name.title().replace('_', '')}Choices", members)
    LOGGER.debug(
        "Generated runtime Enum for elicitation field '%s' with values=%s",
        field_name,
        list(members.values())
    )
    return enum_type


def _resolve_action_field_type(action_prop: Dict[str, Any]) -> type:
    """
    Resolve the Python type for the special 'action' field on complete actions.

    Args:
        action_prop: The form property dict whose id is "action"

    Returns:
        A runtime Enum type if enum_values exist, otherwise str
    """
    enum_ids = _extract_enum_value_ids(action_prop)
    if enum_ids:
        action_type = _build_runtime_multi_select_type("action", enum_ids)
        LOGGER.info(
            "Added 'action' field for complete action with runtime enum choices from enum_values: %s",
            enum_ids
        )
        return action_type
    LOGGER.info("Added 'action' field for complete action (no enum_values found, falling back to string)")
    return str


def _add_action_field(fields: Dict[str, Any], form_properties: List[Dict[str, Any]]) -> None:
    """
    Add the special 'action' radio field for the 'complete' action.

    The field is only added when the form properties contain an "action"
    property.  Its type is derived from the property's enum_values when
    available, falling back to a plain string.

    Args:
        fields: Mutable field-definitions dictionary to update in-place
        form_properties: List of raw form property dictionaries from API
    """
    action_prop = next(
        (prop for prop in form_properties
         if isinstance(prop, dict) and prop.get("id") == "action"),
        None
    )
    if not action_prop:
        return

    action_type = _resolve_action_field_type(action_prop)
    fields["action"] = (
        action_type,
        Field(
            ...,
            description="Select the action to perform on the task",
            json_schema_extra={"ui": {"widget": "radio"}}
        )
    )


def _resolve_property_type(prop: Dict[str, Any]) -> type:
    """
    Determine the Python type for a single form property.

    If the property carries enum_values and is of an enum/string type,
    a runtime Enum type is returned; otherwise the raw type is mapped to a
    standard Python type.

    Args:
        prop: Form property dictionary

    Returns:
        Python type (Enum, str, int, float, bool, …)
    """
    prop_id = str(prop.get("id", "unknown"))
    prop_type = prop.get("type", "string")
    enum_ids = _extract_enum_value_ids(prop)

    if enum_ids and prop_type.lower() in ("enum", "string"):
        resolved_type = _build_runtime_multi_select_type(prop_id, enum_ids)
        LOGGER.debug(
            "Property '%s' uses runtime Enum from enum_values=%s",
            prop_id,
            enum_ids
        )
        return resolved_type

    resolved_type = _map_property_type_to_python_type(prop_type)
    LOGGER.debug(
        "Property '%s' resolved to python type '%s' from prop_type='%s'",
        prop_id,
        getattr(resolved_type, "__name__", str(resolved_type)),
        prop_type
    )
    return resolved_type


def _form_supports_rejection_comment_validation(form_properties: List[Dict[str, Any]]) -> bool:
    """
    Determine whether the task form can express a rejection action with a comment.

    Args:
        form_properties: Raw form property dictionaries from the task

    Returns:
        True when the form contains both an action field with reject-like choices
        and a comment field.
    """
    action_prop = next(
        (prop for prop in form_properties if isinstance(prop, dict) and prop.get("id") == "action"),
        None
    )
    if not action_prop:
        return False

    has_comment_field = any(
        isinstance(prop, dict) and prop.get("id") == "comment"
        for prop in form_properties
    )
    if not has_comment_field:
        return False

    return any(
        _is_reject_like_action_value(enum_id)
        for enum_id in _extract_enum_value_ids(action_prop)
    )


def _is_reject_like_action_value(action_value: Any) -> bool:
    """
    Determine whether a submitted action value semantically represents rejection.

    Args:
        action_value: Submitted or configured action value

    Returns:
        True when the value is a reject-like action identifier.
    """
    if action_value is None:
        return False

    normalized = re.sub(r"[^a-z0-9]+", "", str(action_value).strip().lower())
    return "reject" in normalized if normalized else False


def _build_rejection_comment_retry_metadata(action_value: Any) -> Dict[str, str]:
    """
    Build machine-readable retry metadata for rejection comment recovery.

    Args:
        action_value: The already-selected reject-like action value

    Returns:
        Metadata that helps clients/LLMs retry with only the missing comment.
    """
    return {
        "retry_reason": "rejection_comment_too_short",
        "missing_field": "comment",
        "preserved_action": str(action_value),
        "min_length": str(REJECTION_COMMENT_MIN_LENGTH),
    }


def _store_pending_rejection_action(task_id: str, action_value: Any) -> None:
    """Store the reject-like action so a follow-up retry can omit it."""
    _PENDING_REJECTION_ACTIONS[task_id] = str(action_value)


def _pop_pending_rejection_action(task_id: str) -> Optional[str]:
    """Remove and return a previously stored reject-like action."""
    return _PENDING_REJECTION_ACTIONS.pop(task_id, None)


def _peek_pending_rejection_action(task_id: str) -> Optional[str]:
    """Return a previously stored reject-like action without clearing it."""
    return _PENDING_REJECTION_ACTIONS.get(task_id)


def _restore_pending_rejection_action(
    task_id: str,
    form_values: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Restore a previously stored reject-like action when retry input contains only comment.

    Args:
        task_id: Task identifier used as retry-state key
        form_values: User-supplied retry values

    Returns:
        Updated form values with restored action when applicable.
    """
    if not form_values:
        return form_values

    if form_values.get("action"):
        return form_values

    if "comment" not in form_values:
        return form_values

    pending_action = _peek_pending_rejection_action(task_id)
    if not pending_action:
        return form_values

    restored_values = dict(form_values)
    restored_values["action"] = pending_action
    return restored_values


def _build_rejection_comment_retry_message(action_value: Any) -> str:
    """
    Build a targeted retry message when only a rejection justification comment is missing.

    Args:
        action_value: The already-selected reject-like action value

    Returns:
        Retry guidance focused only on providing a sufficient comment.
    """
    return (
        f"The requested action '{action_value}' is a rejection action. "
        f"The task's state is unchanged.\n\n"
        f"Please ask the user for a justification comment and retry the task completion "
        f"using the same action:\n"
        f"- comment (string): User-provided justification comment. Minimum length: "
        f"{REJECTION_COMMENT_MIN_LENGTH} characters.\n\n"
        f"Do not invent, generate, assume, summarize, or paraphrase the comment yourself. "
        f"The comment must come from the user. If no user-provided comment is available yet, "
        f"request it explicitly instead of filling form_values yourself.\n\n"
        f"You do not need to provide the action '{action_value}' again; only a user-provided "
        f"sufficient comment in form_values is needed, and I will fill in the action "
        f"'{action_value}'."
    )


def _validate_rejection_comment(
    task_id: str,
    form_values: Optional[Dict[str, Any]]
) -> Optional[TaskActionResponse]:
    """
    Validate the hard-coded rejection comment rule for task completion.

    Args:
        task_id: Task identifier used for retry-state persistence
        form_values: User-provided form values

    Returns:
        None when valid or not applicable, otherwise a retry response with metadata.
    """
    if not form_values:
        return None

    action_value = form_values.get("action")
    if not _is_reject_like_action_value(action_value):
        _pop_pending_rejection_action(task_id)
        return None

    comment_value = form_values.get("comment")
    comment_text = "" if comment_value is None else str(comment_value).strip()
    if len(comment_text) >= REJECTION_COMMENT_MIN_LENGTH:
        return None

    _store_pending_rejection_action(task_id, action_value)
    return TaskActionResponse(
        status_code=400,
        message=_build_rejection_comment_retry_message(action_value),
        retry_metadata=_build_rejection_comment_retry_metadata(action_value)
    )


def _build_property_field(prop: Dict[str, Any], is_complete_action: bool) -> Optional[tuple]:
    """
    Build a single (name, (type, Field)) tuple for a form property.

    Args:
        prop: Raw form property dictionary from the API
        is_complete_action: True when the overall action is "complete"

    Returns:
        A (prop_id, (python_type, Field)) tuple, or None when the
        property should be skipped
    """
    prop_id = prop.get("id")

    if not prop_id:
        return None

    # Skip 'action' field from form properties – we add our own above
    if prop_id == "action" and is_complete_action:
        return None

    prop_name = prop.get("name", prop_id)
    description = prop.get("description", prop_name)
    python_type = _resolve_property_type(prop)
    LOGGER.debug(
        "Building elicitation field '%s': flowable_type='%s', resolved_type='%s', writable=%s",
        prop_id,
        prop.get("type", "string"),
        getattr(python_type, "__name__", str(python_type)),
        _prop_writable(prop)
    )

    field_default = ... if isinstance(python_type, type) and issubclass(python_type, Enum) else ""
    return (prop_id, (python_type, Field(default=field_default, description=description)))


def _create_elicitation_schema(form_properties: List[Dict[str, Any]], action: str = "") -> Type[BaseModel]:
    """
    Create a dynamic pydantic BaseModel class for MCP elicitation from form properties.
    
    Args:
        form_properties: List of raw form property dictionaries from API
        action: Action being performed (used to determine if action field should be added)
        
    Returns:
        A pydantic BaseModel class with fields corresponding to form properties
    """
    fields: Dict[str, Any] = {}

    LOGGER.debug(
        "Creating elicitation schema for action='%s' from raw property ids=%s",
        action,
        [prop.get("id") for prop in form_properties if isinstance(prop, dict)]
    )

    # For 'complete' action, add an 'action' field as the first field
    if action == "complete":
        _add_action_field(fields, form_properties)

    # Build field definitions from each valid form property
    is_complete_action = action == "complete"
    for prop in form_properties:
        if not isinstance(prop, dict):
            LOGGER.warning(f"Skipping non-dictionary property in schema creation: {prop} (type: {type(prop).__name__})")
            continue

        result = _build_property_field(prop, is_complete_action)
        if result is not None:
            fields[result[0]] = result[1]

    model = create_model('DynamicElicitationModel', **fields)
    try:
        schema = model.model_json_schema()
        LOGGER.debug(
            "Generated elicitation schema fields=%s",
            {
                field_name: schema.get("properties", {}).get(field_name, {})
                for field_name in fields.keys()
            }
        )
    except Exception as exc:
        LOGGER.warning("Failed to serialize elicitation schema for debug logging: %s", exc)

    return model


def _map_property_type_to_python_type(prop_type: str) -> type:
    """
    Map form property type to Python type for pydantic fields.
    
    Args:
        prop_type: Form property type string (e.g., "string", "integer", "boolean", "date")
        
    Returns:
        Python type (str, int, float, bool)
    """
    type_mapping = {
        "string": str,
        "text": str,
        "integer": int,
        "long": int,
        "double": float,
        "float": float,
        "boolean": bool,
        "date": str,
        "datetime": str,
        "time": str,
        "enum": str,
        "multi-enum": List[str],
    }
    
    return type_mapping.get(prop_type.lower(), str)


def _extract_enum_value_ids(prop: Dict[str, Any]) -> List[str]:
    """
    Extract enum value IDs from a form property's enum_values field.
    
    Args:
        prop: Form property dictionary that may contain an 'enum_values' list
        
    Returns:
        List of enum value ID strings, or empty list if not available
    """
    enum_values = prop.get("enum_values", [])
    if not isinstance(enum_values, list) or not enum_values:
        LOGGER.debug("Property '%s' has no enum_values", prop.get("id", "unknown"))
        return []
    
    ids = []
    for ev in enum_values:
        if isinstance(ev, dict) and "id" in ev:
            ids.append(str(ev["id"]))
        elif isinstance(ev, str):
            ids.append(ev)

    LOGGER.debug(
        "Extracted enum_values for property '%s': raw=%s, ids=%s",
        prop.get("id", "unknown"),
        enum_values,
        ids
    )
    return ids


def _describe_writable_properties(form_properties: List[Dict[str, Any]], action: str = "") -> str:
    """
    Build a human-readable description of writable form properties.
    
    This is used as a fallback when MCP elicitation is not supported, so the
    client/LLM can present the required fields to the user.
    
    Args:
        form_properties: List of raw form property dictionaries from API
        action: Action being performed (used to determine if action field should be included)
        
    Returns:
        Formatted string listing each writable field with its details
    """
    writable_props = [
        prop for prop in form_properties
        if isinstance(prop, dict) and _prop_writable(prop)
    ]
    
    if not writable_props:
        return "No writable form properties found."
    
    lines = []
    requires_rejection_comment_validation = (
        action == "complete" and _form_supports_rejection_comment_validation(form_properties)
    )
    
    # For 'complete' action, include the special 'action' field first
    if action == "complete":
        _append_action_field_description(lines, form_properties)
    
    for prop in writable_props:
        prop_id = prop.get("id", "unknown")
        if prop_id == "action" and action == "complete":
            continue  # already handled above
        lines.append(_describe_single_property(prop, requires_rejection_comment_validation))
    
    return "\n".join(lines)


def _append_action_field_description(lines: List[str], form_properties: List[Dict[str, Any]]) -> None:
    """
    Append the special 'action' field description for complete actions.
    
    Args:
        lines: Mutable list to append the description line to
        form_properties: Raw form property dictionaries to find the action field in
    """
    action_prop = next(
        (prop for prop in form_properties
         if isinstance(prop, dict) and prop.get("id") == "action"),
        None
    )
    if not action_prop:
        return
    
    choices = _format_choices(action_prop)
    if choices:
        lines.append(f"⊙ action: {choices}")
    else:
        lines.append("⊙ action")


def _describe_single_property(
    prop: Dict[str, Any],
    requires_rejection_comment_validation: bool = False
) -> str:
    """
    Format a single form property as a human-readable description line.
    
    Args:
        prop: Form property dictionary with id, type, name/description, and optional enum_values
        requires_rejection_comment_validation: True when comment should mention the
            hard-coded minimum length for rejection flows
        
    Returns:
        Formatted description string like "🗈 comment: description" or "field_id: description [Choices: a, b]"
    """
    prop_id = prop.get("id", "unknown")
    prop_name = prop.get("name", prop_id)
    description = prop.get("description", prop_name)

    if prop_id == "comment" and requires_rejection_comment_validation:
        description = (
            f"{description} Minimum length: {REJECTION_COMMENT_MIN_LENGTH} characters "
            f"when submitting a rejection action."
        )
    
    choices = _format_choices(prop)
    suffix = f" [Choices: {choices}]" if choices else ""
    
    # Add special prefix for comment fields
    if prop_id == "comment":
        return f"🗈 {prop_id}: {description}{suffix}"
    else:
        return f"{prop_id}: {description}{suffix}"


def _format_choices(prop: Dict[str, Any]) -> Optional[str]:
    """
    Format enum choices from a property as a comma-separated string.
    
    Args:
        prop: Form property that may contain enum_values
        
    Returns:
        Comma-separated choices string, or None if no enum values
    """
    enum_ids = _extract_enum_value_ids(prop)
    return ", ".join(enum_ids) if enum_ids else None


def _prop_writable(prop: Dict[str, Any]) -> bool:
    """
    Check if a property is writable.
    
    Args:
        prop: Form property dictionary
        
    Returns:
        True if writable, False otherwise
    """
    return prop.get("writable", True)


def _filter_writable_properties(form_properties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter form properties to only writable ones, with type safety.
    
    Args:
        form_properties: List of raw form property dictionaries
        
    Returns:
        List of writable properties (dictionaries only)
    """
    return [
        prop for prop in form_properties
        if isinstance(prop, dict) and _prop_writable(prop)
    ]


def _is_elicitation_not_supported_error(error_str: str) -> bool:
    """
    Check if an error indicates that elicitation is not supported by the MCP client.
    
    Common patterns: MCP error code -32042, "elicitation" in message, "not supported"
    
    Args:
        error_str: Error message string
        
    Returns:
        True if error indicates elicitation is not supported
    """
    return (
        "-32042" in error_str
        or "elicitation" in error_str.lower()
        or "not supported" in error_str.lower()
    )


def _convert_response_data_to_dict(response_data: Any) -> Dict[str, Any]:
    """
    Convert elicitation response data to dictionary.
    
    Args:
        response_data: Response data from elicitation (BaseModel or dict)
        
    Returns:
        Dictionary representation of the response data
    """
    if isinstance(response_data, BaseModel):
        return response_data.model_dump()
    return response_data or {}


async def _call_elicit_with_error_handling(
    ctx: Context,
    message: str,
    response_type: Type[BaseModel],
    operation_name: str,
    raise_on_not_supported: bool = True,
    action_context: str = ""
) -> Optional[Any]:
    """
    Call ctx.elicit with standardized error handling and logging.
    
    Args:
        ctx: MCP context for elicitation
        message: Message to display to user
        response_type: Pydantic model for response schema
        operation_name: Name of operation for logging (e.g., "elicitation", "claim preview")
        raise_on_not_supported: If True, raise ElicitationNotSupportedError when not supported;
                                if False, return a sentinel value ('NOT_SUPPORTED')
        action_context: Additional context for error messages (e.g., action name like "complete")
        
    Returns:
        Response object if successful and accepted
        None if declined/cancelled
        'NOT_SUPPORTED' string if not supported and raise_on_not_supported=False
        
    Raises:
        ElicitationNotSupportedError: If client doesn't support elicitation and raise_on_not_supported=True
    """
    try:
        response = await ctx.elicit(
            message=message,
            response_type=response_type
        )
        
        if response is not None and response.action == 'accept':
            LOGGER.info(f"{operation_name} accepted, received: {response.data}")
            return response
        else:
            LOGGER.info(f"{operation_name} declined or cancelled")
            return None
            
    except Exception as e:
        error_str = str(e)
        LOGGER.warning(f"Failed to call {operation_name}: {error_str}")
        
        if _is_elicitation_not_supported_error(error_str):
            if raise_on_not_supported:
                LOGGER.error(f"MCP client does not support elicitation: {error_str}")
                action_msg = f" for the '{action_context}' action" if action_context else ""
                raise ElicitationNotSupportedError(
                    f"The MCP client does not support elicitation, which is required"
                    f"{action_msg}. The task's state is unchanged. Error: {error_str}"
                )
            else:
                LOGGER.info(f"MCP client does not support {operation_name}; proceeding without it")
                return 'NOT_SUPPORTED'
        
        return None


def _validate_and_filter_properties(
    ctx: Context,
    form_properties: List[Dict[str, Any]],
    operation_name: str
) -> Optional[List[Dict[str, Any]]]:
    """
    Validate context and filter form properties to writable ones.
    
    Args:
        ctx: MCP context (can be None)
        form_properties: List of raw form property dictionaries
        operation_name: Name of operation for logging (e.g., "elicitation", "claim preview")
        
    Returns:
        List of writable properties if validation passes, None otherwise
    """
    if ctx is None:
        LOGGER.warning(f"No context provided, skipping {operation_name}")
        return None
    
    # Log any non-dictionary elements for debugging (only for main elicitation)
    if operation_name == "elicitation":
        non_dict_elements = [prop for prop in form_properties if not isinstance(prop, dict)]
        if non_dict_elements:
            LOGGER.warning(
                f"Found {len(non_dict_elements)} non-dictionary elements in form_properties "
                f"during {operation_name}: {non_dict_elements[:5]}..."
            )
    
    # Filter to writable properties
    writable_props = _filter_writable_properties(form_properties)
    
    if not writable_props:
        LOGGER.info(f"No writable properties found for {operation_name}; skipping")
        return None
    
    return writable_props


async def _handle_elicitation(
    form_properties: List[Dict[str, Any]],
    task_display_name: str,
    action: str,
    ctx: Context
) -> Optional[Dict[str, str]]:
    """
    Handle MCP elicitation to collect user input for form properties.
    
    Args:
        form_properties: List of raw form property dictionaries
        task_display_name: Display name of the task for context in the elicitation message
        action: Action being performed (claim or complete)
        ctx: MCP context for elicitation
        
    Returns:
        Dictionary mapping property IDs to user-provided values, or None if elicitation failed
    """
    # Validate context and filter to writable properties
    writable_props = _validate_and_filter_properties(ctx, form_properties, "elicitation")
    if writable_props is None:
        return None
    
    # Create JSON Schema for elicitation
    schema = _create_elicitation_schema(writable_props, action)
    
    # Create elicitation message
    message = f"Please provide the required information to {action} task: {task_display_name}"
    
    LOGGER.info(f"Sending elicitation request for {len(writable_props)} properties for action: {action}")
    response = await _call_elicit_with_error_handling(ctx, message, schema, "elicitation", action_context=action)
    
    if response is not None:
        return _convert_response_data_to_dict(response.data)
    return None


async def _handle_claim_preview_elicitation(
    form_properties: List[Dict[str, Any]],
    task_display_name: str,
    ctx: Context
) -> Optional[bool]:
    """
    Show a confirmation-only elicitation before claiming a task.

    The prompt explains which information will be required later to complete
    the task, but does not collect any completion values yet.
    
    Args:
        form_properties: List of raw form property dictionaries
        task_display_name: Display name of the task
        ctx: MCP context for elicitation
        
    Returns:
        True if user confirms claim, False if declined, True if elicitation not supported
    """
    # Validate context and filter to writable properties
    writable_props = _validate_and_filter_properties(ctx, form_properties, "claim preview elicitation")
    if writable_props is None:
        # For claim preview, if validation fails, proceed with claim (return True)
        return True

    description = _describe_writable_properties(form_properties, "complete")
    confirmation_model = create_model(
        'ClaimPreviewConfirmationModel',
        confirm_claim=(
            bool,
            Field(
                ...,
                description="Confirm whether you want to claim this task now after reviewing the required completion information"
            )
        )
    )

    message = (
        f"**{task_display_name}**\n"
        f"Claiming this task assigns it to you. To complete it, you'll have to provide:\n"
        f"{description}\n\n"
        f"Do you want to claim this task now?"
    )

    LOGGER.info(
        "Sending claim preview elicitation for task '%s' with %d writable properties",
        task_display_name,
        len(writable_props)
    )
    response = await _call_elicit_with_error_handling(
        ctx, message, confirmation_model, "claim preview elicitation", raise_on_not_supported=False
    )
    
    # Handle different response types
    if response == 'NOT_SUPPORTED':
        # Elicitation not supported, proceed with claim
        return True
    elif response is None:
        # User declined or cancelled
        return False
    
    # User accepted, check the confirmation value
    data = _convert_response_data_to_dict(response.data)
    confirmed = bool(data.get("confirm_claim"))
    LOGGER.info("Claim preview elicitation accepted with confirm_claim=%s", confirmed)
    return confirmed


def _extract_status_from_response(response: Any) -> Optional[int]:
    """
    Extract HTTP status code from a successful API response body.
    
    Args:
        response: Response data from API (expected dict)
        
    Returns:
        Status code integer if found, None otherwise
    """
    if isinstance(response, dict):
        if "status" in response:
            return response.get("status")
        if "statusCode" in response:
            return response.get("statusCode")
    return None


def _extract_status_from_error(error_msg: str) -> Optional[int]:
    """
    Extract HTTP status code from an error message string.
    
    Args:
        error_msg: Error message string, potentially containing "HTTP error NNN"
        
    Returns:
        Status code integer if found, None otherwise
    """
    match = re.search(r"HTTP error (\d+)", error_msg)
    if match:
        return int(match.group(1))
    return None


async def _perform_claim_or_complete(
    task_id: str,
    action: str,
    user_id: str,
    form_properties: List[FormProperty]
) -> int:
    """
    Perform claim or complete action on the task.
    
    Args:
        task_id: Unique identifier of the task
        action: Either "claim" or "complete"
        user_id: User ID to associate with the action
        form_properties: List of simplified form properties
        
    Returns:
        HTTP status code from the action
        
    Raises:
        ToolError: If the request fails
    """
    # Convert FormProperty objects to dictionaries for the API request
    form_props_dict = [
        {
            "id": prop.id,
            "value": prop.value,
            "date_value": prop.date_value,
            "period_value": prop.period_value,
            "long_value": prop.long_value,
            "list_value": prop.list_value
        }
        for prop in form_properties
    ]
    
    # Build request body
    request_body = {
        "action": action,
        "assignee": user_id,
        "form_properties": form_props_dict
    }
    
    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}/{task_id}/actions",
            json=request_body,
            tool_name="perform_workflow_task_action"
        )
        
        # If we reach here, the request was successful (2xx status)
        LOGGER.info(f"Task {task_id} {action} successful for user {user_id}. Response: {response}")
        
        # Try to extract status from response body if available
        status = _extract_status_from_response(response)
        if status is not None:
            return status
        
        return 200  # Default success status code
        
    except Exception as e:
        error_msg = str(e)
        LOGGER.error(f"Failed to {action} task {task_id}: {error_msg}")
        
        # Try to extract status code from error message
        status = _extract_status_from_error(error_msg)
        if status is not None:
            LOGGER.info(f"Extracted status code {status} from error")
            return status
        
        # If we can't extract a status code, raise ToolError
        raise ToolError(f"Failed to {action} task: {str(e)}")


async def _perform_unclaim(task_id: str) -> int:
    """
    Perform unclaim action on the task.
    
    Args:
        task_id: Unique identifier of the task
        
    Returns:
        HTTP status code from the unclaim action
        
    Raises:
        ToolError: If the request fails
    """
    # Build request body with task ID in array format
    request_body = {
        "ids": [task_id]
    }
    
    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}{WORKFLOW_TASK_ENDPOINT}/unclaim",
            json=request_body,
            tool_name="perform_workflow_task_action"
        )
        
        # Extract status code from response if available
        status = _extract_status_from_response(response)
        if status is not None:
            LOGGER.info(f"Task {task_id} unclaimed with status {status}")
            return status
        
        # Default success status code if no status in response
        LOGGER.info(f"Task {task_id} unclaimed successfully")
        return 200
        
    except Exception as e:
        LOGGER.error(f"Failed to unclaim task {task_id}: {str(e)}")
        # Try to extract status code from error message
        status = _extract_status_from_error(str(e))
        if status is not None:
            return status
        raise ToolError(f"Failed to unclaim task: {str(e)}")


async def _get_authenticated_user_id() -> Optional[str]:
    """
    Get the authenticated user ID from the bearer token.
    
    Returns:
        User ID string or None if authentication fails
        
    Raises:
        ToolError: If user identifier cannot be retrieved
    """
    try:
        user_id = await get_user_identifier()
        if not user_id:
            raise ToolError("Unable to retrieve user identifier from authentication token")
        LOGGER.info(f"Using authenticated user ID: {user_id}")
        return user_id
    except Exception as e:
        LOGGER.error(f"Failed to get user identifier: {str(e)}")
        raise ToolError(f"Authentication required: {str(e)}")


def _extract_and_validate_form_properties(task_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract and validate form properties from task data.
    
    Args:
        task_data: Task data dictionary from API response
        
    Returns:
        List of validated form property dictionaries
    """
    entity = task_data.get("entity", {})
    form_properties_raw = entity.get("form_properties", [])
    
    # Validate that form_properties is a list
    if not isinstance(form_properties_raw, list):
        LOGGER.warning(f"form_properties is not a list: {form_properties_raw} (type: {type(form_properties_raw).__name__})")
        return []
    
    # Log any non-dictionary elements for debugging
    non_dict_elements = [prop for prop in form_properties_raw if not isinstance(prop, dict)]
    if non_dict_elements:
        LOGGER.warning(f"Found {len(non_dict_elements)} non-dictionary elements in form_properties: {non_dict_elements[:5]}...")
    
    if not form_properties_raw:
        LOGGER.info("No form properties found, proceeding with empty form")
        return []
    
    return form_properties_raw


def _normalize_form_value_for_rest(value: Any) -> str:
    """Convert elicitation values into raw REST-compatible string payload values."""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _prepare_form_properties_with_user_values(
    form_properties: List[FormProperty],
    user_values: Optional[Dict[str, str]]
) -> None:
    """
    Update form properties with user values from elicitation.
    
    Args:
        form_properties: List of FormProperty objects to update
        user_values: Dictionary of property IDs to user-provided values
    """
    if not user_values:
        return
    
    for prop in form_properties:
        if prop.id in user_values:
            prop.value = _normalize_form_value_for_rest(user_values[prop.id])
            LOGGER.info(f"Updated property {prop.id} with elicitation value")


def _generate_action_message(action: str, status_code: int) -> str:
    """
    Generate appropriate success/error message based on action and status code.
    
    Args:
        action: Action type (claim, complete, unclaim)
        status_code: HTTP status code from the action
        
    Returns:
        Appropriate message string
    """
    # Handle unclaim separately as it has its own endpoint
    if action == "unclaim":
        return "Task unclaimed successfully" if status_code == 200 else f"Unclaim completed with status {status_code}"
    
    # Handle claim and complete
    if action == "claim":
        success_message = "Task claimed successfully"
        error_message = f"Claim completed with status {status_code}"
    elif action == "complete":
        success_message = "Task completed successfully"
        error_message = f"Complete completed with status {status_code}"
    else:
        success_message = f"Task {action} successfully"
        error_message = f"{action.capitalize()} completed with status {status_code}"
    
    return success_message if status_code == 200 else error_message


async def _handle_unclaim_action(task_id: str) -> TaskActionResponse:
    """
    Handle the unclaim action flow.
    
    Args:
        task_id: Unique identifier of the task
        
    Returns:
        TaskActionResponse with status and message
    """
    try:
        status_code = await _perform_unclaim(task_id)
        message = _generate_action_message("unclaim", status_code)
        
        return TaskActionResponse(
            status_code=status_code,
            message=message
        )
    except ToolError as e:
        return TaskActionResponse(
            status_code=500,
            message=str(e)
        )


def _build_elicitation_unavailable_response(form_properties_raw: List[Dict[str, Any]], action: str) -> TaskActionResponse:
    """
    Build a 501 response listing required form fields when elicitation is unavailable.
    
    This is returned when the MCP client does not support elicitation and no
    form_values were provided, enabling the client to retry with values.
    
    Args:
        form_properties_raw: Raw form property dictionaries from the task
        action: Action being performed (e.g. "complete")
        
    Returns:
        TaskActionResponse with status 501 and descriptive field listing
    """
    fields_description = _describe_writable_properties(form_properties_raw, action)
    detailed_message = (
        f"The MCP client does not support elicitation, which is required "
        f"for the '{action}' action. The task's state is unchanged.\n\n"
        f"To complete this task, the following form fields need to be provided:\n"
        f"{fields_description}\n\n"
        f"Please provide these values and retry the task completion using the form_values parameter."
    )
    return TaskActionResponse(status_code=501, message=detailed_message)


async def _resolve_user_values_for_complete(
    request: TaskActionRequest,
    ctx: Context,
    form_properties_raw: List[Dict[str, Any]],
    task_display_name: str
) -> Optional[TaskActionResponse]:
    """
    Resolve user-supplied form values for the 'complete' action.
    
    Tries three strategies in order:
    1. Use request.form_values if provided (skip elicitation)
    2. Attempt MCP elicitation if the client supports it
    3. Return a 501 response listing required fields
    
    Args:
        request: The task action request (may contain form_values)
        ctx: MCP context for elicitation
        form_properties_raw: Raw form properties from the task
        task_display_name: Task display name for elicitation message
        
    Returns:
        A TaskActionResponse (501 or 499) if the flow should abort early,
        or None if user values were resolved successfully (stored in
        request.form_values or obtained via elicitation — caller should
        check request.form_values).
        
    Design:
        This uses the "early return" pattern — a non-None return means
        the caller should stop and return the response immediately.
        When None is returned, the caller retrieves user values via
        the return channel described below.
        
        On success, the resolved values dict is attached to
        ``request.form_values`` so the caller can access it.
    """
    # Strategy 1: values provided directly
    if request.form_values:
        LOGGER.info(f"Using form_values provided in request ({len(request.form_values)} fields)")
        return None  # caller reads request.form_values
    
    # Strategy 2: attempt MCP elicitation
    if client_supports_elicitation(ctx):
        try:
            user_values = await _handle_elicitation(form_properties_raw, task_display_name, request.action, ctx)
        except ElicitationNotSupportedError:
            return _build_elicitation_unavailable_response(form_properties_raw, request.action)
        
        if user_values is None:
            LOGGER.info("Task completion cancelled due to elicitation rejection")
            return TaskActionResponse(status_code=499, message="Task completion cancelled by user")
        
        # Store resolved values on the request for the caller
        request.form_values = user_values
        return None
    
    # Strategy 3: no way to obtain values — return field listing
    LOGGER.info("Client does not support elicitation and no form_values provided; returning 501 with field descriptions")
    return _build_elicitation_unavailable_response(form_properties_raw, request.action)


async def _handle_claim_action(
    request: TaskActionRequest,
    task_data: Dict[str, Any],
    ctx: Context
) -> TaskActionResponse:
    """
    Handle the claim action flow.

    Task lifecycle and claim flow:

        ┌─────────── claim ──────────┐       ┌─────────── complete ──────────┐
        │                            │       │                               │
        │  UNCLAIMED ─────────────────┼──────▶ CLAIMED ──────────────────────┼──────▶ COMPLETED
        │                            │       │  │                            │
        └────────────────────────────┘       │  │ unclaim                    │
                                             │  ▼                            │
        Re-claim guard:                      │ UNCLAIMED                     │
        A task that is already CLAIMED       └──────────────────────────────┘
        cannot be claimed again → 409

    "claim" action:

        ┌──────────┐
        │ UNCLAIMED │
        └─────┬─────┘
              │
              ▼
        Already claimed? ──Yes──▶ 409 Conflict
              │
             No
              │
              ▼
        Auth OK? ──No──▶ 401 Unauthorized
              │
             Yes
              │
              ▼
        Extract form properties
              │
              ▼
        Claim API call ──Error──▶ 500 Server Error
              │
           200 OK
              │
              ▼
        ┌─────────┐
        │ CLAIMED  │
        └──────────┘

    Args:
        request: TaskActionRequest containing task_id and action="claim"
        task_data: Task data dictionary from API response
        ctx: MCP context for optional claim-preview elicitation

    Returns:
        TaskActionResponse with status and message
    """
    # Guard: task must not already be claimed
    if _is_task_already_claimed(task_data):
        return TaskActionResponse(status_code=409, message="Task is already claimed")

    # Get authenticated user ID
    try:
        user_id = await _get_authenticated_user_id()
    except ToolError as e:
        return TaskActionResponse(status_code=401, message=str(e))

    # Extract and validate form properties
    form_properties_raw = _extract_and_validate_form_properties(task_data)

    task_display_name = _get_task_display_name(task_data)
    if client_supports_elicitation(ctx):
        claim_confirmed = await _handle_claim_preview_elicitation(form_properties_raw, task_display_name, ctx)
        if not claim_confirmed:
            return TaskActionResponse(
                status_code=499,
                message="Task claim cancelled by user after reviewing the required completion information"
            )

    # Transform form properties
    form_properties = _transform_form_properties(form_properties_raw)

    # Perform the claim
    try:
        status_code = await _perform_claim_or_complete(request.task_id, "claim", user_id, form_properties)
        return TaskActionResponse(
            status_code=status_code,
            message=_generate_action_message("claim", status_code)
        )
    except ToolError as e:
        return TaskActionResponse(status_code=500, message=str(e))


async def _handle_complete_action(
    request: TaskActionRequest,
    ctx: Context,
    task_data: Dict[str, Any]
) -> TaskActionResponse:
    """
    Handle the complete action flow.

    Prerequisite: task should already be CLAIMED by the current user.
    The API call sends the assignee, so a task that is UNCLAIMED may
    be implicitly claimed + completed in one step (API-dependent).

    "complete" action:

        ┌──────────┐
        │  CLAIMED  │ (may be unclaimed; API may implicitly claim)
        └─────┬─────┘
              │
              ▼
        Auth OK? ──No──▶ 401 Unauthorized
              │
             Yes
              │
              ▼
        Extract form properties
              │
              ▼
        Resolve form values ──────────────────────────────────────────┐
              │                                                        │
              ├── form_values in request? ──Yes──▶ use them           │
              │                                                        │
              ├── Client supports elicitation?                         │
              │     ├── Yes ──▶ Elicit user input                      │
              │     │         ├── Declined/Cancelled ──▶ 499 Cancelled │
              │     │         └── Accepted ──▶ use elicited values     │
              │     └── No ──▶ 501 + field descriptions (retry hint)  │
              │                                                        │
              ◀────────────────────────────────────────────────────────┘
              │
              ▼
        Transform & merge user values into form properties
              │
              ▼
        Complete API call ──Error──▶ 500 Server Error
              │
           200 OK
              │
              ▼
        ┌────────────┐
        │  COMPLETED  │
        └─────────────┘

    Args:
        request: TaskActionRequest containing task_id and action="complete"
        ctx: MCP context for elicitation
        task_data: Task data dictionary from API response

    Returns:
        TaskActionResponse with status and message
    """
    # Get authenticated user ID
    try:
        user_id = await _get_authenticated_user_id()
    except ToolError as e:
        return TaskActionResponse(status_code=401, message=str(e))

    # Extract and validate form properties
    form_properties_raw = _extract_and_validate_form_properties(task_data)

    # Resolve user-supplied form values via three strategies:
    #   1) form_values already in request  2) MCP elicitation  3) return 501
    task_display_name = _get_task_display_name(task_data)
    early_response = await _resolve_user_values_for_complete(
        request, ctx, form_properties_raw, task_display_name
    )
    if early_response is not None:
        return early_response

    request.form_values = _restore_pending_rejection_action(request.task_id, request.form_values)

    validation_error = _validate_rejection_comment(request.task_id, request.form_values)
    if validation_error is not None:
        return validation_error

    # Transform form properties and apply user values
    form_properties = _transform_form_properties(form_properties_raw)
    if request.form_values:
        _prepare_form_properties_with_user_values(form_properties, request.form_values)

    # Perform the complete action
    try:
        status_code = await _perform_claim_or_complete(request.task_id, "complete", user_id, form_properties)
        _pop_pending_rejection_action(request.task_id)
        return TaskActionResponse(
            status_code=status_code,
            message=_generate_action_message("complete", status_code)
        )
    except ToolError as e:
        return TaskActionResponse(status_code=500, message=str(e))


task_action_description="""
    Perform an action on a workflow task: claim, complete, or unclaim.
    
    This tool allows you to:
    - Claim a task (assign it to yourself)
    - Complete a task (finish it) with required form property values collected via elicitation
    - Unclaim a task (release it if previously claimed)

    CRITICAL: Never assume, infer, or present available task actions to the user 
    without first calling this tool with action="complete" to retrieve the valid 
    actions for that specific task. Actions vary by task type and workflow state 
    and must always be read directly from the tool response before presenting 
    options to the user.
    
    CRITICAL SAFETY RULE FOR action="complete":
    Do not create, invent, infer, assume, summarize, paraphrase, default, auto-fill, or guess any form_values yourself.
    Only include form_values that satisfy at least one of these conditions:
    1. The user explicitly provided them in this conversation, or
    2. They are being restored automatically by the server from prior retry state.
    
    It is always allowed to call this tool for action="complete" without form_values to start elicitation.
    This is the default behavior unless the user has already explicitly provided some completion input.
    If the user explicitly provided partial completion input, include only that user-provided input and let elicitation
    collect the rest.
    
    NEVER choose approval, rejection, or any other workflow form action on behalf of the user.
    NEVER generate a justification comment on behalf of the user.
    If retry instructions say the server will restore a preserved action automatically, provide only the missing
    user-supplied field(s), such as comment, and do not add any other form values.
    
    Negative example for action="complete":
    - Wrong: The user did not provide approval/rejection or comment, and you call this tool with invented
      form_values such as {"action": "approve"} or {"action": "-reject", "comment": "Looks fine"}.
    - Correct: Call this tool without form_values to start elicitation, or include only the completion values the
      user explicitly provided and let elicitation collect the rest. If the server explicitly says it will restore a
      preserved action automatically, provide only the user-supplied missing field.
    
    For the complete action, the tool retrieves task details and collects required
    information through MCP elicitation. If the client does not support elicitation,
    the tool returns a 501 response listing the required form fields. You can then
    retry the call with the form_values parameter populated to complete the task.
    
    For claim action, the tool assigns the authenticated user to the task.
    
    For unclaim action, the tool simply releases the claimed task.
    
    Make sure to use a request json object for the parameters.
    """


# explicit context for MCP elicitation, no autocontext
async def _task_action(
    request: TaskActionRequest,
    ctx: Context
) -> TaskActionResponse:
    """
    Perform an action on a workflow task.

    Args:
        request: TaskActionRequest object containing task_id and action
        ctx: MCP context for elicitation (used for claim/complete actions)

    Returns:
        TaskActionResponse object containing status code and message
    """
    LOGGER.info(f"Performing action '{request.action}' on task with task_id: {request.task_id}")
    
    # Route to appropriate action handler
    if request.action == "unclaim":
        return await _handle_unclaim_action(request.task_id)

    # For claim and complete actions, retrieve task details first
    task_data = await _get_task_details(request.task_id)

    if request.action == "claim":
        return await _handle_claim_action(request, task_data, ctx)
    else:  # complete
        return await _handle_complete_action(request, ctx, task_data)


@service_registry.tool(
    name="perform_workflow_task_action",
    annotations={
        "title": "Perform Actions on Workflow Tasks: Claim, Complete, or Unclaim",
        "destructiveHint": True
    },
    description=task_action_description,
    tags={"workflow", "flowable", "tasks", "governance"},
    meta={"version": "1.0", "service": "perform_workflow_task_action"},
)
@auto_context
async def perform_workflow_task_action(
    task_id: str,
    action: str = "claim",
    form_values: Optional[Dict[str, str]] = None,
    ctx: Context = None
) -> TaskActionResponse:
    """Wrapper version of perform_workflow_task_action."""
    
    request = TaskActionRequest(task_id=task_id, action=action, form_values=form_values)
    
    # Use the real context if available, otherwise use minimal context
    if ctx is not None:
        return await _task_action(request, ctx)
    
    # Fallback for wxo version or when context is not available
    return await _task_action(request, MinimalContext())
