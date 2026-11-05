# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json  # noqa: I001 # Baseline
from pydantic import BaseModel, Field, model_validator
from app.shared.models import BaseResponseModel, field_validator
from typing import List, Optional, Union  # noqa: UP035 # Baseline
from app.services.metadata_import.models.create_metadata_import import ImportType


class EditReimportOptions(BaseModel):
    """Re-import behaviour overrides. All fields are required."""

    update_name: bool = Field(
        description="Whether to update the asset name during re-import."
    )
    update_description: bool = Field(
        description="Whether to update the asset description during re-import."
    )
    update_column_descriptions: bool = Field(
        description="Whether to update column descriptions during re-import."
    )
    delete_when_deleted_at_source: bool = Field(
        description="Whether to delete the asset when it is deleted at the source."
    )
    delete_when_removed_from_scope: bool = Field(
        description="Whether to delete the asset when it is removed from the import scope."
    )


class EditImportOptions(BaseModel):
    """Import options overrides. All fields are required."""

    exclude_tables: bool = Field(
        description="Whether to exclude tables from the import."
    )
    exclude_views: bool = Field(description="Whether to exclude views from the import.")
    import_incremental_changes_only: bool = Field(
        description="Whether to import only incremental changes since the last import."
    )
    include_foreign_key: bool = Field(
        description="Whether to include foreign key relationships in the import."
    )
    include_primary_key: bool = Field(
        description="Whether to include primary key information in the import."
    )
    include_asset_lifecycle_timestamps: bool = Field(
        description="Whether to include asset lifecycle timestamps in the import."
    )
    metadata_from_catalog_table_only: bool = Field(
        description="Whether to import metadata from catalog tables only."
    )


class EditMetadataImportRequest(BaseModel):
    """
    Request model for editing an existing metadata import asset.
    All editable fields are optional, but at least one must be provided.
    """

    # Required fields to identify the asset
    project_name: str = Field(
        ..., description="Name of the project containing the metadata import asset."
    )
    metadata_import_name: str = Field(
        ..., description="Name of the metadata import asset to update."
    )

    # Optional editable fields
    description: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="New description for the metadata import asset."
    )
    scope: Optional[Union[List[str], str]] = Field(  # noqa: UP006, UP007, UP045 # Baseline
        None,
        description="Updated list of schema/table paths to import. Provide as a list of strings, e.g., ['/schema1', '/schema2'] or ['/'] for all schemas.",
        examples=[
            ["/"],
            ["/schema1", "/schema2"],
            ["/demo/bank", "/demo/bank/employee"],
        ],
    )
    tags: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        None, description="Updated list of tags for the metadata import asset."
    )
    import_type: Optional[ImportType] = Field(  # noqa: UP045 # Baseline
        None, description="The type of metadata import (e.g. 'metadata')."
    )
    reimport_options: Optional[EditReimportOptions] = Field(  # noqa: UP045 # Baseline
        None,
        description="Partial overrides for re-import behaviour. Only supply the keys you want to change.",
    )
    import_options: Optional[EditImportOptions] = Field(  # noqa: UP045 # Baseline
        None,
        description="Partial overrides for import options. Only supply the keys you want to change.",
    )

    @field_validator("scope")
    def validate_scope(cls, v):  # noqa: ANN001, ANN201, N805 # Baseline
        if v is None:
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):  # noqa: SIM108 # Baseline
                    v = parsed
                else:
                    v = [parsed]
            except json.JSONDecodeError as e:
                raise ValueError(  # noqa: B904 # Baseline
                    f"Invalid JSON in scope parameter: {e}. "
                    'Expected a list of path strings, e.g. ["/schema1", "/schema2"].'
                )
        if isinstance(v, list) and len(v) == 0:
            raise ValueError(
                "scope list cannot be empty. Provide at least one path or omit the field."
            )
        return v

    @model_validator(mode="after")
    def validate_at_least_one_field(self):  # noqa: ANN201 # Baseline
        provided = [
            self.description,
            self.scope,
            self.tags,
            self.import_type,
            self.reimport_options,
            self.import_options,
        ]
        if all(v is None for v in provided):
            raise ValueError(
                "At least one field (description, scope, tags, import_type, "
                "reimport_options, or import_options) must be provided for update."
            )
        return self


class EditMetadataImportResponse(BaseResponseModel):
    """Response model for editing a metadata import asset."""

    message: str = Field(
        ..., description="Success message describing the update operation."
    )
    metadata_import_id: str = Field(
        ..., description="The unique identifier of the updated metadata import asset."
    )
    metadata_import_name: str = Field(
        ..., description="The name of the updated metadata import asset."
    )
    metadata_import_asset_ui_url: str = Field(
        ..., description="The URL to view the updated metadata import asset in the UI."
    )
