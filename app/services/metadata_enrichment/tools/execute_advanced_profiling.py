# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.

from functools import partial
from string import Template

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.advanced_profiling import (
    AdvancedProfilingRequest,
    AdvancedProfilingResponse,
    SamplingPreset,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    MDE_UI_URL_TEMPLATE,
)
from app.services.metadata_enrichment.utils.advanced_profiling_utils import (
    execute_advanced_profiling_job,
    get_sampling_config_for_preset,
)
from app.services.tool_utils import (
    confirm_list_str,
    find_asset_id_exact_match,
    find_connection_id,
    find_metadata_enrichment_id,
    find_project_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url, confirm_uuid


@service_registry.tool(
    name="execute_advanced_profiling",
    description="""Executes advanced profiling on a metadata enrichment asset for selected datasets.

    This tool runs advanced profiling on specified datasets within a metadata enrichment asset.
    Advanced profiling provides detailed analysis including unique value distributions and 
    comprehensive data quality metrics.

    The tool supports four sampling presets:
    - basic: Minimum sample size (1,000 rows, 100 values for classification) - optimized for speed
    - moderate: Balanced approach (10,000 rows, 100 values for classification) - trade-off between speed and accuracy
    - comprehensive: Large sample size (100,000 rows, all values for classification) - optimized for accuracy
    - custom: User-defined sampling configuration via custom_sampling parameter

    The execution process involves:
    1. Confirming the project ID based on the provided project name.
    2. Retrieving the metadata enrichment asset ID using its name.
    3. Looking up dataset IDs from the provided dataset names.
    4. Configuring sampling based on the selected preset or custom configuration.
    5. Executing the advanced profiling job with the specified parameters.
    6. Returning job details and a URL to monitor progress in the UI.

    The function assumes the metadata enrichment asset and datasets exist within the project.""",
)
@auto_context
async def execute_advanced_profiling(
    request: AdvancedProfilingRequest,
) -> AdvancedProfilingResponse:

    LOGGER.info(
        f"The execute_advanced_profiling was called with project_name={request.project_name}, "
        f"mde_name={request.metadata_enrichment_name}, dataset_names={request.dataset_names}, "
        f"sampling_preset={request.sampling_preset}"
    )

    # Confirm project ID
    project_id = await confirm_uuid(request.project_name, find_project_id)
    
    # Confirm metadata enrichment asset ID
    metadata_enrichment_id = await find_metadata_enrichment_id(
        request.metadata_enrichment_name, project_id
    )
    
    # Confirm dataset IDs
    dataset_names = confirm_list_str(request.dataset_names)
    dataset_ids = [
        await confirm_uuid(
            dataset_name, partial(find_asset_id_exact_match, container_id=project_id)
        )
        for dataset_name in dataset_names
    ]
    
    # Determine sampling configuration
    if request.sampling_preset == SamplingPreset.CUSTOM:
        if not request.custom_sampling:
            raise ServiceError(
                "custom_sampling parameter is required when sampling_preset is 'custom'"
            )
        sampling_config = request.custom_sampling.structured
    else:
        sampling_config = get_sampling_config_for_preset(request.sampling_preset)
    
    # Build unique_value_table_info with connection_id lookup if provided
    unique_value_table_info = None
    if request.unique_value_table_info:
        try:
            # Look up connection ID from connection name (following the pattern of other ID lookups in this tool)
            connection_id = await find_connection_id(
                request.unique_value_table_info.location.connection_name,
                project_id,
                'project'
            )
            
            if not connection_id:
                raise ServiceError(
                    f"No connection found with name '{request.unique_value_table_info.location.connection_name}' "
                    f"in project '{request.project_name}'. Please verify the connection name and try again."
                )
            
            # Build the payload with resolved connection_id
            unique_value_table_info = {
                "location": {
                    "connection_id": connection_id,
                    "catalog_name": request.unique_value_table_info.location.catalog_name,
                    "schema_name": request.unique_value_table_info.location.schema_name,
                    "table_name": request.unique_value_table_info.location.table_name,
                },
                "count": request.unique_value_table_info.count,
            }
        except ServiceError as e:
            # Re-raise with additional context about advanced profiling
            raise ServiceError(
                f"Failed to configure unique value table for advanced profiling: {str(e)}"
            )
    
    # Execute the advanced profiling job with resolved IDs
    advanced_profiling_response = await execute_advanced_profiling_job(
        metadata_enrichment_id=metadata_enrichment_id,
        project_id=project_id,
        dataset_ids=dataset_ids,
        sampling_config=sampling_config,
        unique_value_table_info=unique_value_table_info,
    )
    
    # Construct the UI URL for monitoring
    mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
        mde_id=metadata_enrichment_id, project_id=project_id
    )
    mde_url = append_context_to_url(mde_url)

    advanced_profiling_response.metadata_enrichment_ui_url = mde_url

    return advanced_profiling_response


@service_registry.tool(
    name="execute_advanced_profiling",
    description="""Executes advanced profiling on a metadata enrichment asset for selected datasets.

    This tool runs advanced profiling on specified datasets within a metadata enrichment asset.
    Advanced profiling provides detailed analysis including unique value distributions and 
    comprehensive data quality metrics.

    The tool supports four sampling presets:
    - basic: Minimum sample size (1,000 rows, 100 values for classification) - optimized for speed
    - moderate: Balanced approach (10,000 rows, 100 values for classification) - trade-off between speed and accuracy
    - comprehensive: Large sample size (100,000 rows, all values for classification) - optimized for accuracy
    - custom: User-defined sampling configuration via custom_sampling parameter

    The execution process involves:
    1. Confirming the project ID based on the provided project name.
    2. Retrieving the metadata enrichment asset ID using its name.
    3. Looking up dataset IDs from the provided dataset names.
    4. Configuring sampling based on the selected preset or custom configuration.
    5. Executing the advanced profiling job with the specified parameters.
    6. Returning job details and a URL to monitor progress in the UI.

    The function assumes the metadata enrichment asset and datasets exist within the project.""",
)
@auto_context
async def wxo_execute_advanced_profiling(
    project_name: str,
    metadata_enrichment_name: str,
    dataset_names: list[str] | str,
    sampling_preset: str = "basic",
) -> AdvancedProfilingResponse:
    """Watsonx Orchestrator compatible version that expands AdvancedProfilingRequest into individual parameters."""
    
    request = AdvancedProfilingRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
        dataset_names=dataset_names,
        sampling_preset=SamplingPreset(sampling_preset),
    )
    return await execute_advanced_profiling(request)