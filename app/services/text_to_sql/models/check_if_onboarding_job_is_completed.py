# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from typing import Literal, Optional
from app.shared.models import BaseResponseModel


class CheckIfOnboardingJobIsCompletedRequest(BaseModel):
    container_id_or_name: str = Field(..., description="Name or UUID of the container to onboard.")
    container_type: Literal["catalog", "project"] = Field("project", description="The container type of the container to onboard, project by default.")
    project_id_or_name: Optional[str] = Field(None, description="Name or UUID of the project to create the onboarding job in, only required when onboarding non-project container.")

class CheckIfOnboardingJobIsCompletedResponse(BaseResponseModel):
    state: str = Field(
        ..., description="A string indicating the state which the job is in."
    )
