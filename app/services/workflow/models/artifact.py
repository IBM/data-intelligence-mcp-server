# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Unified Artifact model for data classes and business terms.

This module provides a single model to represent both data classes and business terms
in the glossary, using "artifact" as the generic term.
"""

from pydantic import BaseModel, Field
from typing import Optional


class Artifact(BaseModel):
    """Model representing a glossary artifact (data class or business term)."""

    name: str = Field(..., description="Artifact name")
    description: Optional[str] = Field(None, description="Artifact description")
    artifact_id: Optional[str] = Field(None, description="Associated artifact ID")
    state: Optional[str] = Field(None, description="Artifact state")
    modified_by: Optional[str] = Field(None, description="Modifier")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    workflow_id: Optional[str] = Field(None, description="Workflow ID for artifacts in draft")
    artifact_type: Optional[str] = Field(None, description="Type of artifact: 'data_class' or 'glossary_term'")

class BusinessTerm(Artifact):
    """Model representing a glossary business term (alias for Artifact)."""
    pass

class DataClass(Artifact):
    """Model representing a glossary data class (alias for Artifact)."""
    pass
