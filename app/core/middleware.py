# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

# Enhanced validation error handling middleware with meaningful error messages.

import json
import logging
from typing import Any, NoReturn

from mcp import MCPError
from mcp.types import INVALID_PARAMS
from pydantic import ValidationError as PydanticValidationError

from fastmcp.exceptions import ValidationError as FastMCPValidationError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

import mcp.types as mcpType
from fastmcp.server.dependencies import get_http_headers
from app.shared.logging.utils import LOGGER
from app.core.settings import settings

# Tool groups that can be toggled via the x-tool-groups request header.
# All groups are globally disabled at server startup; only the groups
# listed in the header are enabled for the connecting session.
KNOWN_TOOL_GROUPS = {
    "metadata_management_and_governance",
    "data_product",
    "data_quality",
    "lineage",
    "generative_ai",
}

# Groups enabled by default when no explicit x-tool-groups header / TOOL_GROUPS env var
# is supplied.  Clients can opt out by explicitly listing the groups they want
# (omitting a default group removes it) or by setting the env var to a specific list.
DEFAULT_ENABLED_TOOL_GROUPS = {
    "metadata_management_and_governance",
}


class SessionInitMiddleware(Middleware):
    """Enables/disables tool groups per session based on the x-tool-groups header.

    When a client connects it may send:
        x-tool-groups: data_product,workflow

    Only the groups listed in that header are enabled for the session.
    Groups that are absent from the header remain disabled (the global
    server-level disable applied in create_server() stays in effect).
    """

    @staticmethod
    def _parse_raw(raw: str) -> set[str]:
        """Parse a tool-groups value into a set of lowercase stripped tokens.

        Accepts two formats:
        - Comma-separated: ``data_product,lineage``
        - JSON array:      ``["data_product","lineage"]``
        """
        stripped = raw.strip()
        if stripped.startswith("["):
            try:
                items = json.loads(stripped)
                if isinstance(items, list):
                    return {str(group).strip().lower() for group in items if str(group).strip()}
            except json.JSONDecodeError:
                pass  # fall through to comma-split below
        return {group.strip().lower() for group in stripped.split(",") if group.strip()}

    def _resolve_enabled_groups(self) -> set[str]:
        """Resolve which tool groups should be enabled for the current request.

        For stdio transport, reads from the TOOL_GROUPS env var (set at startup).
        For HTTP transport, reads from the x-tool-groups request header.
        Falls back to DEFAULT_ENABLED_TOOL_GROUPS when nothing is supplied.
        """
        if settings.server_transport == "stdio":
            raw_value = settings.tool_groups
        else:
            headers = get_http_headers()
            raw_value = headers.get("x-tool-groups", "")

        if not raw_value.strip():
            return DEFAULT_ENABLED_TOOL_GROUPS.copy()
        return self._parse_raw(raw_value) & KNOWN_TOOL_GROUPS

    async def on_initialize(
        self,
        context: MiddlewareContext[mcpType.InitializeRequest],
        call_next: CallNext[mcpType.InitializeRequest, mcpType.InitializeResult | None],
    ) -> mcpType.InitializeResult | None:
        # For stdio, tool groups are fixed at startup so on_initialize is the
        # right place to enable them (no per-request header exists).
        # For HTTP, the session_id is not yet stable at initialize time (the
        # server-assigned mcp-session-id is sent back in the initialize response
        # and is unknown server-side until after the response is written).
        # Enabling groups here via ctx.enable_components stores the rules under
        # a temporary UUID that is never matched by subsequent requests, so the
        # groups appear disabled on the first real tool call.
        # HTTP groups are therefore handled in on_call_tool / on_list_tools
        # where the session_id is stable (sent by the client in the header).
        if settings.server_transport == "stdio":
            enabled_groups = self._resolve_enabled_groups()
            LOGGER.info(f"[stdio] Enabling tool groups: {enabled_groups or 'none'}")
            ctx = context.fastmcp_context
            if ctx is not None:
                for group in enabled_groups:
                    await ctx.enable_components(tags={group})

        return await call_next(context)

    async def _enable_groups_for_http_request(self, context: MiddlewareContext) -> None:
        """Enable tool groups for an HTTP request using the stable session context.

        Called from on_call_tool and on_list_tools where the mcp-session-id header
        is present and the session_id is resolved correctly.

        IMPORTANT: enable_components() fires a ToolListChangedNotification on every
        call, which upgrades the HTTP response to a persistent SSE stream. Calling it
        on every request causes open connections to accumulate and triggers uvicorn's
        limit_concurrency 503 responses. We guard with a session-state flag so the
        enable runs exactly once per session.
        """
        if settings.server_transport == "stdio":
            return  # handled once in on_initialize for stdio

        ctx = context.fastmcp_context
        if ctx is None:
            return

        # Guard: only enable groups once per session. Subsequent requests on the
        # same session re-use the rules already stored in session state.
        already_initialised = await ctx.get_state("_tool_groups_initialised")
        if already_initialised:
            return

        enabled_groups = self._resolve_enabled_groups()
        LOGGER.debug(f"[http] Enabling tool groups for session (first request): {enabled_groups or 'none'}")
        for group in enabled_groups:
            await ctx.enable_components(tags={group})

        await ctx.set_state("_tool_groups_initialised", True)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcpType.CallToolRequest],
        call_next: CallNext[mcpType.CallToolRequest, mcpType.CallToolResult],
    ) -> mcpType.CallToolResult:
        await self._enable_groups_for_http_request(context)
        return await call_next(context)

    async def on_list_tools(
        self,
        context: MiddlewareContext[mcpType.ListToolsRequest],
        call_next: CallNext[mcpType.ListToolsRequest, mcpType.ListToolsResult],
    ) -> mcpType.ListToolsResult:
        await self._enable_groups_for_http_request(context)
        LOGGER.debug("Enabling tool groups for session during listing the tools")
        return await call_next(context)
        
    
class ValidationErrorHandlingMiddleware(Middleware):
    """Middleware that provides meaningful error messages for parameter validation errors.

    This middleware catches validation errors and transforms them into user-friendly
    error messages that explain what went wrong and how to fix it. This is
    especially useful when clients send parameters that don't match the expected
    schema (e.g., not wrapped in the correct request structure).

    Example:
        ```python
        from fastmcp import FastMCP
        from fastmcp_validation_error_handler import ValidationErrorHandlingMiddleware

        mcp = FastMCP("MyServer", strict_input_validation=True)
        mcp.add_middleware(ValidationErrorHandlingMiddleware())
        ```

    The middleware enhances errors for:
    - Missing required parameters
    - Wrong parameter types
    - Invalid parameter values
    - Extra parameters not in schema
    - Malformed parameter structures
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ):
        """Initialize validation error handling middleware.

        Args:
            logger: Logger instance for error logging. If None, uses
                'fastmcp.validation_errors'
        """
        self.logger = logger or logging.getLogger("fastmcp.validation_errors")

    async def on_message(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Handle validation errors for all messages."""
        try:
            return await call_next(context)
        except PydanticValidationError as e:
            # Pydantic validation error from MCP SDK or FastMCP
            return self._handle_pydantic_validation_error(e, context)
        except FastMCPValidationError as e:
            # FastMCP wraps PydanticValidationError as __cause__; unwrap it when
            # available so we can extract structured field-level details.
            cause = e.__cause__
            if isinstance(cause, PydanticValidationError):
                return self._handle_pydantic_validation_error(cause, context)
            return self._handle_fastmcp_validation_error(e, context)

    def _handle_pydantic_validation_error(
        self, error: PydanticValidationError, context: MiddlewareContext
    ) -> NoReturn:
        """Handle Pydantic validation errors with meaningful messages."""
        error_details = error.errors()

        # Build error messages with actual validation details
        error_parts = ["Parameter validation failed:"]
        for error_detail in error_details:
            field = " -> ".join(str(loc) for loc in error_detail.get("loc", []))
            msg = error_detail.get("msg", "Unknown error")
            error_parts.append(f"  - {field}: {msg}")

        suggestions = []
        for error_detail in error_details:
            loc = error_detail.get("loc", [])
            error_type = error_detail.get("type", "")
            
            # Handle missing request argument
            if error_type == 'missing_argument' and loc and loc[0] == 'request':
                suggestions.append("Wrap tool call arguments in a request object")
            
            # Handle type errors
            elif error_type in ['int_parsing', 'float_parsing', 'bool_parsing', 
                                'string_too_short', 'string_too_long']:
                suggestions.append(f"Check the type of parameter '{' -> '.join(str(elem) for elem in loc)}'")
            
            # Handle format errors
            elif error_type in ['email', 'url', 'json']:
                suggestions.append(f"Ensure parameter '{' -> '.join(str(elem) for elem in loc)}' has correct format")
            
            # Handle value range errors
            elif error_type in ['greater_than', 'less_than', 'multiple_of']:
                suggestions.append(f"Ensure parameter '{' -> '.join(str(elem) for elem in loc)}' is within valid range")
            
            # Handle enum errors
            elif error_type == 'literal_error':
                suggestions.append(f"Parameter '{' -> '.join(str(elem) for elem in loc)}' must be one of the allowed values")

        # Add suggestions if available
        if suggestions:
            error_parts.append("\nSuggestions:")
            error_parts.extend(f"  - {s}" for s in suggestions)

        # Log the error
        self.logger.warning(
            f"Parameter validation error in {context.method or 'unknown'}: "
            f"{error_details}"
        )

        # Raise MCP error with code INVALID_PARAMS (Invalid Params)
        message = "\n".join(error_parts)
        raise MCPError(INVALID_PARAMS, message) from error

    def _handle_fastmcp_validation_error(
        self, error: FastMCPValidationError, context: MiddlewareContext
    ) -> NoReturn:
        """Handle FastMCP validation errors that have no structured Pydantic details."""
        message = str(error) or "Parameter validation failed"
        self.logger.warning(
            f"Parameter validation error in {context.method or 'unknown'}: "
            f"{message}"
        )
        raise MCPError(INVALID_PARAMS, message) from error
