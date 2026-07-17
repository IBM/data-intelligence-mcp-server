# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from typing import Literal, Optional
from app.shared.models import BaseResponseModel


class EnableContainerForTextToSqlRequest(BaseModel):
    container_id_or_name: str = Field(..., description="Name or UUID of the container to onboard.")
    container_type: Literal["catalog", "project"] = Field("project", description="The container type of the container to onboard, project by default.")
    project_id_or_name: Optional[str] = Field(None, description="Name or UUID of the project to create the onboarding job in, only required when onboarding non-project container.")


class EnableContainerForTextToSqlResponse(BaseResponseModel):
    message: str = Field(
        ...,
        description="A message indicating the success of the operation with UI link to check onboarding job.",
    )
