# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Models for listing glossary business terms.

This module contains request and response models for querying the glossary API to retrieve glossary business terms.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from app.shared.models import BaseResponseModel, field_validator
from app.services.workflow.models.artefact import Artefact, BusinessTerm


class ListBusinessTermsRequest(BaseModel):
    """Request model for listing glossary business terms."""

    search_term: str = Field(..., description="Search term for name or description of the business terms")
    draft: bool = Field(..., description="Data class in draft or published")
    max_results: int = Field(
        50,
        description="Maximum number of business terms to return",
        ge=1,
        le=100
    )
    format: str = Field(
        "table",
        description="Output format: 'table' for formatted markdown table, 'json' for raw data"
    )


class ListBusinessTermsResponse(BaseResponseModel):
    """Response model for listing glossary business terms."""

    business_terms: Optional[List[BusinessTerm]] = Field(
        None,
        description="List of glossary business terms (only when format='json')"
    )
    total_count: int = Field(..., description="Total number of business terms available")
    name_to_artifact_id_map: Optional[Dict[str, str]] = Field(
        None,
        description="Mapping of business term names to their artifact IDs (only when format='json')"
    )
    formatted_output: Optional[str] = Field(
        None,
        description="Formatted markdown table output when format='table'"
    )

