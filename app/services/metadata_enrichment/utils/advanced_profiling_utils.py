# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Final

from app.services.metadata_enrichment.models.advanced_profiling import (
    SampleSize,
    SampleSizeOptions,
    SampleSizePercentageOptions,
    SamplingPreset,
    StructuredSampling, AdvancedProfilingResponse,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import METADATA_ENRICHMENT_SERVICE_URL

from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.utils import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service

TOOL_NAME: Final = "execute_advanced_profiling"


def get_sampling_config_for_preset(preset: SamplingPreset) -> StructuredSampling:
    """
    Generate sampling configuration based on the selected preset.
    
    Args:
        preset: The sampling preset to use
        
    Returns:
        StructuredSampling configuration for the preset
        
    Raises:
        ServiceError: If an invalid preset is provided
    """
    if preset == SamplingPreset.BASIC:
        # Basic: 1,000 rows, 100 values for classification
        return StructuredSampling(
            method="random",
            analysis_method="fixed",
            sample_size=SampleSize(
                name="Basic",
                options=SampleSizeOptions(
                    row_number=1000,
                    classify_value_number=100
                )
            )
        )
    elif preset == SamplingPreset.MODERATE:
        # Moderate: 10,000 rows, 100 values for classification
        return StructuredSampling(
            method="random",
            analysis_method="fixed",
            sample_size=SampleSize(
                name="Moderate",
                options=SampleSizeOptions(
                    row_number=10000,
                    classify_value_number=100
                )
            )
        )
    elif preset == SamplingPreset.COMPREHENSIVE:
        # Comprehensive: 100,000 rows, all values for classification
        return StructuredSampling(
            method="random",
            analysis_method="percentage",
            sample_size=SampleSize(
                name="Comprehensive",
                percentage_options=SampleSizePercentageOptions(
                    decimal_value=1.0,
                    row_number_min=100000,
                    row_number_max=100000,
                    classify_value_number=9007199254740991  # Max safe integer for all values
                )
            )
        )
    else:
        raise ServiceError(
            f"Invalid sampling preset: {preset}. Use 'custom' preset with custom_sampling parameter for custom configurations."
        )


async def execute_advanced_profiling_job(
    metadata_enrichment_id: str,
    project_id: str,
    dataset_ids: list[str],
    sampling_config: StructuredSampling,
    unique_value_table_info: dict | None = None,
) -> AdvancedProfilingResponse:
    """
    Execute advanced profiling job for a metadata enrichment asset.
    
    Args:
        metadata_enrichment_id: The ID of the metadata enrichment asset
        project_id: The ID of the project
        dataset_ids: List of dataset IDs to profile
        sampling_config: The sampling configuration to use
        unique_value_table_info: Optional unique value table configuration dict with connection_id already resolved
        
    Returns:
        str: The job run ID
        
    Raises:
        ServiceError: If the advanced profiling job fails to execute
    """
    post_url = f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{metadata_enrichment_id}/start_advanced_profiling"
    query_params = {
        "project_id": project_id,
    }
    
    # Build the request payload
    payload = {
        "data_asset_selection": {
            "ids": dataset_ids
        },
        "sampling": {
            "structured": sampling_config.model_dump(exclude_none=True)
        }
    }
    
    # Add unique_value_table_info if provided (already has connection_id resolved)
    if unique_value_table_info:
        payload["unique_value_table_info"] = unique_value_table_info
    
    try:
        response = await tool_helper_service.execute_post_request(
            url=post_url,
            params=query_params,
            json=payload,
            tool_name=TOOL_NAME,
        )
        job_run_id = response.get("job_run_id")
        href = response.get("href")
        if job_run_id:
            return AdvancedProfilingResponse(
                job_run_id=job_run_id,
                project_id=project_id,
                metadata_enrichment_id=metadata_enrichment_id,
                href=href,
                metadata_enrichment_ui_url=""
            )
        else:
            raise ServiceError(
                f"The execution of advanced profiling for metadata enrichment ID:'{metadata_enrichment_id}' failed. No job_run_id returned."
            )
    except ExternalAPIError as eae:
        LOGGER.error(
            "An unexpected exception occurs during executing advanced profiling. (Cause=%s)",
            str(eae),
        )
        raise ServiceError(
            f"The execution of advanced profiling for metadata enrichment ID:'{metadata_enrichment_id}' failed due to {str(eae)}."
        )