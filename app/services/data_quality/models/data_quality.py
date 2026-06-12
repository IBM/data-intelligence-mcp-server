# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Dict, Optional


class SlaAssessmentSummary(BaseModel):
    """Summary of SLA assessments for an asset."""
    
    matching_data_quality_slas: int = Field(..., description="Number of data quality SLAs currently monitoring this asset (based on latest assessments)")
    total_data_quality_sla_violations: int = Field(..., description="Total number of data quality SLA violations across all latest assessments")
    last_assessment_time: Optional[str] = Field(None, description="Timestamp of the most recent assessment (ISO 8601 format)")


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
    sla_assessment_summary: Optional[SlaAssessmentSummary] = Field(
        None, description="Summary of SLA assessments for this asset"
    )

class DataQualityRule(BaseModel):
    data_quality_rule_id: str
    project_id: str
    data_quality_rule_ui_url: str
    data_quality_rule_name: Optional[str] = None
