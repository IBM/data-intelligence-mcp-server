# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class CheckIfOnboardingJobIsCompletedRequest(BaseModel):
    project_id_or_name: str = Field(
        ..., description="ID or name of the project that is being onboarded."
    )


class CheckIfOnboardingJobIsCompletedResponse(BaseResponseModel):
    state: str = Field(
        ..., description="A string indicating the state which the job is in."
    )
