# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import time

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_result, RetryError

from app.core.registry import service_registry
from app.services.constants import GEN_AI_ONBOARD_API, JOBS_BASE_ENDPOINT
from app.services.text_to_sql.models.enable_project_for_text_to_sql import (
    EnableProjectForTextToSqlRequest,
    EnableProjectForTextToSqlResponse,
)
from app.services.tool_utils import find_project_id
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


async def _wait_for_onboarding_job_to_finish(job_id, run_id, project_id):
    params = {"project_id": project_id}

    @retry(
        retry=retry_if_result(lambda result: result is True),
        stop=stop_after_attempt(30),
        wait=wait_fixed(10),
        reraise=True,
    )
    async def check_job_status():
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{JOBS_BASE_ENDPOINT}/{job_id}/runs/{run_id}",
            params=params,
        )

        run_state = (
            response.get("entity", {}).get("job_run", {}).get("state", "Running")
        )

        if run_state.lower() in ["completed", "completedwithwarnings"]:
            return False
        elif run_state.lower() in [
            "failed",
            "canceled",
            "paused",
            "completedwitherrors",
        ]:
            raise ExternalAPIError(
                f"Tool enable_project_for_text_to_sql call finishes unsuccessfully because onboarding job had some failure for job_id: {job_id}, run_id: {run_id} in project: {project_id}. Please check the job status in the UI."
            )
        return True

    try:
        await check_job_status()
        LOGGER.info(
            "Onboarding job for project_id: %s completed successfully.", project_id
        )
    except RetryError:
        raise ServiceError(
            f"Tool enable_project_for_text_to_sql call finishes unsuccessfully because onboarding job is still running for job_id: {job_id}, run_id: {run_id} in project: {project_id}. Please check the job status in the UI."
        )


@service_registry.tool(
    name="text_to_sql_enable_project_for_text_to_sql",
    description="This tool enables the specified project for Text To SQL.",
)
@auto_context
async def enable_project_for_text_to_sql(
    input: EnableProjectForTextToSqlRequest,
) -> EnableProjectForTextToSqlResponse:
    project_id = await confirm_uuid(input.project_id_or_name, find_project_id)
    LOGGER.info(
        "Calling enable_project_for_text_to_sql, project_id: %s",
        input.project_id_or_name,
    )

    params = {
        "container_type": "project",
        "container_id": project_id,
    }

    payload = {
        "containers": [{"container_id": project_id, "container_type": "project"}],
        "description": "Onboard the asset containers for text2sql capability",
        "name": f"Onboard for generative AI {time.strftime('%Y-%m-%d %H-%M-%S')}",
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GEN_AI_ONBOARD_API,
        params=params,
        json=payload,
    )

    await _wait_for_onboarding_job_to_finish(
        job_id=response["job_id"],
        run_id=response["run_id"],
        project_id=project_id,
    )

    return EnableProjectForTextToSqlResponse(
        message=f"Project {project_id} has been enabled for Text to SQL."
    )


@service_registry.tool(
    name="text_to_sql_enable_project_for_text_to_sql",
    description="This tool enables the specified project for Text To SQL.",
)
@auto_context
async def wxo_enable_project_for_text_to_sql(
    project_id_or_name: str,
) -> EnableProjectForTextToSqlResponse:
    """Watsonx Orchestrator compatible version that expands EnableProjectForTextToSqlRequest object into individual parameters."""

    request = EnableProjectForTextToSqlRequest(project_id_or_name=project_id_or_name)

    # Call the original enable_project_for_text_to_sql function
    return await enable_project_for_text_to_sql(request)
