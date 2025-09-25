# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
MCP-specific middleware for automatic ID generation and context management.

This module provides decorators to automatically generate transaction IDs,
trace IDs, and other context information for MCP tool calls.
"""

import uuid
import time
import functools
from typing import Optional, Callable

from .filter import (
    set_transaction_id,
    set_trace_id
)
from .utils import LOGGER

def generate_short_uuid() -> str:
    """Generate a short UUID for trace IDs."""
    return str(uuid.uuid4())[:8]

def with_request_context(
    transaction_id: Optional[str] = None,
    trace_id: Optional[str] = None
):
    """
    Decorator to automatically set up request context for async MCP tool calls.
    
    Args:
        transaction_id: Optional transaction ID (generated if not provided)
        trace_id: Optional trace ID (generated if not provided)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def context_wrapper(*args, **kwargs):
            
            # Generate IDs
            final_transaction_id = transaction_id or str(uuid.uuid4())
            final_trace_id = trace_id or generate_short_uuid()
            
            # Set context variables
            set_transaction_id(final_transaction_id)
            set_trace_id(final_trace_id)
            
            # Log the start of the tool call
            LOGGER.info(f"Tool call started - {func.__name__}")
            
            start_time = time.perf_counter()
            
            try:
                # Call the original function
                result = await func(*args, **kwargs)
                
                execution_time = time.perf_counter() - start_time
                LOGGER.info(f"Tool call completed - {func.__name__} in {execution_time:.3f}s")
                
                return result
                
            except Exception as e:
                execution_time = time.perf_counter() - start_time
                LOGGER.error(f"Tool call failed - {func.__name__} in {execution_time:.3f}s, error={str(e)}")
                raise

        return context_wrapper
    
    return decorator


def auto_context(func: Callable) -> Callable:
    """
    Simple decorator that automatically generates all context IDs.
    This MCP server supports both http and stdio transport modes.
    So we can't depend on mcp middleware for just http. We need to cater to
    both http and stdio modes. For MCP client calls, entry point is the tool.
    Add this decorator around the tool methods so that the context IDs are 
    automatically added

    Usage example:
        @service_registry.tool( ... )
        @auto_context
        async def search_asset(request: SearchAssetRequest, ctx=None) -> List[SearchAssetResponse]:
    """
    return with_request_context()(func)
