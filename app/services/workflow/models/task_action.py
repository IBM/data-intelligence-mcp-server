# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import re as _re
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Literal
from app.shared.models import BaseResponseModel


class FormProperty(BaseModel):
    """Simplified form property for task actions."""
    
    id: str = Field(..., description="Property identifier")
    value: str = Field(..., description="Property value as string")
    date_value: Optional[str] = Field(None, description="Date value placeholder (ISO format)")
    period_value: Optional[dict] = Field(None, description="Period value placeholder")
    long_value: Optional[int] = Field(None, description="Long value placeholder")
    list_value: Optional[List] = Field(None, description="List value placeholder")


class TaskActionRequest(BaseModel):
    """Request model for task_action."""
    
    task_id: str = Field(..., description="Unique identifier of the task")
    action: Literal["claim", "complete", "unclaim"] = Field(
        default="claim",
        description="Action to perform on the task: 'claim' to assign the task, 'complete' to finish it, or 'unclaim' to release it"
    )
    form_values: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Optional pre-filled form field values for the 'complete' action. "
            "Use this to supply values when elicitation is not supported or on retry "
            "after a 501 response. Keys must match form property IDs from the task."
        )
    )
    
    @field_validator('task_id')
    @classmethod
    def task_id_must_be_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('task_id cannot be empty')
        # Prevent path traversal in URL construction
        if _re.search(r'[/\\]|\.\.', v):
            raise ValueError('task_id contains invalid characters')
        return v


class TaskActionResponse(BaseResponseModel):
    """Response model for task_action."""
    
    status_code: int = Field(..., description="HTTP status code from the action")
    message: Optional[str] = Field(None, description="Status message")
    retry_metadata: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional machine-readable retry metadata for clients/LLMs"
    )