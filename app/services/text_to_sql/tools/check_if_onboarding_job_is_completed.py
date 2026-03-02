# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import re
from app.core.registry import service_registry
from app.services.constants import JOBS_BASE_ENDPOINT
from app.services.text_to_sql.models.check_if_onboarding_job_is_completed import (
    CheckIfOnboardingJobIsCompletedRequest,
    CheckIfOnboardingJobIsCompletedResponse,
)
from app.services.tool_utils import (
    check_if_container_is_enabled_for_text_to_sql,
    find_project_id,
    get_onboarding_job_run_url,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


async def _retrieve_onboarding_job_id(project_id):
    """
    Retrieves all jobs for the given project and returns the latest onboarding job id.

    Args:
       project_id (str): The project id.

    Returns:
       str: The latest onboarding job id.
    """

    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}{JOBS_BASE_ENDPOINT}",
        params={"project_id": project_id, "asset_ref_type": "ibm_gen_ai_onboard_flow"},
    )
    jobs = sorted(
        [
            job
            for job in response.get("results", [])
            if re.search(
                r"^Onboard\sfor\sgenerative\sAI\s\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}$",
                job.get("metadata", {}).get("name"),
            )
        ],
        key=lambda job: job.get("metadata", {}).get("name"),
        reverse=True,
    )
    if not jobs:
        raise ServiceError(
            f"Couldn't find Text To SQL onboarding job for project {project_id}. Please enable it first."
        )
    return jobs[0].get("metadata", {}).get("asset_id", "")


async def _retrieve_onboarding_job_run_id(project_id, job_id):
    """
    Retrieves all runs of the onboarding job for the given project and returns the id of the most recent run.

    Args:
        project_id (str): The id of the project.
        job_id (str): The id of the onboarding job.

    Returns:
        str: The id of the most recent run of the onboarding job.
    """
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}{JOBS_BASE_ENDPOINT}/{job_id}/runs",
        params={"project_id": project_id},
    )
    runs = sorted(
        response.get("results", []),
        key=lambda run: run.get("metadata", {}).get("created_at"),
        reverse=True,
    )
    if not runs:
        raise ServiceError(
            f"Couldn't find Text To SQL onboarding job run for project {project_id}. Please enable it first."
        )
    return runs[0].get("metadata", {}).get("asset_id", "")


async def _check_onboarding_job_status(project_id, job_id, run_id):
    """
    Check the status of the onboarding job for the given project.

    Args:
        project_id (str): The ID of the project to check the onboarding job status for.
        job_id (str): The ID of the onboarding job to check the status of.
        run_id (str): The ID of the run to check the status of.

    Returns:
        bool: True if the onboarding job is completed, False if job is still in progress.

    Throws:
        ExternalServiceError: If onboarding job is in any of unsuccessful states.
    """
    params = {"project_id": project_id}
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}{JOBS_BASE_ENDPOINT}/{job_id}/runs/{run_id}",
        params=params,
        tool_name="enable_project_for_text_to_sql",
    )
    run_state = response.get("entity", {}).get("job_run", {}).get("state", "Running")

    if run_state.lower() in ["completed", "completedwithwarnings"]:
        return True
    elif run_state.lower() in [
        "failed",
        "canceled",
        "paused",
        "completedwitherrors",
    ]:
        raise ServiceError(
            f"Tool check_if_onboarding_job_is_completed call finishes unsuccessfully because onboarding job had some failure for job_id: {job_id}, run_id: {run_id} in project: {project_id}. Please check the job status in the UI: {get_onboarding_job_run_url(project_id, job_id, run_id)}."
        )
    return False


@service_registry.tool(
    name="text_to_sql_check_if_onboarding_job_is_completed",
    description="This tool checks if the onboarding job for enabling Text to SQL is completed.",
)
@auto_context
async def check_if_onboarding_job_is_completed(
    input: CheckIfOnboardingJobIsCompletedRequest,
) -> CheckIfOnboardingJobIsCompletedResponse:
    LOGGER.info(
        "Calling check_if_onboarding_job_is_completed, project_id_or_name: %s",
        input.project_id_or_name,
    )

    project_id = await confirm_uuid(
        input.project_id_or_name,
        find_project_id,
    )

    if not await check_if_container_is_enabled_for_text_to_sql(project_id, "project"):
        raise ServiceError(
            f"Tool check_if_onboarding_job_is_completed failed because project {input.project_id_or_name} has not been enabled for Text to SQL. Please enable it first."
        )

    job_id = await _retrieve_onboarding_job_id(project_id)
    run_id = await _retrieve_onboarding_job_run_id(project_id, job_id)

    if await _check_onboarding_job_status(project_id, job_id, run_id):
        return CheckIfOnboardingJobIsCompletedResponse(
            state="Onboarding job is completed."
        )
    return CheckIfOnboardingJobIsCompletedResponse(
        state=f"Onboarding job is still in progress. Use this link to check the status of the job: {get_onboarding_job_run_url(project_id, job_id, run_id)}"
    )


@service_registry.tool(
    name="text_to_sql_check_if_onboarding_job_is_completed",
    description="This tool checks if the onboarding job for enabling Text to SQL is completed.",
)
@auto_context
async def wxo_check_if_onboarding_job_is_completed(
    project_id_or_name: str,
) -> CheckIfOnboardingJobIsCompletedResponse:
    """Watsonx Orchestrator compatible version that expands CheckIfOnboardingJobIsCompletedRequest object into individual parameters."""

    request = CheckIfOnboardingJobIsCompletedRequest(
        project_id_or_name=project_id_or_name
    )

    # Call the original check_if_onboarding_job_is_completed function
    return await check_if_onboarding_job_is_completed(request)
