# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
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

            # If wxo mode is enabled, only register tools with 'wxo' prefix
            # if wxo mode is disabled, skip tools with 'wxo' prefix
            if hasattr(settings, 'wxo'):
                if (settings.wxo and not tool.func.__name__.startswith("wxo")) or \
                   (not settings.wxo and tool.func.__name__.startswith("wxo")):
                    continue

            # Build kwargs and register tool
            kwargs = self._build_tool_kwargs(tool)
            mcp_instance.tool(**kwargs)(tool.func)
            self._registered_count += 1

    def get_registered_count(self):
        """Returns the number of tools that were actually registered."""
        return self._registered_count

# Global singleton instance for collecting tools
service_registry = ServiceRegistry()
