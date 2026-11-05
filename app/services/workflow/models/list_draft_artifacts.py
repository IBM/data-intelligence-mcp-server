# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.


"""Models for listing draft workflow glossary artifacts."""

from typing import Literal, Optional  # noqa: I001 # Baseline

from pydantic import BaseModel, Field

from app.shared.models import BaseResponseModel
from app.services.workflow.models.get_artifact_details import ArtifactType

DraftArtifactType = Literal["glossary_term", "data_class", "all"]


class DraftArtifactOverview(BaseModel):
    """Overview data for a draft business term or data class."""

    name: str = Field(..., description="Artifact name")
    artifact_type: ArtifactType = Field(..., description="Artifact type")
    artifact_id: str = Field(..., description="Artifact ID")
    version_id: Optional[str] = Field(None, description="Draft version ID")  # noqa: UP045 # Baseline
    state: Optional[str] = Field(None, description="Artifact state")  # noqa: UP045 # Baseline
    workflow_id: Optional[str] = Field(None, description="Workflow ID")  # noqa: UP045 # Baseline
    workflow_state: Optional[str] = Field(None, description="Workflow state")  # noqa: UP045 # Baseline
    created_at: Optional[str] = Field(None, description="Creation timestamp")  # noqa: UP045 # Baseline
    modified_at: Optional[str] = Field(None, description="Last modification timestamp")  # noqa: UP045 # Baseline
    modified_by: Optional[str] = Field(None, description="Last modifier")  # noqa: UP045 # Baseline
    url: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="Formatted URL to view artifact in the UI"
    )


class ListDraftArtifactsRequest(BaseModel):
    """Request model for listing draft glossary artifacts."""

    artifact_type: DraftArtifactType = Field(
        "all",
        description="Artifact type to list: 'glossary_term', 'data_class', or 'all'",
    )
    max_results: int = Field(
        50, description="Maximum number of draft artifacts to return", ge=1, le=200
    )
    format: str = Field(
        "table",
        description="Output format: 'table' for formatted output, 'json' for structured data",
    )


class ListDraftArtifactsResponse(BaseResponseModel):
    """Response model for listing draft glossary artifacts."""

    artifacts: Optional[list[DraftArtifactOverview]] = Field(  # noqa: UP045 # Baseline
        None, description="Draft artifact overviews"
    )
    total_count: int = Field(
        ..., description="Total number of draft artifacts returned"
    )
    formatted_output: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="Formatted table output when format='table'"
    )
