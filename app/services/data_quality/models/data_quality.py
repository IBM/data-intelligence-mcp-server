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
