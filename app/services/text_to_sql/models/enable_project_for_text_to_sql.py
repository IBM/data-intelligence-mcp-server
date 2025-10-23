# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field


class EnableProjectForTextToSqlRequest(BaseModel):
    project_id: str = Field(..., description="UUID of the project to onboard.")


class EnableProjectForTextToSqlResponse(BaseModel):
    message: str = Field(
        ...,
        description="Confirmation message indicating that the project has been enabled for Text To SQL.",
    )
