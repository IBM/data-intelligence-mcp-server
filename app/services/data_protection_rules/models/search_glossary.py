# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import Literal, List


class SearchGovernanceArtifactRequest(BaseModel):
    rhs_type: Literal["classification", "data_class", "glossary_term"] = Field(
        description="Governance artifacts type name. Must be one of: 'classification', 'data_class', or 'glossary_term'(another name is business term)."
    )
    query_value: str = Field(
        description="Search query string. Cannot be empty."
    )


class GovernanceArtifact(BaseModel):
    name: str = Field(description="The name of the governance artifact.")
    global_id: str = Field(description="The global ID of the governance artifact.")


class SearchGovernanceArtifactResponse(BaseResponseModel):
    count: int = Field(description="The number of governance artifacts found.")
    artifacts: List[GovernanceArtifact] = Field(
        description="List of matching governance artifacts."
    )
    message: str = Field(description="Status message about the search results.")

# Made with Bob
