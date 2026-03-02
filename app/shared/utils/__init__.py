"""
Shared utilities for MCP services.

This module provides common utilities used across MCP services, including:

LLM Integration:
    - chat_llm_request: Request LLM text generation using MCP sampling
    - LLMResponse: Response wrapper for LLM-generated content

The LLM utilities use the Model Context Protocol (MCP) sampling capability
to request text generation from the client's LLM during tool execution.

Example:
    >>> from app.shared.utils import chat_llm_request
    >>> from app.shared.logging import auto_context
    >>>
    >>> @auto_context
    >>> async def my_tool(request, ctx=None):
    ...     response = await chat_llm_request("Generate a description", ctx=ctx)
    ...     description = response.content
    ...     return {"description": description}

For detailed LLM usage guide, see: readme_guides/LLM_SAMPLING_GUIDE.md
"""

from app.shared.utils.llm_utils import chat_llm_request, LLMResponse

__all__ = ["chat_llm_request", "LLMResponse"]
