# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import Optional

from app.shared.utils.tool_helper_service import tool_helper_service
class ExecuteMetadataImportRequest(BaseModel):
    """Request model for executing a metadata import job."""
    
    project_name: str = Field(
        ..., 
        description="The name of the project containing the metadata import asset."
    )
    metadata_import_name: str = Field(
        ..., 
        description="The name of the metadata import asset to execute."
    )


class ExecuteMetadataImportResponse(BaseResponseModel):
    """Response model for metadata import execution."""
    
    metadata_import_id: str = Field(
        ..., 
        description="The unique identifier of the metadata import asset."
    )
    job_id: str = Field(
        ..., 
        description="The unique identifier of the metadata import job."
    )
    job_run_id: str = Field(
        ..., 
        description="The unique identifier of the job run."
    )
    project_id: str = Field(
        ..., 
        description="The unique identifier of the project."
    )
    metadata_import_job_run_ui_url: str = Field(
        ..., 
        description="The URL to monitor the metadata import job in the UI."
    )
    state: str = Field(
        ...,
        description="The current state of the job run (e.g., 'Running', 'Completed', 'Failed')."
    )


class MetadataImportJobRunDetail(BaseModel):
    """Complete metadata import job run detail."""
    
    state: str

class MetadataImportJobRunMetadata(BaseModel):
    """Metadata for a metadata import job run."""
    
    name: str
    asset_id: str
    asset_type: str
    project_id: str
    created: int
    created_at: str
    owner_id: str

class MetadataImportJobRunEntity(BaseModel):
    """Entity details for a metadata import job run."""

    job_run: MetadataImportJobRunDetail


class MetadataImportJobRun(BaseModel):
    """Complete metadata import job run response."""
    
    metadata: MetadataImportJobRunMetadata
    entity: MetadataImportJobRunEntity