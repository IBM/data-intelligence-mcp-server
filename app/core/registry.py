# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import inspect
import re
import typing
from collections.abc import Callable
from typing import Any, List, NamedTuple
from functools import wraps
from app.core.settings import settings
from app.shared.logging.utils import LOGGER

# Tool name validation pattern: alphanumeric, underscore, hyphen, 1-64 chars
TOOL_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

def _clean_description(description: str) -> str:
    """
    Clean description by replacing newlines, tabs, and multiple consecutive spaces
    with a single space.
    
    Args:
        description: The description string to clean
        
    Returns:
        Cleaned description string
    """
    if not description:
        return description
    # Replace newlines, tabs, and multiple spaces with a single space
    cleaned = re.sub(r'\s+', ' ', description)
    # Strip leading/trailing whitespace
    return cleaned.strip()

# Experimental tool tags that should not be used in production environment
EXPERIMENTAL_TAGS= {"experimental"}

class RegisteredTool(NamedTuple):
    """Holds tool information prior to registration with the MCP server."""
    func: Callable
    name: str
    description: str
    input_model: Any
    output_model: Any
    tags: set[str] | None
    enabled: bool
    exclude_args: list[str] | None
    annotations: Any
    meta: dict[str, Any] | None

class RegisteredPrompt(NamedTuple):
    """Holds prompt information prior to registration with the MCP server."""
    func: Callable
    name: str
    description: str
    input_model: Any

class ServiceRegistry:
    def __init__(self):
        self._tools: list[RegisteredTool] = []
        self._registered_count = 0

    def _validate_tool_name(self, tool_name: str) -> None:
        """Validate that tool name matches required pattern."""
        if not TOOL_NAME_PATTERN.match(tool_name):
            raise ValueError(
                f"Invalid tool name '{tool_name}'. Tool names must match pattern "
                f"'^[a-zA-Z0-9_-]{{1,64}}$' (alphanumeric, underscore, hyphen, 1-64 chars). "
                f"Colons and other special characters are not allowed."
            )


    def _is_experimental(self, tags: set[str] | None) -> bool:
        """Check if tool has experimental tag """
        if not tags:
            return False
        return any(experimental_tag in tags for experimental_tag in EXPERIMENTAL_TAGS)

    def _infer_models(self, func: Callable) -> tuple[Any, Any]:
        """Infer input and output models from function signature."""
        sig = inspect.signature(func)
        params = list(sig.parameters.values())  
        input_model = params[0].annotation if params else None
        if len(params) > 1:
            LOGGER.info(f"Registering tool with context parameter: {str(func)}")
            input_model = [params[0].annotation, params[1].annotation]
        output_model = sig.return_annotation if sig.return_annotation is not inspect.Signature.empty else None
        return input_model, output_model

    def tool(
        self,
        name: str | None = None,
        description: str | None = None,
        tags: set[str] | None = None,
        enabled: bool = True,
        exclude_args: list[str] | None = None,
        annotations: Any = None,
        meta: dict[str, Any] | None = None
    ) -> Callable:
        """A decorator to collect a function as a tool to be registered later."""
        def decorator(func: Callable) -> Callable:
            tool_name = name if name is not None else func.__name__
            self._validate_tool_name(tool_name)
            
            """Do not load the tool if it's experimental and the experimental setting is not enabled"""
            if settings.use_experimental == False and self._is_experimental(tags):
                return func

            input_model, output_model = self._infer_models(func)
            self._tools.append(
                RegisteredTool(
                    func=func,
                    name=tool_name,
                    description=_clean_description(description or ""),
                    input_model=input_model,
                    output_model=output_model,
                    tags=tags,
                    enabled=enabled,
                    exclude_args=exclude_args,
                    annotations=annotations,
                    meta=meta
                )
            )
            return func
        return decorator

    def _build_tool_kwargs(self, tool: RegisteredTool) -> dict[str, Any]:
        """Build kwargs dictionary for mcp.tool decorator."""
        kwargs = {
            "name": tool.name,
            "description": tool.description
        }

        if tool.tags is not None:
            kwargs["tags"] = tool.tags
        if tool.exclude_args is not None:
            kwargs["exclude_args"] = tool.exclude_args
        if tool.annotations is not None:
            kwargs["annotations"] = tool.annotations
        if tool.meta is not None:
            kwargs["meta"] = tool.meta

        return kwargs

    def _handle_generic_type(self, return_type, error_message: str, remediation_steps: str = ""):
        """Handle generic types like List[Model], Union[Model1, Model2], Dict, etc."""
        origin = typing.get_origin(return_type)
        
        # Handle Union types by trying the first type in the union
        if origin is typing.Union  or " | " in str(return_type):
            args = typing.get_args(return_type)
            type_to_use = self._get_union_type(args)
            LOGGER.info(f"Union type detected, attempting to create error response using type: {type_to_use}")
            # Recursively call _create_error_response to handle the selected Union type
            # This will NOT call _handle_generic_type again unless the selected type is also generic
            return self._create_error_response(type_to_use, error_message, remediation_steps)
        
        # Handle List types
        if origin is list:
            args = typing.get_args(return_type)
            if args and len(args) > 0:
                try:
                    error_instance = self._create_error_response(args[0], error_message, remediation_steps)
                    return [error_instance]
                except Exception as e:
                    LOGGER.debug(f"Failed to create List error response: {e}")
                    # Return error message string as fallback
                    return error_message
            # List without type parameters - return error message string
            LOGGER.debug("List type has no args, returning error message string")
            return error_message
        
        # For other generic types (Dict, etc.) that we can't handle, return the error message string
        # This allows the function to gracefully handle typing.Dict, typing.List without parameters, etc.
        LOGGER.debug(f"Unable to handle generic type {return_type}, returning error message string")
        return error_message

    def _get_union_type(self, args):
        """
        Get the type to use out of union response types.
        """
        if not args or len(args) == 0:
            # Empty Union args - return None
            LOGGER.debug("Union type has no args, returning None")
            return None
            
        # Filter out NoneType for Optional types
        non_none_args = [arg for arg in args if arg is not type(None)]
        if not non_none_args:
            # All args were NoneType - return None
            LOGGER.debug("Union type has only NoneType args, returning None")
            return None
        
        # Use the second non-None type if available, otherwise use the first
        type_to_use = non_none_args[1] if len(non_none_args) > 1 else non_none_args[0]
        return type_to_use

    def _try_simple_strategies(self, return_type, error_message: str, remediation_steps: str = ""):
        """Try simple constructor strategies for creating error response."""
        strategies = [
            lambda: return_type(error=error_message, success=False, remediation_steps=remediation_steps),
            lambda: return_type(error=error_message, remediation_steps=remediation_steps),
            lambda: return_type(error=error_message, success=False),
            lambda: return_type(error=error_message),
            lambda: return_type(error_message),
        ]
        
        for strategy in strategies:
            try:
                return strategy()
            except Exception as e:
                LOGGER.debug(f"Strategy failed: {e}")
        return None

    def _try_default_with_setattr(self, return_type, error_message: str, remediation_steps: str = ""):
        """Try creating default instance and setting error attributes."""
        try:
            response = return_type()
            if hasattr(response, 'error'):
                response.error = error_message
            if hasattr(response, 'success'):
                response.success = False
            if hasattr(response, 'remediation_steps') and remediation_steps:
                response.remediation_steps = remediation_steps
            return response
        except Exception as e:
            LOGGER.debug(f"Failed to create default response: {e}")
        return None

    def _get_default_value_for_field(self, field_type, field_info, error_message: str = ""):
        """Get appropriate default value for a field based on its type."""
        if hasattr(field_type, '__origin__'):
            return self._handle_generic_field_type(field_type, field_info)
        
        return self._handle_basic_field_type(field_type, field_info, error_message)

    def _handle_generic_field_type(self, field_type, field_info):
        """Handle generic field types like Optional, List, Dict."""
        origin = field_type.__origin__
        args = getattr(field_type, '__args__', ())
        
        if origin is typing.Union and type(None) in args:
            return None
        elif origin is list:
            return []
        elif origin is dict:
            return {}
        
        return None if not field_info.is_required() else ""

    def _handle_basic_field_type(self, field_type, field_info, error_message: str = ""):
        """Handle basic field types like str, int, bool, Enum, etc."""
        from enum import Enum
        
        type_defaults = {
            str: "",
            int: 0,
            float: 0.0,
            bool: False,
            list: [],
            dict: {}
        }
        
        if field_type in type_defaults:
            return type_defaults[field_type]
        
        # Handle Enum types by returning the first enum value
        if isinstance(field_type, type) and issubclass(field_type, Enum):
            try:
                # Get the first enum value
                first_value = next(iter(field_type))
                LOGGER.debug(f"Using first enum value '{first_value.value}' for field type {field_type}")
                return first_value
            except (StopIteration, AttributeError) as e:
                LOGGER.debug(f"Failed to get first enum value for {field_type}: {e}")
        
        if hasattr(field_type, 'model_fields'):
            return self._create_nested_model_default(field_type, field_info, error_message)
        
        return None if not field_info.is_required() else ""

    def _create_nested_model_default(self, field_type, field_info, error_message: str = ""):
        """Create default value for nested Pydantic models."""
        try:
            return self._create_error_response(field_type, error_message)
        except Exception:
            try:
                return field_type()
            except Exception:
                return None if not field_info.is_required() else {}

    def _try_field_inspection(self, return_type, error_message: str, remediation_steps: str = ""):
        """Try creating error response by inspecting Pydantic model fields."""
        if not hasattr(return_type, 'model_fields'):
            return None
        
        try:
            kwargs = {'error': error_message, 'success': False}
            
            # Add remediation_steps if provided and field exists
            if remediation_steps and 'remediation_steps' in return_type.model_fields:
                kwargs['remediation_steps'] = remediation_steps

            for field_name, field_info in return_type.model_fields.items():
                if field_name not in kwargs and field_info.is_required():
                    kwargs[field_name] = self._get_default_value_for_field(
                        field_info.annotation, field_info, error_message
                    )
            
            return return_type(**kwargs)
        except Exception as e:
            LOGGER.error(f"Failed to create error response with field inspection: {e}")
            raise

    def _create_error_response(self, return_type, error_message: str, remediation_steps: str = ""):
        """
        Attempt to create an error response object with the given error message.
        Tries multiple strategies to accommodate different response model structures.
        
        Args:
            return_type: The return type annotation of the function
            error_message: The error message to include in the response
            remediation_steps: Optional guidance on how to handle the error
            
        Returns:
            An instance of return_type with error information, or raises if unable to create
        """
        if hasattr(typing, 'get_origin') and typing.get_origin(return_type) is not None:
            return self._handle_generic_type(return_type, error_message, remediation_steps)
        
        result = self._try_simple_strategies(return_type, error_message, remediation_steps)
        if result is not None:
            return result
        
        result = self._try_default_with_setattr(return_type, error_message, remediation_steps)
        if result is not None:
            return result
        
        return self._try_field_inspection(return_type, error_message, remediation_steps)

    def _create_error_wrapper(self, func: Callable, tool_name: str) -> Callable:
        """
        Create an error wrapper that catches exceptions and returns
        structured error responses.
        
        Args:
            func: The original tool function
            tool_name: Name of the tool (for logging)
            
        Returns:
            Wrapped function that handles errors gracefully
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Log the error with full stack trace
                import traceback
                error_message = str(e)
                stack_trace = traceback.format_exc()
                LOGGER.error(f"Tool '{tool_name}' failed with error: {error_message}")
                LOGGER.error(f"Stack trace:\n{stack_trace}")
                
                # Extract remediation_steps from exception if available
                remediation_steps = getattr(e, 'remediation_steps', "")

                # Get the return type annotation
                sig = inspect.signature(func)
                return_type = sig.return_annotation
                
                if not return_type or return_type == inspect.Signature.empty:
                    LOGGER.error(f"No return type annotation for {tool_name}, re-raising error")
                    raise e
                
                # Try to create error response
                try:
                    error_response = self._create_error_response(return_type, error_message, remediation_steps)
                    LOGGER.info(f"Successfully created error response for tool '{tool_name}'")
                    return error_response
                except Exception as create_error:
                    # If all strategies fail, re-raise original error
                    LOGGER.error(f"Unable to create error response for {tool_name}: {create_error}")
                    import traceback
                    LOGGER.error(f"Error response creation traceback:\n{traceback.format_exc()}")
                    raise e
        
        return wrapper

    def register_all(self, mcp_instance):
        """Registers all collected tools with the FastMCP instance at startup."""
        self._registered_count = 0

        for tool in self._tools:
            # Only register enabled tools
            if not tool.enabled:
                continue

            # Wrap all tools with error handler
            LOGGER.info(f"Wrapping tool '{tool.name}' with error handler")
            func_to_register = self._create_error_wrapper(tool.func, tool.name)

            # Build kwargs and register tool
            kwargs = self._build_tool_kwargs(tool)

            mcp_instance.tool(**kwargs)(func_to_register)
            self._registered_count += 1

    def get_registered_count(self):
        """Returns the number of tools that were actually registered."""
        return self._registered_count

class PromptRegistry:
    """Registry for collecting and registering prompts with the MCP server."""
    
    def __init__(self):
        self._prompts: list[RegisteredPrompt] = []
        self._registered_count = 0

    def prompt(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> Callable:
        """A decorator to collect a function as a prompt to be registered later."""
        def decorator(func: Callable) -> Callable:
            sig = inspect.signature(func)
            params = list(sig.parameters.values())

            # Infer Input model from type hints (first parameter)
            input_model = params[0].annotation if params else None

            # Use function name if name not provided
            prompt_name = name if name is not None else func.__name__

            self._prompts.append(
                RegisteredPrompt(
                    func=func,
                    name=prompt_name,
                    description=description or func.__doc__ or "",
                    input_model=input_model,
                )
            )
            return func
        return decorator

    def register_all(self, mcp_instance):
        """Registers all collected prompts with the FastMCP instance at startup."""
        self._registered_count = 0
        for prompt in self._prompts:
            kwargs = {
                "name": prompt.name,
            }
            if prompt.description:
                # FastMCP uses docstring for description, but we can pass it if supported
                pass
            mcp_instance.prompt(**kwargs)(prompt.func)
            self._registered_count += 1

    def get_registered_count(self):
        """Returns the number of prompts that were actually registered."""
        return self._registered_count

# Global singleton instance for collecting tools
service_registry = ServiceRegistry()
# Global singleton instance for collecting prompts
prompt_registry = PromptRegistry()
