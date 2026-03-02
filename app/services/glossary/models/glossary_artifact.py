# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Models for glossary artifacts."""

from typing import Optional
from pydantic import BaseModel, Field


class GlossaryArtifact(BaseModel):
    id: str = Field(..., description="Unique identifier of the glossary artifact")
    name: str = Field(..., description="Display name of the glossary artifact")
    artifact_type: str = Field(
        ..., 
        description="Type of artifact (e.g., 'term', 'classification', 'data_class', 'policy', 'rule', 'category', 'reference_data_set')"
    )
    url: str = Field(..., description="URL to access the glossary artifact in the UI")


class ExplainGlossaryArtifactRequest(BaseModel):
    artifact_name: str = Field(
        ...,
        description="The name of the glossary artifact to look up. Can be a glossary term, classification, data class, reference data, policy, or rule."
    )


class GlossaryArtifactDescription(BaseModel):
    glossary_artifact: Optional[GlossaryArtifact] = Field(
        None,
        description="Details about the glossary artifact (id, name, type, url)"
    )
    description: str = Field(
        ...,
        description="Textual explanation of the artifact and its purpose"
    )
    ai_generated: bool = Field(
        False,
        description="Whether the description was AI-generated or came from metadata"
    )
    generation_prompt: Optional[str] = Field(
        None,
        description="Prompt for generating a description when one is not available. The calling model should use this to generate a proper description."
    )


class GetGlossaryArtifactsForAssetRequest(BaseModel):
    asset_id_or_name: str = Field(
        ...,
        description="UUID or name of the asset to retrieve glossary artifacts for"
    )
    container_id_or_name: str = Field(
        ...,
        description="UUID or name of the project or catalog containing the asset"
    )
    container_type: str = Field(
        ...,
        description="Type of container - either 'project' or 'catalog'"
    )