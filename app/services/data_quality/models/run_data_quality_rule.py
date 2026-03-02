# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Optional, Any


class RunDataQualityRuleRequest(BaseModel):
    project_id_or_name: str = Field(
        ..., description="Project ID or project name in which the rule to executed."
    )
    data_quality_rule_id_or_name: str = Field(
    ...,
    description="ID or name of the data quality rule to run."
   )

class RunDataQualityRuleResponse(BaseResponseModel):
    data_quality_rule_id: str = Field(
        ..., description="ID of the data quality rule that was executed."
    )
    project_id: str = Field(
        ..., description="Project ID in which the rule was executed."
    )
    data_quality_rule_ui_url: str = Field(
        ..., description="UI URL to view the executed data quality rule."
    )
    data_quality_rule_name: Optional[str] = Field(
        None, description="Name of the data quality rule."
    )
