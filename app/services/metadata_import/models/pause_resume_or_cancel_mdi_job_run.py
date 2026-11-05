# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Models for the unified MDI job operations tool (pause, resume, cancel)."""

from typing import Literal, Optional  # noqa: I001 # Baseline
from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel

from app.services.metadata_import.models.constants import (
    DESC_PROJECT_NAME,
    DESC_METADATA_IMPORT_NAME,
    DESC_ACTION,
    DESC_JOB_RUN_ID,
    DESC_METADATA_IMPORT_ID,
    DESC_METADATA_IMPORT_NAME_RESPONSE,
    DESC_JOB_ID,
    DESC_JOB_RUN_ID_RESPONSE,
    DESC_METADATA_IMPORT_JOB_RUN_UI_URL,
)


class PauseResumeOrCancelMdiJobRunRequest(BaseModel):
    """Request model for the unified MDI job operations tool."""

    project_name: str = Field(..., description=DESC_PROJECT_NAME)
    metadata_import_name: str = Field(..., description=DESC_METADATA_IMPORT_NAME)
    action: Literal["pause", "resume", "cancel"] = Field(..., description=DESC_ACTION)
    job_run_id: Optional[str] = Field(None, description=DESC_JOB_RUN_ID)  # noqa: UP045 # Baseline


class PauseResumeOrCancelMdiJobRunResponse(BaseResponseModel):
    """Response model for the unified MDI job operations tool."""

    message: str = Field(
        ...,
        description="A descriptive confirmation message about the operation performed.",
    )
    metadata_import_id: str = Field(..., description=DESC_METADATA_IMPORT_ID)
    metadata_import_name: str = Field(
        ..., description=DESC_METADATA_IMPORT_NAME_RESPONSE
    )
    job_id: str = Field(..., description=DESC_JOB_ID)
    job_run_id: str = Field(..., description=DESC_JOB_RUN_ID_RESPONSE)
    job_state: str = Field(
        ..., description="The current state of the job run after the operation."
    )
    metadata_import_job_run_ui_url: str = Field(
        ..., description=DESC_METADATA_IMPORT_JOB_RUN_UI_URL
    )


# Made with Bob
