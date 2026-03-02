# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Union, Literal, List

class SearchDataProtectionRuleRequest(BaseModel):
    data_protection_rule_search_query: Union[Literal["*"], str] = Field(
        description='The search query to search for data protection rules. If the user wants to search for data protection rules with a specific name or description, this is the name to search for. If user wants to search for all data protection rules, this value should be "*".'
    )

class DataProtectionRule(BaseModel):
    name: str
    description: str
    modified_on: str
    url: str

class SearchDataProtectionRuleResponse(BaseResponseModel):
    count: int = Field(description="The number of data protection rules found.")
    data_protection_rules: List[DataProtectionRule]
