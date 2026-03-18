# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Import APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.

from string import Template

from app.core.registry import service_registry
from app.services.constants import METADATA_IMPORT_BASE_ENDPOINT, JOBS_BASE_ENDPOINT
from app.services.metadata_import.models.execute_metadata_import import (
    ExecuteMetadataImportRequest,
    ExecuteMetadataImportResponse,
    MetadataImportJobRun
)
from app.services.tool_utils import find_project_id, find_metadata_import_id
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url, confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ExternalAPIError, ServiceError


UI_BASE_URL = str(tool_helper_service.ui_base_url)
MDI_UI_JOB_RUN_URL_TEMPLATE = UI_BASE_URL + "/gov/metadata-imports/jobs/runs?project_id=${project_id}&job_id=${job_id}&jobrun_id=${jobrun_id}"

async def find_job_id_in_metadata_import(
    metadata_import_id: str, project_id: str
) -> str:
    """
    Find ID of the job in a metadata import asset.

    Args:
        metadata_import_id (str): The ID of the metadata import asset.
        project_id (str): The ID of the project containing the metadata import.

    Returns:
        str: The unique identifier of the job in the metadata import.

    Raises:
        ServiceError: If the job ID is not found in the metadata import.
    """
    LOGGER.info(
        "Finding job ID in metadata import: metadata_import_id=%s, project_id=%s",
        metadata_import_id,
        project_id,
    )

    get_url = f"{tool_helper_service.base_url}{METADATA_IMPORT_BASE_ENDPOINT}/{metadata_import_id}"
    query_params = {
        "project_id": project_id,
    }
    LOGGER.debug("GET request URL: %s, params: %s", get_url, query_params)
    
    response = await tool_helper_service.execute_get_request(
        url=get_url,
        params=query_params,
        tool_name="execute_metadata_import",
    )

    result_id = response.get("entity", {}).get("job_id", None)
    
    if result_id:
        LOGGER.info("Successfully found job ID: %s", result_id)
        return result_id
    else:
        LOGGER.error(
            "Job ID not found in metadata import: metadata_import_id=%s",
            metadata_import_id,
        )
        raise ServiceError(
            f"The job id in the metadata import with id: {metadata_import_id} was not found."
        )


async def execute_metadata_import_job(
    job_id: str, project_id: str
) -> tuple[str, str]:
    """
    Execute the metadata import job.

    Args:
        job_id (str): The ID of the job in the metadata import.
        project_id (str): The ID of the project containing the metadata import.
    
    Returns:
        tuple[str, str]: A tuple containing (job_run_id, state).

    Raises:
        ServiceError: If the metadata import job fails to execute.
        ExternalAPIError: If an unexpected error occurs while communicating with the external service.
    """
    LOGGER.info(
        "Executing metadata import job: job_id=%s, project_id=%s",
        job_id,
        project_id
    )

    post_url = f"{tool_helper_service.base_url}{JOBS_BASE_ENDPOINT}/{job_id}/runs"
    query_params = {
        "project_id": project_id,
    }
    
    LOGGER.debug("POST request URL: %s, params: %s", post_url, query_params)

    try:
        response = await tool_helper_service.execute_post_request(
            url=post_url,
            params=query_params,
            tool_name="execute_metadata_import",
        )
        
        LOGGER.debug("Received response from metadata import job execution")
        
        job_run = MetadataImportJobRun(**response)
        job_run_id = job_run.metadata.asset_id
        state = job_run.entity.job_run.state
        
        LOGGER.info(
            "Metadata import job executed successfully: job_run_id=%s, state=%s",
            job_run_id,
            state,
        )
        
        if job_run_id:
            return job_run_id, state
        else:
            LOGGER.error("Job run ID is missing in response for job_id=%s", job_id)
            raise ServiceError(
                f"The execution of metadata import with Job ID: '{job_id}' failed."
            )
    except ExternalAPIError as eae:
        LOGGER.error(
            "An unexpected exception occurred during executing Metadata Import: job_id=%s (Cause=%s)",
            job_id,
            str(eae),
        )
        raise ServiceError(
            f"The execution of metadata import with Job ID: '{job_id}' failed due to {str(eae)}."
        )


@service_registry.tool(
    name="execute_metadata_import",
    description="""Execute a metadata import job in a project.

    ERROR HANDLING:
    - If project not found: Use 'list_containers' to find available projects or verify the project name
    - If metadata import asset not found: Use 'create_metadata_import' to create the asset first

    Returns: Job ID, run ID, state, and monitoring URL.""",
    tags={"run-metadata-import", "execute-metadata-import", "start-metadata-import"},
    meta={"version": "1.0", "service": "metadata-import"},
)
@auto_context
async def execute_metadata_import(
    request: ExecuteMetadataImportRequest,
) -> ExecuteMetadataImportResponse:

    LOGGER.info(
        "execute_metadata_import called: metadata_import_name=%s, project_name=%s",
        request.metadata_import_name,
        request.project_name,
    )

    project_id = await confirm_uuid(request.project_name, find_project_id)
    metadata_import_id = await find_metadata_import_id(
        request.metadata_import_name, project_id
    )
    job_id = await find_job_id_in_metadata_import(
        metadata_import_id, project_id
    )
    job_run_id, state = await execute_metadata_import_job(
        job_id, project_id
    )

    mdi_job_run_url = Template(MDI_UI_JOB_RUN_URL_TEMPLATE).substitute(
        job_id=job_id, jobrun_id=job_run_id, project_id=project_id
    )
    mdi_job_run_url = append_context_to_url(mdi_job_run_url)
    LOGGER.debug("Generated UI URL: %s", mdi_job_run_url)
    
    response_operation = ExecuteMetadataImportResponse(
        metadata_import_id=metadata_import_id,
        job_id=job_id,
        job_run_id=job_run_id,
        project_id=project_id,
        metadata_import_job_run_ui_url=mdi_job_run_url,
        state=state,
    )
    
    LOGGER.info(
        "execute_metadata_import completed successfully: metadata_import_id=%s, job_run_id=%s",
        metadata_import_id,
        job_run_id,
    )
    
    return response_operation


@service_registry.tool(
    name="execute_metadata_import",
    description="""Execute a metadata import job in a project.

    ERROR HANDLING:
    - If project not found: Use 'list_containers' to find available projects or verify the project name
    - If metadata import asset not found: Use 'create_metadata_import' to create the asset first
    Returns: Job ID, run ID, state, and monitoring URL.""",
    tags={"run-metadata-import", "execute-metadata-import", "start-metadata-import", "wxo"},
    meta={"version": "1.0", "service": "metadata-import"},
)
@auto_context
async def wxo_execute_metadata_import(
    project_name: str,
    metadata_import_name: str,
) -> ExecuteMetadataImportResponse:
    """Watsonx Orchestrator compatible version that expands ExecuteMetadataImportRequest object into individual parameters."""

    request = ExecuteMetadataImportRequest(
        project_name=project_name,
        metadata_import_name=metadata_import_name,
    )
    return await execute_metadata_import(request)