# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Models for listing glossary business terms by category.

This module contains request and response models for querying the glossary API
to retrieve business terms scoped to a specific category.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from app.shared.models import BaseResponseModel
from app.services.workflow.models.artifact import BusinessTerm


class ListBusinessTermsByCategoryRequest(BaseModel):
    """Request model for listing glossary business terms by category."""

    primary_category: str = Field(
        ...,
        description="Human-readable name of the primary category to filter business terms by."
    )
    description: Optional[str] = Field(
        None,
        description=(
            "Optional description text provided by the user. When supplied, the top "
            "similar terms (up to top_n) are returned ranked by BM25 similarity against "
            "this description. When omitted, all terms in the category are returned."
        )
    )
    top_n: int = Field(
        5,
        description="Maximum number of similar terms to return when description is provided",
        ge=1,
        le=50
    )
    max_results: int = Field(
        200,
        description="Maximum number of business terms to fetch from the category before ranking",
        ge=1,
        le=200
    )
    format: str = Field(
        "table",
        description="Output format: 'table' for formatted markdown table, 'json' for raw data"
    )


class ListBusinessTermsByCategoryResponse(BaseResponseModel):
    """Response model for listing glossary business terms by category."""

    business_terms: Optional[List[BusinessTerm]] = Field(
        None,
        description="List of glossary business terms belonging to the category"
    )
    total_count: int = Field(..., description="Total number of business terms found in the category")
    category_name: str = Field(..., description="Resolved category name used for the filter")
    category_id: str = Field(..., description="Resolved category UUID used as parent_category_id")
    name_to_artifact_id_map: Optional[Dict[str, str]] = Field(
        None,
        description="Mapping of business term names to their artifact IDs"
    )
    formatted_output: Optional[str] = Field(
        None,
        description="Formatted markdown table output when format='table'"
    )
