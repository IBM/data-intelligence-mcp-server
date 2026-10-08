# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Models for the glossary import status service."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.shared.models import BaseResponseModel


class ImportStatusApiResponse(BaseModel):
    """Typed representation of the raw API response from the import status endpoint."""

    status: str = Field(..., description="Current status (SUCCEEDED, FAILED, IN_PROGRESS, etc.)")
    step_number: int = Field(..., description="Current step number in the import process")
    step_message: str = Field(..., description="Human-readable message describing the current step")
    total_steps: int = Field(..., description="Total number of steps in the import process")
    workflow_id: str | None = Field(None, description="Import workflow identifier")
    operations_count: Dict[str, Any] = Field(default_factory=dict, description="Per-artifact operation counts")
    children_statuses: List[Dict[str, Any]] = Field(default_factory=list, description="Child process statuses")
    messages: Dict[str, Any] = Field(default_factory=dict, description="Import log messages")


class ImportGlossaryStatusResult(BaseResponseModel):
    process_id: str = Field(..., description="Import process identifier")
    workflow_id: str | None = Field(None, description="Import workflow identifier")
    status: str = Field(..., description="Current status (SUCCEEDED, FAILED, IN_PROGRESS, etc.)")
    step_number: int | None = Field(None, description="Current step number in the import process")
    step_message: str | None = Field(None, description="Human-readable message describing the current step")
    total_steps: int | None = Field(None, description="Total number of steps in the import process")
    operations_by_type: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Per-artifact-type operation counts, e.g. {'glossary_term': {'created': 2, 'modified': 1}}",
    )
    warning_msgs: List[str] = Field(default=[], description="Warning messages on successful import")
    error_message: str | None = Field(None, description="Failure details when status is FAILED")
