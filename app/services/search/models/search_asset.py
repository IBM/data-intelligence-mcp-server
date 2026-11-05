# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field  # noqa: I001 # Baseline
from app.shared.models import BaseResponseModel
from typing import Any, Optional, List  # noqa: UP035 # Baseline


class SearchAssetRequest(BaseModel):
    """Request model for searching assets."""

    search_prompt: str = Field(
        ...,
        description="The search prompt from the user about data assets potentially with additional searching details",
    )
    container_type: Optional[str] = Field(  # noqa: UP045 # Baseline
        default="catalog",
        description="The container type in which to search assets, defaults to catalog",
        examples=["catalog", "project"],
    )
    container_name: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Optional container name to resolve to ID and filter results",
    )


class SearchAssetResponse(BaseResponseModel):
    """Search assets response model"""

    id: str = Field(
        ...,
        description="Internal unique id of the asset. Do not show to the user unless explicitly requested.",
    )
    name: str = Field(
        ...,
        description="Name of the asset. Always display as a hyperlink using the url field.",
    )
    description: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Description of the asset. Always show this field; display '-' when empty.",
    )
    catalog_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Internal catalog identifier. Do not show to the user unless explicitly requested.",
    )
    catalog_name: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Catalog name in which the asset resides. Always show this as the workspace name.",
    )
    project_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Internal project identifier. Do not show to the user unless explicitly requested.",
    )
    project_name: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="Project name in which the asset resides. Always show this as the workspace name.",
    )
    url: str = Field(
        ...,
        description="URL of the asset. Use this to create a hyperlink on the asset name.",
    )
    additional_metadata: Optional[dict[str, Any]] = Field(  # noqa: UP045 # Baseline
        None,
        description="Additional metadata fields from the search index (e.g. modified_on, created_on, asset_type). These fields are NOT shown in the agentic UI table (which always renders a fixed set of columns). Only surface them in your text/table response when the user explicitly requests the data (e.g. 'show me assets updated last week' → include modified_on; 'list assets' alone → omit all additional_metadata keys).",
    )


class SearchAssetListResponse(BaseResponseModel):
    assets: List[SearchAssetResponse]  # noqa: UP006 # Baseline
    total_count: int
    search_prompt: str
    container_type: str = "catalog"
