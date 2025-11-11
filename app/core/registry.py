# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import inspect
from collections.abc import Callable
from typing import Any, NamedTuple

from app.core.settings import settings


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

class ServiceRegistry:
    def __init__(self):
        self._tools: list[RegisteredTool] = []
        self._registered_count = 0

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
            # Filter during collection phase based on wxo setting
            # This prevents duplicate tool names from being collected
            if hasattr(settings, 'wxo'):
                func_name = func.__name__
                is_wxo_func = func_name.startswith('wxo')
                
                # Skip collection if:
                # - wxo mode is enabled but function doesn't start with 'wxo'
                # - wxo mode is disabled but function starts with 'wxo'
                if (settings.wxo and not is_wxo_func) or (not settings.wxo and is_wxo_func):
                    return func
            
            sig = inspect.signature(func)
            params = list(sig.parameters.values())

            # Infer Input/Output models from type hints
            input_model = params[0].annotation if params else None
            output_model = sig.return_annotation if sig.return_annotation is not inspect.Signature.empty else None

            # Use function name if name not provided
            tool_name = name if name is not None else func.__name__

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

    def register_all(self, mcp_instance):
        """Registers all collected tools with the FastMCP instance at startup."""
        self._registered_count = 0

        for tool in self._tools:
            # Only register enabled tools
            if not tool.enabled:
                continue

            # Note: wxo filtering now happens during collection phase in the decorator
            # so all tools in self._tools are already filtered appropriately

            # Build kwargs and register tool
            kwargs = self._build_tool_kwargs(tool)
            mcp_instance.tool(**kwargs)(tool.func)
            self._registered_count += 1

    def get_registered_count(self):
        """Returns the number of tools that were actually registered."""
        return self._registered_count

# Global singleton instance for collecting tools
service_registry = ServiceRegistry()
