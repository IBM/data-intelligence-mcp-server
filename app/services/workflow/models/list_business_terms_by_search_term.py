# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Models for listing glossary business terms.

This module contains request and response models for querying the glossary API to retrieve glossary business terms.
"""

from pydantic import BaseModel, Field, model_validator  # noqa: I001 # Baseline
from typing import List, Dict, Optional  # noqa: UP035 # Baseline

from app.shared.models import BaseResponseModel, field_validator  # noqa: F401 # Baseline
from app.services.workflow.models.artifact import Artifact, BusinessTerm  # noqa: F401 # Baseline


class ListBusinessTermsRequest(BaseModel):
    """Request model for listing glossary business terms."""

    search_term: str = Field(
        ..., description="Search term for name or description of the business terms"
    )
    draft: bool = Field(..., description="Business term in draft or published")
    max_results: Optional[int] = Field(  # noqa: UP045 # Baseline
        None,
        description="[Deprecated: use page_size] Maximum number of business terms to return",
        ge=1,
        le=100,
    )
    page_size: int = Field(
        10,
        description="Number of business terms to return per page (1-50)",
        ge=1,
        le=50,
    )
    page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Opaque pagination cursor token from a previous response",
    )
    format: str = Field(
        "table",
        description="Output format: 'table' for formatted markdown table, 'json' for raw data",
    )

    @model_validator(mode="after")
    def _compat_max_results(self) -> "ListBusinessTermsRequest":
        """Backward compatibility: max_results overrides page_size when supplied."""
        if self.max_results is not None:
            self.page_size = self.max_results
        return self


class ListBusinessTermsResponse(BaseResponseModel):
    """Response model for listing glossary business terms."""

    business_terms: Optional[List[BusinessTerm]] = Field(  # noqa: UP006, UP045 # Baseline
        None, description="List of glossary business terms (only when format='json')"
    )
    total_count: int = Field(
        ..., description="Total number of business terms available"
    )
    name_to_artifact_id_map: Optional[Dict[str, str]] = Field(  # noqa: UP006, UP045 # Baseline
        None,
        description="Mapping of business term names to their artifact IDs (only when format='json')",
    )
    formatted_output: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="Formatted markdown table output when format='table'"
    )
    next_page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Opaque token to fetch the next page of results",
    )
    prev_page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Opaque token to fetch the previous page of results",
    )
    has_more: bool = Field(
        False,
        description="Whether more items exist beyond this page",
    )
    semantic_summary: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Human-readable summary of the business terms and current page view",
    )
