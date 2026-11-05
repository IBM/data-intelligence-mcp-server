# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field  # noqa: I001 # Baseline
from app.shared.models import BaseResponseModel


class DeleteMetadataImportRequest(BaseModel):
    """
    Request model for deleting a metadata import asset.
    """

    project_name: str = Field(
        ..., description="Name of the project containing the metadata import asset."
    )
    metadata_import_name: str = Field(
        ..., description="Name of the metadata import asset to delete."
    )


class DeleteMetadataImportResponse(BaseResponseModel):
    """Response model for deleting a metadata import asset."""

    message: str = Field(..., description="Success message confirming the deletion.")
    metadata_import_id: str = Field(
        ..., description="The ID of the deleted metadata import asset."
    )
    metadata_import_name: str = Field(
        ..., description="The name of the deleted metadata import asset."
    )
