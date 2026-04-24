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

import re
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
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.llm_utils import client_supports_elicitation
from app.shared.utils.tool_helper_service import tool_helper_service

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context


class ElicitationNotSupportedError(Exception):
    """Raised when the MCP client does not support elicitation."""
    pass


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
            tool_name="task_action"
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


def _resolve_action_field_type(action_prop: Dict[str, Any]) -> type:
    """
    Resolve the Python type for the special 'action' field on complete actions.

    Args:
        action_prop: The form property dict whose id is "action"

    Returns:
        A Literal type if enum_values exist, otherwise str
    """
    enum_ids = _extract_enum_value_ids(action_prop)
    if enum_ids:
        LOGGER.info(f"Added 'action' field for complete action with dynamic choices from enum_values: {enum_ids}")
        return Literal[tuple(enum_ids)]
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
    a Literal type is returned; otherwise the raw type is mapped to a
    standard Python type.

    Args:
        prop: Form property dictionary

    Returns:
        Python type (Literal, str, int, float, bool, …)
    """
    prop_type = prop.get("type", "string")
    enum_ids = _extract_enum_value_ids(prop)

    if enum_ids and prop_type.lower() in ("enum", "string"):
        LOGGER.debug(f"Property '{prop.get('id')}' uses dynamic Literal from enum_values: {enum_ids}")
        return Literal[tuple(enum_ids)]

    return _map_property_type_to_python_type(prop_type)


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

    return (prop_id, (python_type, Field(default="", description=description)))


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

    return create_model('DynamicElicitationModel', **fields)


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
        return []
    
    ids = []
    for ev in enum_values:
        if isinstance(ev, dict) and "id" in ev:
            ids.append(str(ev["id"]))
        elif isinstance(ev, str):
            ids.append(ev)
    
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
    
    # For 'complete' action, include the special 'action' field first
    if action == "complete":
        _append_action_field_description(lines, form_properties)
    
    for prop in writable_props:
        prop_id = prop.get("id", "unknown")
        if prop_id == "action" and action == "complete":
            continue  # already handled above
        lines.append(_describe_single_property(prop))
    
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
    suffix = f" [Choices: {choices}]" if choices else ""
    lines.append(f"- action (string): Select the action to perform on the task{suffix}")


def _describe_single_property(prop: Dict[str, Any]) -> str:
    """
    Format a single form property as a human-readable description line.
    
    Args:
        prop: Form property dictionary with id, type, name/description, and optional enum_values
        
    Returns:
        Formatted description string like "- field_id (type): description [Choices: a, b]"
    """
    prop_id = prop.get("id", "unknown")
    prop_name = prop.get("name", prop_id)
    description = prop.get("description", prop_name)
    prop_type = prop.get("type", "string")
    
    choices = _format_choices(prop)
    suffix = f" [Choices: {choices}]" if choices else ""
    return f"- {prop_id} ({prop_type}): {description}{suffix}"


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


async def _handle_elicitation(
    form_properties: List[Dict[str, Any]],
    task_name: str,
    action: str,
    ctx: Context
) -> Optional[Dict[str, str]]:
    """
    Handle MCP elicitation to collect user input for form properties.
    
    Args:
        form_properties: List of raw form property dictionaries
        task_name: Name of the task for context in the elicitation message
        action: Action being performed (claim or complete)
        ctx: MCP context for elicitation
        
    Returns:
        Dictionary mapping property IDs to user-provided values, or None if elicitation failed
    """
    if ctx is None:
        LOGGER.warning("No context provided, skipping elicitation")
        return None
    
    # Log any non-dictionary elements for debugging
    non_dict_elements = [prop for prop in form_properties if not isinstance(prop, dict)]
    if non_dict_elements:
        LOGGER.warning(f"Found {len(non_dict_elements)} non-dictionary elements in form_properties during elicitation: {non_dict_elements[:5]}...")
    
    # Filter to writable properties, with type safety
    writable_props = [
        prop for prop in form_properties 
        if isinstance(prop, dict) and _prop_writable(prop)
    ]
    
    if not writable_props:
        LOGGER.info("No writable properties, skipping elicitation")
        return None
    
    # Create JSON Schema for elicitation
    schema = _create_elicitation_schema(writable_props, action)
    
    # Create elicitation message
    message = f"Please provide the required information to {action} task: {task_name}"
    
    try:
        # Build the JSON-RPC elicitation request
        
        LOGGER.info(f"Sending elicitation request for {len(writable_props)} properties for action: {action}")
        
        # Use ctx.elicit with the BaseModel class
        # The ctx.elicit method will handle the JSON-RPC format internally
        response = await ctx.elicit(
            message=message,
            response_type=schema
        )
        
        if response is not None and response.action == 'accept':
            LOGGER.info(f"Elicitation accepted, received: {response.data}")
            # response.data is a BaseModel instance, convert to dict
            # Convert BaseModel to dict, handling potential nested structures
            if isinstance(response.data, BaseModel):
                return response.data.model_dump()
            return response.data
        else:
            LOGGER.info("Elicitation declined or cancelled")
            return None
            
    except Exception as e:
        error_str = str(e)
        LOGGER.warning(f"Failed to call elicitation: {error_str}")
        
        # Detect errors indicating the client does not support elicitation
        # Common patterns: MCP error code -32042, "elicitation" in message, 
        # "not supported" or "capability" references
        if ("-32042" in error_str
                or "elicitation" in error_str.lower()
                or "not supported" in error_str.lower()):
            LOGGER.error(f"MCP client does not support elicitation: {error_str}")
            raise ElicitationNotSupportedError(
                f"The MCP client does not support elicitation, which is required "
                f"for the '{action}' action. The task's state is unchanged. "
                f"Error: {error_str}"
            )
        
        return None


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
            tool_name="task_action"
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
            tool_name="task_action"
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
            prop.value = str(user_values[prop.id])
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
    task_name: str
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
        task_name: Task name for elicitation message
        
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
            user_values = await _handle_elicitation(form_properties_raw, task_name, request.action, ctx)
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
    task_data: Dict[str, Any]
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
    task_name = task_data.get("metadata", {}).get("name", "Unknown Task")
    early_response = await _resolve_user_values_for_complete(
        request, ctx, form_properties_raw, task_name
    )
    if early_response is not None:
        return early_response

    # Transform form properties and apply user values
    form_properties = _transform_form_properties(form_properties_raw)
    if request.form_values:
        _prepare_form_properties_with_user_values(form_properties, request.form_values)

    # Perform the complete action
    try:
        status_code = await _perform_claim_or_complete(request.task_id, "complete", user_id, form_properties)
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
    
    For the complete action, the tool retrieves task details and collects required 
    information through MCP elicitation. If the client does not support elicitation,
    the tool returns a 501 response listing the required form fields. You can then
    retry the call with the form_values parameter populated to complete the task.
    
    For claim action, the tool assigns the authenticated user to the task.
    
    For unclaim action, the tool simply releases the claimed task.
    
    Make sure to use a request json object for the parameters.
    """


@service_registry.tool(
    name="task_action",
    description=task_action_description,
    tags={"workflow", "flowable", "tasks", "governance"},
    meta={"version": "1.0", "service": "task_action"},
)
# explicit context for MCP elicitation, no autocontext
async def task_action(
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
        return await _handle_claim_action(request, task_data)
    else:  # complete
        return await _handle_complete_action(request, ctx, task_data)


@service_registry.tool(
    name="task_action",
    description="Watsonx Orchestrator compatible wrapper for task_action. " + task_action_description,
    tags={"wxo", "workflow", "flowable", "tasks", "governance"},
    meta={"version": "1.0", "service": "task_action"},
)
@auto_context
async def wxo_task_action(
    task_id: str,
    action: str = "claim"
) -> TaskActionResponse:
    """Watsonx Orchestrator compatible version of task_action."""
    
    request = TaskActionRequest(task_id=task_id, action=action)
    
    # Create a minimal context for the main function
    class MinimalContext:
        def elicit(self, message, response_type):  # not async as stub
            # Skip elicitation for wxo version - synchronous mock
            LOGGER.info(f"Empty elicitation {message}, {response_type}")
            # Return a mock response that matches the expected async interface
            return type('MockResponse', (), {'action': 'decline', 'data': None})()
    
    return await task_action(request, MinimalContext())
