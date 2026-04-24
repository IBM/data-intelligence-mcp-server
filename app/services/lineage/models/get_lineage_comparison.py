# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Optional, Union
from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel


class LineageRequestBodyPart(BaseModel):
    """
    Nested lineage configuration containing initial asset IDs for graph comparison.
    This corresponds to the Java LineageRequestBodyPart class.
    """
    
    initial_asset_ids: List[str] = Field(
        ...,
        description="""List of initial asset IDs for lineage graph comparison.
        These are the root assets from which the lineage graph was originally generated.""",
        min_length=1,
    )


class GetLineageComparisonRequest(BaseModel):
    """
    Request for comparing lineage between different historical versions.
    
    This model aligns with the Java CompareLineageRequest class, allowing tracking
    of changes in lineage over time, identifying new, modified, or deleted assets and edges.
    """
    
    compared_lineage_assets: Union[str, List[str]] = Field(
        ...,
        description="""The list of asset IDs of assets to be compared.
        For graphs, this should contain all asset IDs returned by lineage_get_lineage_graph.
        For single asset comparison, this contains the asset ID(s) to compare.""",
    )
    
    lineage: Optional[LineageRequestBodyPart] = Field(
        None,
        description="""Lineage configuration containing initial asset IDs.
        Required when comparing lineage graphs. Should be None when comparing single assets.
        Contains the root asset ID(s) used in the original lineage_get_lineage_graph call.""",
    )
    
    base_version: str = Field(
        ...,
        description="""Base version datetime in ISO-8601 format specifying the earlier lineage version to compare.
        This is the starting version of the comparison. Supports various ISO-8601 formats:
        - Full datetime: "2025-11-12T10:00:00Z"
        - Year only: "2025Z"
        - Month: "2025-03Z"
        - Week: "2025-W13Z"
        If an asset is "added" in the comparison, it means it didn't exist in the "base" version
        and appeared in the "compared" one. Usually, the "base" version is the older one and the
        "compared" one is newer. If the base version is newer than the compared version, the result
        operations will seem inverted, e.g. "added" assets in the response were actually present in
        the older ("compared") version and removed in the later ("base") version.""",
    )
    
    compared_version: str = Field(
        ...,
        description="""Compared version datetime in ISO-8601 format specifying the later lineage version to compare.
        This is the target version of the comparison. Supports various ISO-8601 formats:
        - Full datetime: "2025-11-12T12:00:00Z"
        - Year only: "2026Z"
        - Month: "2025-12Z"
        - Week: "2025-W52Z"
        If an asset is "added" in the comparison, it means it didn't exist in the "base" version
        and appeared in the "compared" one. Usually, the "base" version is the older one and the
        "compared" one is newer. If the base version is newer than the compared version, the result
        operations will seem inverted, e.g. "added" assets in the response were actually present in
        the older ("compared") version and removed in the later ("base") version.""",
    )

class LineageComparisonAsset(BaseModel):
    """Lineage asset comparison result"""

    id: str = Field(..., description="Unique id of the asset")
    name: str = Field(..., description="Name of the asset")
    changes: List[str] = Field(
        default_factory=list,
        description="""Set of change statuses: added, removed, descendant_added, descendant_removed,
        source_code_snippet_added, source_code_snippet_removed, source_code_snippet_changed.
        Empty list indicates no changes."""
    )
    descendants_added: int = Field(
        0,
        description="Number of descendant assets added in the compared version"
    )
    descendants_removed: int = Field(
        0,
        description="Number of descendant assets removed in the compared version"
    )


class LineageComparisonEdge(BaseModel):
    """Lineage edge comparison result"""

    source: str = Field(..., description="ID of the source asset")
    target: str = Field(..., description="ID of the target asset")
    type: str = Field(..., description="Type of the edge (e.g., direct, indirect)")
    changes: List[str] = Field(
        default_factory=list,
        description="""Set of change statuses: added, removed, descendant_added, descendant_removed,
        edge_type_changed. Empty list indicates no changes."""
    )


class GetLineageComparisonResponse(BaseResponseModel):
    """Response containing lineage comparison results between two versions"""

    lineage_assets: List[LineageComparisonAsset] = Field(
        ...,
        description="List of asset comparison results between lineage versions"
    )
    lineage_edges: List[LineageComparisonEdge] = Field(
        ...,
        description="List of edge comparison results between lineage versions"
    )
