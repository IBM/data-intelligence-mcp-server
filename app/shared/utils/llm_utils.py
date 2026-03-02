# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Utilities for LLM interactions using MCP sampling.

This module provides a unified interface for requesting LLM text generation using
the Model Context Protocol (MCP) sampling capability.

Key Components:
    - client_supports_sampling: Check if client supports MCP sampling capability
    - chat_llm_request: Main function for LLM text generation via MCP sampling
    - LLMResponse: Response wrapper containing generated content

Example:
    >>> from app.shared.utils.llm_utils import client_supports_sampling, chat_llm_request
    >>> from app.shared.logging import auto_context
    >>>
    >>> @auto_context
    >>> async def my_tool(request, ctx=None):
    ...     if client_supports_sampling(ctx):
    ...         # Use LLM sampling
    ...         prompt = f"Generate description for: {request.name}"
    ...         response = await chat_llm_request(prompt, ctx=ctx)
    ...         return {"description": response.content}
    ...     else:
    ...         # Use metaprompting
    ...         return {"generation_prompt": prompt}
"""

from typing import Optional
from fastmcp import Context
from mcp.types import SamplingMessage, TextContent
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER

DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7


class LLMResponse:
    def __init__(self, content: str):
        self.content = content


def client_supports_sampling(ctx: Optional[Context]) -> bool:
    """
    Check if the connected MCP client supports sampling capability.
    
    This function examines the client's capabilities to determine if it supports
    LLM sampling via the MCP protocol. Sampling allows the server to request
    text generation from the client's LLM.
    
    Args:
        ctx: Optional MCP Context containing session and client information
        
    Returns:
        True if the client supports sampling, False otherwise
        
    Example:
        >>> from app.shared.logging import auto_context
        >>>
        >>> @auto_context
        >>> async def my_tool(request, ctx=None):
        ...     if client_supports_sampling(ctx):
        ...         # Use LLM sampling
        ...         response = await chat_llm_request(prompt, ctx=ctx)
        ...     else:
        ...         # Use metaprompting
        ...         return {"generation_prompt": prompt}
    """
    if not ctx or not ctx.request_context:
        LOGGER.debug("Context or request_context not available for sampling check")
        return False
    
    try:
        session = ctx.session
        client_params = session.client_params
        
        if not client_params or not client_params.capabilities:
            LOGGER.debug("Client parameters or capabilities not available")
            return False
        
        # Check if sampling capability is present and not None
        supports_sampling = client_params.capabilities.sampling is not None
        LOGGER.info(f"Client sampling support: {supports_sampling}")
        return supports_sampling
        
    except Exception as e:
        LOGGER.warning(f"Failed to check client sampling capability: {e}")
        return False


async def chat_llm_request(
    prompt: str,
    ctx: Optional[Context] = None,
) -> LLMResponse:
    """
    Request LLM text generation using MCP's sampling capability.
    
    This function uses the MCP protocol to request text generation from the client's LLM.
    The context must be provided for sampling to work.
    
    Args:
        prompt: The prompt to send to the LLM
        ctx: MCP Context (required for sampling)
        
    Returns:
        LLMResponse with the generated content
        
    Raises:
        ServiceError: When context is not provided or sampling fails
    """
    
    if not ctx:
        raise ServiceError("MCP context is required for LLM sampling")
    
    try:
        # Use the context's sample method to request LLM generation
        # Format messages according to MCP specification
        text_content = TextContent(type="text", text=prompt)
        message = SamplingMessage(role="user", content=text_content)
        
        result = await ctx.sample(
            messages=[message],
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
        )
        
        # Extract the generated text from the sampling result
        # FastMCP returns a SamplingResult - the result itself is the generated text
        if result and isinstance(result, str):
            generated_text = result.strip()
            if generated_text:
                LOGGER.info("Successfully generated content using MCP sampling")
                return LLMResponse(content=generated_text)
        # Handle case where result has text attribute
        elif result and hasattr(result, 'text') and result.text:
            generated_text = result.text.strip()
            if generated_text:
                LOGGER.info("Successfully generated content using MCP sampling")
                return LLMResponse(content=generated_text)
        
        LOGGER.warning("LLM sampling returned empty result")
        raise ServiceError("LLM sampling returned empty result")
        
    except Exception as e:
        LOGGER.error(f"MCP sampling failed: {e}")
        raise ServiceError(f"MCP sampling failed: {e}")