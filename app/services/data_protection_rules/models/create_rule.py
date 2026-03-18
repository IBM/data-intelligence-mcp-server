# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class CreateRuleRequest(BaseModel):
    """Request model for creating a data protection rule from natural language"""
    rule_json: str = Field(
        ...,
        description="JSON string converted from natural language description of the data protection rule to create"
    )
    preview_only: bool = Field(
        default=True,
        description="If true, only show preview; if false, create the rule. DEFAULT IS TRUE - always preview first!"
    )

# ============================================================================
# Common Response Model
# ============================================================================

class CreateRuleResponse(BaseResponseModel):
    """Response model for rule creation."""
    success: bool
    message: str
    rule_id: str | None = None
    url: str | None = None
    error: str | None = None
    preview_json: dict | None = None
