# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.


from functools import partial
from string import Template
from typing import Annotated, Optional

from pydantic import Field
from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    MetadataEnrichmentExecutionRequest,
    MetadataEnrichmentRun,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    MDE_UI_URL_TEMPLATE,
    execute_metadata_enrichment_with_assets,
    find_job_id_in_metadata_enrichment, get_metadata_enrichment_asset_jobs,
)
from app.services.tool_utils import (
    confirm_list_str,
    find_asset_id_exact_match,
    find_metadata_enrichment_id,
    find_project_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import confirm_uuid


async def _execute_metadata_enrichment_asset_for_selected_assets(
    request: MetadataEnrichmentExecutionRequest,
) -> MetadataEnrichmentRun:

    LOGGER.info(
        f"The execute_metadata_enrichment_asset_for_selected_assets was called with mde_name={request.metadata_enrichment_name}, project_name={request.project_name}, dataset_names={request.dataset_names}"
    )

    project_id = await confirm_uuid(request.project_name, find_project_id)
    metadata_enrichment_id = await find_metadata_enrichment_id(
        request.metadata_enrichment_name, project_id
    )
    dataset_ids = [
        await confirm_uuid(
            dataset_name, partial(find_asset_id_exact_match, container_id=project_id)
        )
        for dataset_name in confirm_list_str(request.dataset_names)
    ]
    if request.job_name is None:
        mde_jobs = await get_metadata_enrichment_asset_jobs(project_id, metadata_enrichment_id)
        if len(mde_jobs) == 1:
            job_id = mde_jobs[0].id
        else:
            raise ServiceError(
                message=f"Found multiple jobs for the the MDE {request.metadata_enrichment_name} and project {request.project_name}",
                remediation_steps="Invoke the tool 'list_metadata_enrichment_asset_jobs' to list all the available jobs for the selected MDE and surface them back to the user.",
            )
    else:
        job_id = await confirm_uuid(request.job_name,
                                    partial(find_asset_id_exact_match, container_id=project_id, artifact_type="job", raise_errors=False))

    if not job_id:
        raise ServiceError(
            message=f"No job found with the name {request.job_name} in the MDE {request.metadata_enrichment_name}",
            remediation_steps="Invoke the tool 'list_metadata_enrichment_asset_jobs' to list all the available jobs for the selected MDE and surface them back to the user.",
        )

    job_run_id = await execute_metadata_enrichment_with_assets(
        metadata_enrichment_id, project_id, job_id, dataset_ids
    )

    mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
        mde_id=metadata_enrichment_id, project_id=project_id
    )

    response_operation = MetadataEnrichmentRun(
        metadata_enrichment_id=metadata_enrichment_id,
        job_id=job_id,
        job_run_id=job_run_id,
        project_id=project_id,
        metadata_enrichment_ui_url=mde_url,
    )
    return response_operation


@service_registry.tool(
    name="execute_metadata_enrichment_asset_for_selected_assets",
    annotations={
        "title": "Execute Pre-configured Metadata Enrichment Asset on Selected Datasets",
        "destructiveHint": True
    },
    description="""Use this tool when you need to executes a metadata enrichment asset for selected datasets within a specified project.

    This tool initiates the execution of a pre-configured metadata enrichment asset, applying it to multiple datasets.
    It retrieves the asset's details, confirms its existence within the project, and starts the enrichment job for the specified datasets.
    The function returns a MetadataEnrichmentRun object containing information about the executed job,
    including its ID, run ID, and a URL to monitor its progress in the UI.
    
    The execution process involves:
    1. Confirming the project ID based on the provided project name.
    2. Retrieving the metadata enrichment asset ID using its name within the project.
    3. Confirming the UUIDs of the datasets to be enriched, matching them exactly within the project.
    4. Executing the metadata enrichment job with the selected datasets.
    5. Constructing a URL to the metadata enrichment UI for monitoring.
    
    The function assumes the metadata enrichment asset is already defined and valid within the project,
    and the datasets specified exist. It does not handle asset creation or validation of dataset names beyond exact matching.
    Return: Job execution details including metadata enrichment ID, job ID, job run ID, project ID, and a UI URL to monitor the enrichment progress.""",
)
@auto_context
async def execute_metadata_enrichment_asset_for_selected_assets(
    project_name: Annotated[str, Field(description="The name of the project you want to execute a metadata enrichment.")],
    metadata_enrichment_name: Annotated[str, Field(description="The name of the metadata enrichment you want to execute.")],
    dataset_names: Annotated[list[str] | str, Field(description="Dataset names of the specified datasets to be enriched with metadata.")],
job_name: Annotated[Optional[str], Field(description="The name of the job to execute the metadata enrichment asset.")],
) -> MetadataEnrichmentRun:
    """Wrapper that MetadataEnrichmentExecutionRequest expands object into individual parameters."""

    request = MetadataEnrichmentExecutionRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
        dataset_names=dataset_names,
        job_name=job_name,
    )
    return await _execute_metadata_enrichment_asset_for_selected_assets(request)
