# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel

class GetSemanticModelRequest(BaseModel):
    """Request model for getting schema assets."""

    container_info: Optional[List[dict[str, str | Literal["project", "catalog"]]]] = Field(
        default=None,
        description="Optional list of dictionaries that contain container(s) information to retrieve schema assets from. Each dictionary should conatin 'container_id_or_name' key and optionally 'container_type' key. If 'container_type' not provided, then default is 'project'. The key 'container_id_or_name' is required. Example: [{'container_id_or_name': 'testCatalog', 'container_type': 'catalog'}, {'container_id_or_name': 'testProject'}]"
    )
    connection_ids_or_names: Optional[List[str]] = Field(
        default=None,
        description="Optional list of connection IDs or names to filter schema assets by specific connections."
    )
    asset_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific asset IDs to retrieve schema for."
    )
    data_source_definition_id_or_name: Optional[str] = Field(
        default=None,
        description="Optional data source definition name or asset ID."
    )
    document_library_ids: Optional[str] = Field(
        default=None,
        description="The document libraries to use (for Lakehouse only) for schema linking to assets. If empty, all document libraries will be used."
    )
    query: str = Field(..., description="The search prompt from the user about data assets potentially with additional searching details")

class PropertyMetadata(BaseModel):
    """Model representing a property/column in a schema asset."""
    
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Data type of the column")
    expanded_name: Optional[str] = Field(None, description="Expanded/human-readable name")
    description: Optional[str] = Field(None, description="Column description")
    primary_key: bool = Field(False, description="Whether this is a primary key")
    foreign_key: List[str] = Field(default_factory=list, description="Foreign key references")
    enabled: bool = Field(False, description="Whether the column is enabled")
    profiling: Optional[Dict[str, Any]] = Field(None, description="Profiling information")
    value_samples: Optional[List[Any]] = Field(None, description="Sample values")


class SemanticModel(BaseModel):
    """Model representing a schema asset."""
    
    asset_id: str = Field(..., description="Unique identifier of the schema asset")
    name: str = Field(..., description="Name of the table/asset")
    description: Optional[str] = Field(None, description="Description of the asset")
    expanded_name: Optional[str] = Field(None, description="Expanded/human-readable name")
    schema_name: Optional[str] = Field(None, description="Schema name if applicable")
    properties: List[PropertyMetadata] = Field(
        default_factory=list,
        description="List of columns/properties in this asset"
    )


class GetSemanticModelResponse(BaseResponseModel):
    """Response model for getting schema assets."""
    
    container_ids: List[str] = Field(default_factory=list, description="The container ID (project or catalog) where schema assets were retrieved from")
    schema_assets: List[SemanticModel] = Field(
        default_factory=list,
        description="List of schema assets available for text-to-SQL operations"
    )
    total_count: int = Field(default=0, description="Total number of schema assets found")