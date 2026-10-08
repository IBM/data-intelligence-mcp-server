"""
Shared utilities for MCP services.

LLM Integration:
    - LLMResponse: Response wrapper for LLM-generated content
    - client_supports_elicitation: Check if client supports MCP elicitation

Skill Loading:
    - load_skill_text: Load a skill's SKILL.md file by name
    - log_skill_injected: Log when a skill is injected into LLM context
    - BUSINESS_TERM_SKILL_TEXT: Cached text for the business-term-evaluation skill
    - DATA_CLASS_SKILL_TEXT: Cached text for the data-class-evaluation skill
"""

from app.shared.utils.llm_utils import (
    LLMResponse,
    client_supports_elicitation,
)
from app.shared.utils.skill_loader import (
    load_skill_text,
    log_skill_injected,
    BUSINESS_TERM_SKILL_TEXT,
    DATA_CLASS_SKILL_TEXT,
)

__all__ = [
    "LLMResponse",
    "client_supports_elicitation",
    "load_skill_text",
    "log_skill_injected",
    "BUSINESS_TERM_SKILL_TEXT",
    "DATA_CLASS_SKILL_TEXT",
]
