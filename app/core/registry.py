# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import inspect
import re
from collections.abc import Callable
from typing import Any, NamedTuple
from functools import wraps
from app.core.settings import settings
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.utils import LOGGER

# Tool name validation pattern: alphanumeric, underscore, hyphen, 1-64 chars
TOOL_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

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

    def _is_wxo_function(self, func: Callable) -> bool:
        """Check if function is a WXO function based on naming convention."""
        return func.__name__.startswith('wxo')
    
    def _should_skip_wxo_filtering(self, func: Callable) -> bool:
        """Check if function should be skipped based on WXO filtering rules."""
        if not hasattr(settings, 'wxo'):
            return False
        is_wxo_func = self._is_wxo_function(func)
        # Skip if wxo mode enabled but not wxo function, or vice versa
        return (settings.wxo and not is_wxo_func) or (not settings.wxo and is_wxo_func)

    def _infer_models(self, func: Callable) -> tuple[Any, Any]:
        """Infer input and output models from function signature."""
        sig = inspect.signature(func)
        params = list(sig.parameters.values())  
        input_model = params[0].annotation if params else None
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
            if self._should_skip_wxo_filtering(func):
                return func

            input_model, output_model = self._infer_models(func)
            self._tools.append(
                RegisteredTool(
                    func=func,
                    name=tool_name,
                    description=description or "",
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

    def _create_error_response(self, return_type, error_message: str):
        """
        Attempt to create an error response object with the given error message.
        Tries multiple strategies to accommodate different response model structures.
        
        Args:
            return_type: The return type annotation of the function
            error_message: The error message to include in the response
            
        Returns:
            An instance of return_type with error information, or raises if unable to create
        """
        # Strategy 1: Try with both error and success fields
        try:
            return return_type(error=error_message, success=False)
        except Exception as e1:
            LOGGER.debug(f"Failed to create error response with error+success: {e1}")
        
        # Strategy 2: Try with just error field
        try:
            return return_type(error=error_message)
        except Exception as e2:
            LOGGER.debug(f"Failed to create error response with just error: {e2}")
        
        # Strategy 3: Create with defaults and set fields if they exist
        try:
            response = return_type()
            if hasattr(response, 'error'):
                response.error = error_message
            if hasattr(response, 'success'):
                response.success = False
            return response
        except Exception as e3:
            LOGGER.error(f"Failed to create default response: {e3}")
            raise

    def _create_wxo_error_wrapper(self, func: Callable, tool_name: str) -> Callable:
        """
        Create an error wrapper for wxo tools that catches exceptions and returns
        structured error responses that wxo can understand.
        
        Args:
            func: The original tool function
            tool_name: Name of the tool (for logging)
            
        Returns:
            Wrapped function that handles errors gracefully for wxo
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
                LOGGER.error(f"WXO tool '{tool_name}' failed with error: {error_message}")
                LOGGER.error(f"Stack trace:\n{stack_trace}")
                
                # Get the return type annotation
                sig = inspect.signature(func)
                return_type = sig.return_annotation
                
                if not return_type or return_type == inspect.Signature.empty:
                    LOGGER.error(f"No return type annotation for {tool_name}, re-raising error")
                    raise e
                
                # Try to create error response
                try:
                    return self._create_error_response(return_type, error_message)
                except Exception:
                    # If all strategies fail, re-raise original error
                    LOGGER.error(f"Unable to create error response for {tool_name}")
                    raise e
        
        return wrapper

    def register_all(self, mcp_instance):
        """Registers all collected tools with the FastMCP instance at startup."""
        self._registered_count = 0

        for tool in self._tools:
            # Only register enabled tools
            if not tool.enabled:
                continue

            # Note: wxo filtering now happens during collection phase in the decorator
            # so all tools in self._tools are already filtered appropriately

            # Wrap wxo tools with error handler
            func_to_register = tool.func
            if self._is_wxo_function(tool.func):
                LOGGER.info(f"Wrapping WXO tool '{tool.name}' with error handler")
                func_to_register = self._create_wxo_error_wrapper(tool.func, tool.name)

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
