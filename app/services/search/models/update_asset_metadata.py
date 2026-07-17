# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel


class RelatedAssetRequest(BaseModel):
    """A related item (asset, artifact, or column) to connect to the source asset."""

    item_type: Literal["asset", "artifact", "column"] = Field(
        ...,
        description="Type of related item: 'asset' for data assets, 'artifact' for governance artifacts (business terms, classifications), 'column' for asset columns."
    )
    target_id_or_name: str = Field(
        ...,
        description="Name or ID of the target item. For assets: asset name or UUID (will be resolved internally). For artifacts: business term/classification name or global_id (will be resolved internally). For columns: column name."
    )
    artifact_type: Optional[Literal["glossary_term", "classification"]] = Field(
        None,
        description="For artifacts only: type of governance artifact. 'glossary_term' for business terms, 'classification' for classifications. If not provided, will try glossary_term first, then classification."
    )
    target_asset_id_or_name: Optional[str] = Field(
        None,
        description="For columns only: name or UUID of the asset containing the target column. REQUIRED when item_type='column'. Will be resolved internally if name is provided."
    )
    target_container_id_or_name: Optional[str] = Field(
        None,
        description="Target item's container name or UUID. REQUIRED for assets and columns. NOT used for artifacts (they are global). Will be resolved internally if name is provided. The container TYPE (catalog/project) is inherited from the source asset's container_type, but this MUST be a DIFFERENT container of the same type (never the same as source). If not provided, use dynamic_query_search to find the target item and ask user to select."
    )
    relationship_name: str = Field(
        "accesses",
        description="Relationship name to create from the source asset to the target item. Default: 'accesses'. Common values: 'accesses', 'consists_of', 'asset_term', 'asset-column1', etc."
    )


class UpdateAssetMetadataRequest(BaseModel):
    """Request model for updating asset metadata in either catalog or project, including governance artifacts (business terms and classifications)."""

    asset_id_or_name: str = Field(
        ...,
        description="Name or UUID of the data asset to update. If name is provided, it will be resolved to UUID internally."
    )
    container_id_or_name: str = Field(
        ...,
        description="Container name or UUID (catalog or project) containing the asset. If name is provided, it will be resolved to UUID internally."
    )
    container_type: Literal["catalog", "project"] = Field(
        "catalog",
        description="Type of container: 'catalog' or 'project'. Defaults to 'catalog'"
    )
    new_asset_name: Optional[str] = Field(
        None,
        description="New asset name to update (updates /metadata/name)"
    )
    display_name: Optional[str] = Field(
        None,
        description="Display name for the asset (updates /entity/data_asset/semantic_name)"
    )
    description: Optional[str] = Field(
        None,
        description="Asset description to update (updates /metadata/description)"
    )
    privacy: Optional[Literal[0, 16]] = Field(
        None,
        description="Privacy/ROV mode for the asset. Valid values: 0 (Public), 16 (Private). Updates /metadata/rov/mode"
    )
    format: Optional[str] = Field(
        None,
        description="Asset format/MIME type (e.g., 'application/x-ibm-rel-table', 'text/csv', 'parquet'). Updates /entity/data_asset/mime_type"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="List of tags to ADD to the asset. Merges with existing tags (deduplicates automatically). Updates /metadata/tags"
    )
    business_terms: Optional[List[str]] = Field(
        None,
        description="List of business term names or global_ids to ADD to the asset. Merges with existing business terms (deduplicates by term_id). Names will be resolved to global_ids internally."
    )
    classifications: Optional[List[str]] = Field(
        None,
        description="List of classification names or global_ids to ADD to the asset. Merges with existing classifications (deduplicates by global_id). Names will be resolved to global_ids internally."
    )
    related_items: Optional[List[RelatedAssetRequest]] = Field(
        None,
        description="List of related items (assets, artifacts, columns) to ADD/connect to this asset. Merges with existing relationships (deduplicates by target_id). Each item requires item_type, target_id_or_name, and container info (for assets/columns only)."
    )


class UpdateAssetMetadataResponse(BaseResponseModel):
    """Response from updating asset metadata."""

    message: str = Field(
        ..., 
        description="Human-readable outcome summary of the update operation"
    )
    asset_id: str = Field(
        ..., 
        description="UUID of the asset that was updated"
    )
    updated_fields: List[str] = Field(
        ..., 
        description="List of fields that were successfully updated"
    )

