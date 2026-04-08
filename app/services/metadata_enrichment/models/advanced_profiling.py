# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.shared.models import BaseResponseModel


class SamplingPreset(str, Enum):
    """Predefined sampling presets for advanced profiling."""
    
    BASIC = "basic"
    MODERATE = "moderate"
    COMPREHENSIVE = "comprehensive"
    CUSTOM = "custom"


class UniqueValueTableLocation(BaseModel):
    """Location information for the unique value table."""
    
    connection_name: str = Field(
        ...,
        description="The connection name for the database where profiling results will be stored."
    )
    catalog_name: Optional[str] = Field(
        default=None,
        description="The catalog name in the database."
    )
    schema_name: str = Field(
        ...,
        description="The schema name in the database (mandatory)."
    )
    table_name: str = Field(
        ...,
        description="The table name where results will be stored. Can be an existing table or a new table to be created."
    )


class UniqueValueTableInfo(BaseModel):
    """Information about the unique value table for profiling results."""
    
    location: UniqueValueTableLocation = Field(
        ...,
        description="Location details for the unique value table."
    )
    count: int = Field(
        100,
        description="The count parameter for unique values."
    )


class SampleSizeOptions(BaseModel):
    """Sample size options for structured data profiling."""
    
    row_number: int = Field(
        ...,
        description="The number of rows to analyze per table."
    )
    classify_value_number: int = Field(
        100,
        description="The number of most frequent values per column to use for classification."
    )


class SampleSizePercentageOptions(BaseModel):
    """Percentage-based sample size options for structured data profiling."""
    
    decimal_value: float = Field(
        ...,
        description="The sample percentage expressed as decimal value (e.g., 0.1 for 10%)."
    )
    row_number_min: int = Field(
        ...,
        description="The minimum number of rows to profile."
    )
    row_number_max: int = Field(
        ...,
        description="The maximum number of rows to profile."
    )
    classify_value_number: int = Field(
        100,
        description="The number of most frequent values per column to use for classification."
    )


class SampleSize(BaseModel):
    """Sample size configuration for profiling."""
    
    name: Optional[str] = Field(
        default=None,
        description="An optional name for the sample size configuration."
    )
    options: Optional[SampleSizeOptions] = Field(
        default=None,
        description="Sample size options for fixed sampling method."
    )
    percentage_options: Optional[SampleSizePercentageOptions] = Field(
        default=None,
        description="Sample size percentage options for percentage-based sampling method."
    )


class StructuredSampling(BaseModel):
    """Structured data sampling configuration."""
    
    method: str = Field(
        "random",
        description="The sampling method (e.g., 'random')."
    )
    analysis_method: str = Field(
        "percentage",
        description="The analysis method (e.g., 'percentage' or 'fixed')."
    )
    sample_size: SampleSize = Field(
        ...,
        description="Sample size configuration for the profiling job."
    )


class Sampling(BaseModel):
    """Sampling configuration for advanced profiling."""
    
    structured: StructuredSampling = Field(
        ...,
        description="Structured data sampling configuration."
    )


class DataAssetSelection(BaseModel):
    """Selection of data assets for profiling."""
    
    ids: list[str] = Field(
        ...,
        description="List of data asset IDs to profile."
    )


class AdvancedProfilingRequest(BaseModel):
    """Request model for executing advanced profiling on metadata enrichment assets."""
    
    project_name: str = Field(
        ...,
        description="The name of the project containing the metadata enrichment asset."
    )
    metadata_enrichment_name: str = Field(
        ...,
        description="The name of the metadata enrichment asset to run advanced profiling on."
    )
    dataset_names: list[str] | str = Field(
        ...,
        description="Dataset names to be profiled. Can be a single string or list of strings."
    )
    sampling_preset: SamplingPreset = Field(
        default=SamplingPreset.BASIC,
        description="""The sampling preset to use for profiling:
        - basic: Minimum sample size (1,000 rows, 100 values for classification)
        - moderate: Balanced approach (10,000 rows, 100 values for classification)
        - comprehensive: Large sample size (100,000 rows, all values for classification)
        - custom: User-defined sampling configuration"""
    )
    unique_value_table_info: Optional[UniqueValueTableInfo] = Field(
        default=None,
        description="Optional configuration for storing unique value profiling results in a database table."
    )
    custom_sampling: Optional[Sampling] = Field(
        default=None,
        description="Custom sampling configuration. Required only when sampling_preset is 'custom'."
    )


class AdvancedProfilingResponse(BaseResponseModel):
    """Response model for advanced profiling execution."""
    
    metadata_enrichment_id: str = Field(
        ...,
        description="The unique identifier of the metadata enrichment asset."
    )
    job_run_id: str = Field(
        ...,
        description="The unique identifier of the advanced profiling job run."
    )
    project_id: str = Field(
        ...,
        description="The unique identifier of the project."
    )
    metadata_enrichment_ui_url: str = Field(
        ...,
        description="The URL to monitor the advanced profiling job in the UI."
    )
    href: str = Field(
        ...,
        description="The location URL to retrieve the job run."
    )