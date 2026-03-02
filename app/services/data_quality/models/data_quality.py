# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Optional


class DataQuality(BaseModel):
    """Data quality metrics for an asset."""

    overall: str = Field(..., description="Overall quality score (percentage)")
    consistency: Optional[str] = Field(
        None, description="Consistency score (percentage)"
    )
    validity: Optional[str] = Field(None, description="Validity score (percentage)")
    completeness: Optional[str] = Field(
        None, description="Completeness score (percentage)"
    )
    report_url: str = Field(..., description="Link to detailed quality dashboard")

class DataQualityRule(BaseModel):
    data_quality_rule_id: str
    project_id: str
    data_quality_rule_ui_url: str
    data_quality_rule_name: Optional[str] = None
