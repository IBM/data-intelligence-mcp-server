# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Utilities for LLM interactions.

Key Components:
    - client_supports_elicitation: Check if client supports MCP elicitation capability
    - LLMResponse: Response wrapper containing generated content
"""

from typing import Optional  # noqa: I001 # Baseline
from fastmcp import Context
from app.shared.logging import LOGGER


class LLMResponse:
    def __init__(self, content: str):  # noqa: ANN204 # Baseline
        self.content = content


def client_supports_elicitation(ctx: Optional[Context]) -> bool:  # noqa: PLR0911, UP045 # Baseline
    """
    Check if the MCP client supports elicitation capability.

    Supports both the modern sessionless protocol (2026-07-28+, guard/InputRequiredResult
    pattern) and the legacy stateful protocol (ctx.elicit()).

    For the modern protocol the check returns True whenever the client advertises
    elicitation capability — no session_id is required because the guard pattern
    is stateless.  For the legacy protocol the server must be stateful (session_id
    present) in addition to the client advertising elicitation support.

    Args:
        ctx: Optional MCP Context containing session and client information

    Returns:
        True if elicitation is available (either protocol era), False otherwise

    Example:
        >>> from app.shared.logging import auto_context
        >>>
        >>> @auto_context
        >>> async def my_tool(request, ctx=None):
        ...     if client_supports_elicitation(ctx):
        ...         response = await ctx.elicit(message="...", response_type=MyModel)
    """
    if not ctx:
        return False

    try:
        # Check client capabilities for elicitation support
        session = ctx.session
        if session is None:
            return False
        client_params = session.client_params
        if client_params is None or client_params.capabilities is None:
            return False
        if client_params.capabilities.elicitation is None:
            return False

        # Modern protocol (2026-07-28+): guard pattern works without session state
        if hasattr(ctx, "_is_modern_protocol") and ctx._is_modern_protocol():
            LOGGER.debug(
                "Modern protocol detected: elicitation via InputRequiredResult guard pattern"
            )
            return True

        # Legacy protocol: requires stateful server (session_id must be present)
        if not hasattr(ctx, "session_id") or ctx.session_id is None:
            LOGGER.debug(
                "FastMCP session_id not available or None so MCP server is likely stateless"
            )
            return False

        return True
    except Exception:
        # Any issue accessing capabilities means we can't confirm support
        return False
