# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.


from string import Template

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    MDE_UI_URL_TEMPLATE,
    MetadataEnrichmentExecutionRequest,
    MetadataEnrichmentRun,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    execute_metadata_enrichment_job,
    find_job_id_in_metadata_enrichment,
)
from app.services.tool_utils import find_metadata_enrichment_id, find_project_id
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url, confirm_uuid


@service_registry.tool(
    name="execute_metadata_enrichment_asset",
    description="""Executes a metadata enrichment asset within a specified project.

    This tool initiates the execution of a pre-configured metadata enrichment asset. It retrieves the asset's details,
    confirms its existence within the project, and starts the enrichment job. The function returns a MetadataEnrichmentRun
    object containing information about the executed job, including its ID, run ID, and a URL to monitor its progress in the UI.

    The execution process involves:
    1. Confirming the project ID based on the provided project name.
    2. Retrieving the metadata enrichment asset ID using its name within the project.
    3. Finding the associated job ID for the asset.
    4. Executing the metadata enrichment job.
    5. Constructing a URL to the metadata enrichment UI for monitoring.

    The function assumes the metadata enrichment asset is already defined and valid within the project.
    It does not handle asset creation.""",
)
@auto_context
async def execute_metadata_enrichment_asset(
    request: MetadataEnrichmentExecutionRequest,
) -> MetadataEnrichmentRun:

    LOGGER.info(
        f"The execute_metadata_enrichment_asset was called with mde_name={request.metadata_enrichment_name}, project_name={request.project_name}"
    )

    project_id = await confirm_uuid(request.project_name, find_project_id)
    metadata_enrichment_id = await find_metadata_enrichment_id(
        request.metadata_enrichment_name, project_id
    )
    job_id = await find_job_id_in_metadata_enrichment(
        metadata_enrichment_id, project_id
    )
    job_run_id = await execute_metadata_enrichment_job(job_id, project_id)

    mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
        mde_id=metadata_enrichment_id, project_id=project_id
    )
    mde_url = append_context_to_url(mde_url)
    response_operation = MetadataEnrichmentRun(
        metadata_enrichment_id=metadata_enrichment_id,
        job_id=job_id,
        job_run_id=job_run_id,
        project_id=project_id,
        metadata_enrichment_ui_url=mde_url,
    )
    return response_operation


@service_registry.tool(
    name="execute_metadata_enrichment_asset",
    description="""Executes a metadata enrichment asset within a specified project.

    This tool initiates the execution of a pre-configured metadata enrichment asset. It retrieves the asset's details,
    confirms its existence within the project, and starts the enrichment job. The function returns a MetadataEnrichmentRun
    object containing information about the executed job, including its ID, run ID, and a URL to monitor its progress in the UI.

    The execution process involves:
    1. Confirming the project ID based on the provided project name.
    2. Retrieving the metadata enrichment asset ID using its name within the project.
    3. Finding the associated job ID for the asset.
    4. Executing the metadata enrichment job.
    5. Constructing a URL to the metadata enrichment UI for monitoring.

    The function assumes the metadata enrichment asset is already defined and valid within the project.
    It does not handle asset creation.""",
)
@auto_context
async def wxo_execute_metadata_enrichment_asset(
    project_name: str,
    metadata_enrichment_name: str,
) -> MetadataEnrichmentRun:
    """Watsonx Orchestrator compatible version that MetadataEnrichmentExecutionRequest expands object into individual parameters."""

    request = MetadataEnrichmentExecutionRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
    )
    return await execute_metadata_enrichment_asset(request)
