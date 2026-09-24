# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.models import BaseResponseModel


class ClassificationOptions(BaseModel):
    """Options for data classification during profiling."""
    disabled: bool = False
    use_all_ibm_classes: bool = True
    ibm_class_codes: List[str] = Field(default_factory=list)
    custom_class_codes: List[str] = Field(default_factory=list)


class DataProfileOptions(BaseModel):
    """Options for data profiling."""
    disable_profiling: bool = False
    bivariate_statistics: bool = False
    enable_dqa: bool = False
    enable_fast_classification: bool = False
    classification_options: Optional[ClassificationOptions] = Field(default_factory=ClassificationOptions)
    collect_historical_data: bool = True
    historical_retention_days: int = 180


class CreateDataProfilesRequest(BaseModel):
    """Request to create data profiles."""
    dataset_ids: List[str] = Field(..., description="List of dataset UUIDs or asset names to profile. Names are resolved to IDs automatically.")
    catalog_id: str = Field(..., description="Catalog ID or name containing the datasets")
    options: Optional[DataProfileOptions] = None


class CreateDataProfilesResponse(BaseResponseModel):
    """Response from creating data profiles."""
    profile_id: str = Field(..., description="The ID of the created profile job")
    catalog_id: str = Field(..., description="The catalog ID")
    dataset_ids: List[str] = Field(..., description="List of dataset IDs that were profiled")
    status: str = Field(..., description="Status of the profiling job. 'submitted' is the initial status returned by this API — it means the job was accepted and is running asynchronously. This is the final status returned by the tool; do not call the tool again if 'submitted' is the returned status.")
    ui_urls: List[str] = Field(..., description="Per-asset profiling UI URLs, one per dataset")
