# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel  # noqa: I001 # Baseline
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import Literal, List  # noqa: UP035 # Baseline


class SearchGovernanceArtifactRequest(BaseModel):
    rhs_type: Literal[
        "classification",
        "data_class",
        "glossary_term",
        "policy",
        "rule",
        "reference_data",
    ] = Field(
        description="Governance artifacts type name. Must be one of: 'classification', 'data_class', 'glossary_term'(another name is business term), 'policy', 'rule', or 'reference_data'."
    )
    query_value: str = Field(description="Search query string. Cannot be empty.")


class GovernanceArtifact(BaseModel):
    name: str = Field(description="The name of the governance artifact.")
    global_id: str = Field(description="The global ID of the governance artifact.")


class SearchGovernanceArtifactResponse(BaseResponseModel):
    count: int = Field(description="The number of governance artifacts found.")
    artifacts: List[GovernanceArtifact] = Field(  # noqa: UP006 # Baseline
        description="List of matching governance artifacts."
    )
    message: str = Field(description="Status message about the search results.")


# Made with Bob
