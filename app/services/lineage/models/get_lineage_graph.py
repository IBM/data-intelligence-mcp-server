# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Optional, Union
from pydantic import BaseModel, Field

from app.services.lineage.models.lineage_asset import LineageAsset


class GetLineageGraphRequest(BaseModel):
    lineage_ids: Union[str, List[str]] = Field(
        ...,
        description="The list of lineage identifiers. Example: ['75a06535eb329a6b69d9f2b448e24e5561a5ca0a96417307e73698b2d4fb0c87', '75a06535eb329a6b69d9f2b448e24e5561a5ca0a96417307e73698b2d4fb0c88']",
    )
    hop_up: str = Field(
        "3",
        description="""Number of upstream levels to include in the graph:
            - "1" shows immediate upstream connections only. Use if user uses word immidiate or ultimate.
            - "50" shows path between two assets or mentions word 'between'
            - "50" shows complete path to source
            - "50" if more than one asset is on the lineage_ids list
            - "0" if user mentions only word downstream but not upstream
            - Default is "3" for balanced view""",
    )
    hop_down: str = Field(
        "3",
        description="""Number of downstream levels to include in the graph:
            - "1" shows immediate downstream connections only. Use if user uses word immidiate or ultimate.
            - "50" shows complete path to target
            - "50" shows path between two assets or mentions word 'between'
            - "50" if more than one asset is on the lineage_ids list
            - "0" if user mentions only word upstream but not downstream
            - Default is "3" for balanced view""",
    )
    ultimate: Optional[str] = Field(
        None,
        description="""This optional field should get value:
            - If user mentions target the value should be target
            - If user mentions source the value should be source
            - If both are mentioned the value should be both
            - if user mentioned word between the value should ''""",
    )


class GetLineageGraphResponse(BaseModel):
    lineage_assets: List[LineageAsset] = Field(
        ..., description="List of all assets in the lineage graph"
    )
    edges_in_view: Optional[List[str]] = Field(
        ..., description="Connections between assets showing data flow in format: 'from edge: AssetA, to: AssetB, relation: RelationType'"
    )
    url: str = Field(
        ..., description="Direct link to visualize this lineage graph in the UI"
    )
