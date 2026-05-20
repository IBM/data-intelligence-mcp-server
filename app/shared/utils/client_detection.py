# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
MCP Client Detection Utilities

This module provides utilities for detecting MCP client types,
particularly for identifying clients that do not support rich text formatting.
"""

from fastmcp.server.context import Context
from app.shared.logging import LOGGER


def supports_rich_text_format(ctx: Context) -> bool:
    """
    Check if the current MCP client supports rich text formatting.
    
    This function examines the client initialization parameters to determine
    if the connected client supports rich text formatting (e.g. markdown tables).
    This is useful for client-specific formatting, as some clients may not handle
    markdown tables well and prefer JSON format.

    So far only Claude clients are known not to support rich text formatting
    
    Args:
        ctx: MCP Context object
        
    Returns:
        True if client support rich text formatting, False otherwise
        
    Example:
        @service_registry.tool(name="my_tool")
        async def my_tool(request: MyRequest, ctx: Context) -> str:
            if supports_rich_text_format(ctx):
                return format_as_markdown_table(data)
            else:
                return format_as_json(data)
    """

    # Handle None context (e.g. from wrapper functions where FastMCP context injection failed)
    if ctx is None:
        return True
    
    # Assume unknown clients support RTF
    if not ctx.request_context or not ctx.request_context.session:
        return True
    
    client_params = ctx.request_context.session.client_params
    if not client_params or not client_params.clientInfo:
        return True
    
    client_name = client_params.clientInfo.name
    result = "claude" not in client_name.casefold()
    
    # Log the client detection for debugging
    LOGGER.info(f"Client detected: {client_name} (supports_rich_text_format={result})")
    
    return result


def get_client_info(ctx: Context) -> dict[str, str | None]:
    """
    Get comprehensive client information.
    
    Extracts all available information about the connected MCP client
    including name, version, and protocol version.
    
    Args:
        ctx: MCP Context object
        
    Returns:
        Dictionary with client name, version, and protocol version.
        All values are None if information is not available.
        
    Example:
        client_info = get_client_info(ctx)
        LOGGER.info(f"Client: {client_info['name']} v{client_info['version']}")
    """
    if not ctx.request_context or not ctx.request_context.session:
        return {"name": None, "version": None, "protocol": None}
    
    client_params = ctx.request_context.session.client_params
    if not client_params:
        return {"name": None, "version": None, "protocol": None}
    
    client_info = client_params.clientInfo
    
    result = {
        "name": client_info.name if client_info else None,
        "version": client_info.version if client_info else None,
        "protocol": client_params.protocolVersion
    }
    
    LOGGER.info(f"Client info: {result}")
    
    return result
