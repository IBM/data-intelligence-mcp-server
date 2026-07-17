# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.


from typing import Annotated, Optional

from pydantic import Field
from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    MetadataEnrichmentAnalysisRequest,
    MetadataEnrichmentObjective,
    MetadataEnrichmentRun,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    do_metadata_enrichment_process,
)
from app.shared.logging import LOGGER, auto_context


async def _execute_metadata_expansion_for_selected_assets(
    request: MetadataEnrichmentAnalysisRequest,
) -> list[MetadataEnrichmentRun]:

    LOGGER.info(
        f"The execute_metadata_expansion_for_selected_assets was called with data_assets = {request.dataset_names}, categories={request.category_names}, project_name={request.project_name}"
    )

    return await do_metadata_enrichment_process(
        project_name=request.project_name,
        dataset_names=request.dataset_names,
        category_names=request.category_names,
        objectives=[
            MetadataEnrichmentObjective.PROFILE,
            MetadataEnrichmentObjective.SEMANTIC_EXPANSION,
        ],
        job_name=request.job_name,
    )


@service_registry.tool(
    name="execute_metadata_expansion_for_selected_assets",
    annotations={
        "title": "Execute Semantic Metadata Expansion for Selected Datasets",
        "destructiveHint": True
    },
    description="""Use this tool when you need to executes metadata expansion for specific datasets within a project.
    
    This tool performs metadata expansion on the datasets specified in the request. It retrieves the datasets,
    confirms their existence within the project, selects the designated categories, and initiates the expansion process.
    
    If the specified data asset is not included in any MDE, it will be added to an MDE named Metadata_Enrichment_for_MCP_Agent.
    If Metadata_Enrichment_for_MCP_Agent does not exist, it will be created automatically.
    
    The function returns a MetadataEnrichmentRun object containing details about the executed expansion job,
    including its ID, run ID, and a URL to monitor progress in the UI.
    
    The execution process involves:
    1. Confirming the project ID based on the provided project name.
    2. Identifying the dataset IDs based on the provided dataset names.
    3. Selecting categories for expansion based on the provided category names.
    4. Executing the metadata expansion job for the specified datasets and categories.
    5. Constructing a URL to the metadata enrichment UI for monitoring.
    
    The function assumes the datasets and categories are valid within the project. It does not handle dataset or category creation.
    The metadata expansion objective includes profiling the data and expanding semantically using predefined rules or external knowledge bases.
    Return: A list of objects containing job details including metadata enrichment ID, job ID, job run ID, project ID, and a UI URL to monitor the semantic metadata expansion progress.""",
)
@auto_context
async def execute_metadata_expansion_for_selected_assets(
    project_name: Annotated[str, Field(description="The name of the project for which the analysis is to be performed.")],
    dataset_names: Annotated[list[str] | str, Field(description="Dataset names of the specified datasets to be enriched with metadata.")],
    category_names: Annotated[list[str] | str, Field(description="""Names of the categories for which data quality analysis is required. 
                                                     If a single category name is provided, it should be a string. If multiple categories are specified, they should be provided as a list of strings.""")],
    job_name: Annotated[Optional[str], Field(description="The name of the job to execute the metadata enrichment asset.")],
) -> list[MetadataEnrichmentRun]:
    """Wrapper that MetadataEnrichmentAnalysisRequest expands object into individual parameters."""

    request = MetadataEnrichmentAnalysisRequest(
        project_name=project_name,
        dataset_names=dataset_names,
        category_names=category_names,
        job_name=job_name,
    )
    return await _execute_metadata_expansion_for_selected_assets(request)
