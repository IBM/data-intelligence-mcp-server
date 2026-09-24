# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import Any, Optional

from app.services.glossary.constants import ContainerType
from app.services.search.models.search_asset import SearchAssetResponse
from app.services.text_to_query_search.constants import CONTAINER_TYPE_PROJECT_AND_CATALOG


class Container(BaseModel):
    """Internal model representing a resolved container (project or catalog) with its ID."""

    type: ContainerType
    id: str
    name: str


class TextToQuerySearchAssetRequest(BaseModel):
    """Request model for searching assets."""

    search_prompt: str = Field(
        ...,
        description="The search prompt from the user about data potentially with additional searching details",
    )
    container_type: Optional[str] = Field(
        default=CONTAINER_TYPE_PROJECT_AND_CATALOG,
        description="The container type in which to search assets, defaults to project_and_catalog",
        examples=["catalog", "project", CONTAINER_TYPE_PROJECT_AND_CATALOG],
    )
    container_name: Optional[str] = Field(
        default=None,
        description="Name of the container in which the asset resides. It can be either project or catalog. It allows the tool for searching assets in a specific container",
    )
    artifact_types: Optional[list[str]] = Field(
        default_factory=lambda: ["data_asset"],
        description="The type of artifacts to search for, defaults to data_asset",
    )
    names_mapping: Optional[list[dict]] = Field(
        default=None,
        description="List of named entities with their types to be resolved to IDs. Each dict should contain 'name' and 'type' keys. Supported types: 'connection', 'metadata_import'. Example: [{'name': 'testConnName', 'type': 'connection'}, {'name': 'testMDIName', 'type': 'metadata_import'}]",
    )


class GlobalSearchAssetResponse(BaseResponseModel):
    """Search assets response model"""

    id: str = Field(..., description="Internal unique id of the asset. Do not show to the user unless explicitly requested.")
    name: str = Field(..., description="Name of the asset. Always display as a hyperlink using the url field.")
    description: Optional[str] = Field(None, description="Description of the asset. Always show this field; display '-' when empty.")
    asset_type: Optional[str] = Field(
        None,
        description="Type of the asset (e.g., data_asset, connection, glossary_term, category, etc.)",
    )
    catalog_id: Optional[str] = Field(
        None, description="Internal catalog identifier. Do not show to the user unless explicitly requested."
    )
    catalog_name: Optional[str] = Field(
        None, description="Catalog name in which the asset resides. Always show this as the workspace name."
    )
    project_id: Optional[str] = Field(
        None, description="Internal project identifier. Do not show to the user unless explicitly requested."
    )
    project_name: Optional[str] = Field(
        None, description="Project name in which the asset resides. Always show this as the workspace name."
    )
    url: str = Field(..., description="URL of the asset. Use this to create a hyperlink on the asset name.")
    source_data: Optional[dict] = Field(
        None,
        description="Additional data from specific _source fields requested in the query (excludes full metadata and entity objects)"
    )
    additional_metadata: Optional[dict[str, Any]] = Field(None, description="Additional metadata fields from the search index (e.g. modified_on, created_on, asset_type). These fields are NOT shown in the agentic UI table (which always renders a fixed set of columns). Only surface them in your text/table response when the user explicitly requests the data (e.g. 'show me assets updated last week' → include modified_on; 'list assets' alone → omit all additional_metadata keys).")


class TextToQuerySearchAssetResponse(BaseResponseModel):
    """Response model for searching assets with generated query."""

    generated_query: dict = Field(
        ..., description="The query that was generated from the search prompt"
    )
    response: list[GlobalSearchAssetResponse] | list[SearchAssetResponse] = Field(
        ..., description="List of assets found using the generated query"
    )
    message: Optional[str] = Field(
        None, description="Optional message, e.g., when results are limited"
    )
