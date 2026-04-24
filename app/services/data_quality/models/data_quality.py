# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Dict, Optional


class DataQuality(BaseModel):
    """
    Data quality metrics for an asset.
    
    Uses a dictionary to store dimension scores, allowing dynamic handling of any
    data quality dimensions returned by the API without requiring model changes.
    """

    overall: str = Field(..., description="Overall quality score (percentage)")
    scores_by_dimension: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary of dimension names to their scores (percentages). "
                    "Common dimensions: consistency, validity, completeness, timeliness, accuracy"
    )
    report_url: str = Field(..., description="Link to detailed quality dashboard")

class DataQualityRule(BaseModel):
    data_quality_rule_id: str
    project_id: str
    data_quality_rule_ui_url: str
    data_quality_rule_name: Optional[str] = None
