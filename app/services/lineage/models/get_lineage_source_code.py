# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.


from pydantic import BaseModel, Field

from app.shared.models import BaseResponseModel


class GetLineageSourceCodeRequest(BaseModel):
    lineage_id: str = Field(
        ...,
        description="The lineage ID of the asset whose source code to retrieve "
        "(64-character hexadecimal string or UUID).",
    )


class SourcePosition(BaseModel):
    """A row/column position inside a source code text."""

    row: int = Field(..., description="Row (line) number, starting at 1")
    column: int = Field(..., description="Column number, starting at 1")


class SourceCodeSnippet(BaseModel):
    """A source code snippet attached to a lineage asset."""

    id: str = Field(..., description="Unique identifier of the snippet")
    source_code: str | None = Field(
        None, description="The source code text of the snippet (e.g. DDL of a view or function)"
    )
    source_code_id: str | None = Field(
        None, description="ID of the parent source code object this snippet belongs to"
    )
    is_full_source: bool = Field(
        False,
        description="True when the targeted snippet could not be read and `source_code` is the "
                    "full source of the parent object instead. In that case start_position and "
                    "end_position show which part belongs to this asset.",
    )
    start_position: SourcePosition | None = Field(
        None, description="Where the snippet starts inside the full source code, when known"
    )
    end_position: SourcePosition | None = Field(
        None, description="Where the snippet ends inside the full source code, when known"
    )


class GetLineageSourceCodeResponse(BaseResponseModel):
    lineage_id: str = Field(
        ..., description="The lineage ID that was queried"
    )
    asset_name: str | None = Field(None, description="Name of the lineage asset")
    asset_type: str | None = Field(None, description="Type of the lineage asset (e.g. Function, ColumnFlow)")
    snippets: list[SourceCodeSnippet] = Field(
        default_factory=list,
        description="Source code snippets attached to the asset. An asset can have several "
                    "(e.g. a function and the view that calls it).",
    )
    failed_snippet_ids: list[str] = Field(
        default_factory=list,
        description="IDs of snippets whose code could not be read because the lineage service failed.",
    )
    attributes: dict[str, str | None] = Field(
        default_factory=dict,
        description="All attributes (properties) of the asset by name, e.g. TRANSFORMATION_DESC, "
                    "TRANSFORMATION_DESC_OBJ, ORDER, CONNECTION.",
    )
    transformation_desc: str | None = Field(
        None,
        description="Transformation expression of the asset (e.g. for a ColumnFlow asset), "
                    "taken from its TRANSFORMATION_DESC attribute when present.",
    )
    source_code: str | None = Field(
        None,
        description="Full source code text. Only populated when the given ID is a snippet or "
                    "source code ID rather than a lineage asset ID.",
    )
