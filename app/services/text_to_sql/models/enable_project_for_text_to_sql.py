# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel


class EnableProjectForTextToSqlRequest(BaseModel):
    project_id_or_name: str = Field(
        ..., description="Id or name of the project to onboard."
    )


class EnableProjectForTextToSqlResponse(BaseResponseModel):
    message: str = Field(
        ...,
        description="A message indicating the success of the operation with UI link to check onboarding job.",
    )
