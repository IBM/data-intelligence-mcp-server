# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field


class CreateRuleRequest(BaseModel):
    name: str = Field(..., description="An example input parameter for create_rule.")

class CreateRuleResponse(BaseModel):
    message: str = Field(..., description="An example output message from create_rule.")
