# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Unified tool for MDI job run control operations (pause, resume, cancel)."""

from typing import Annotated, Literal, Optional

from pydantic import Field

from app.shared.logging import LOGGER, auto_context
from app.core.registry import service_registry
from app.shared.exceptions.base import ServiceError

from app.services.metadata_import.models.pause_resume_or_cancel_mdi_job_run import (
    PauseResumeOrCancelMdiJobRunRequest,
    PauseResumeOrCancelMdiJobRunResponse,
)
from app.services.metadata_import.models.constants import (
    DESC_PROJECT_NAME,
    DESC_METADATA_IMPORT_NAME,
    DESC_ACTION,
    DESC_JOB_RUN_ID,
)
from app.services.metadata_import.tools.execute_metadata_import import (
    find_job_id_in_metadata_import,
)
from app.services.metadata_import.utils.job_control_utils import (
    resolve_job_run_ids,
    fetch_job_run_details,
    validate_job_state_for_pause,
    validate_job_state_for_resume,
    validate_job_state_for_cancel,
    JOB_STATE_RUNNING,
    JOB_STATE_PAUSED,
    JOB_STATE_QUEUED,
    ACTIVE_JOB_STATES,
)
from app.shared.utils.tool_helper_service import tool_helper_service

# Maps each action to its API endpoint suffix, state validator, and eligible target states.
# target_states controls which job run states are eligible for auto-discovery when no
# job_run_id is provided. This ensures e.g. 'resume' only finds Paused runs, not Running ones.
_ACTION_CONFIG = {
    "pause": {
        "endpoint": "pause",
        "validator": validate_job_state_for_pause,
        "past_tense": "paused",
        "next_hint": "Use 'pause_resume_or_cancel_mdi_job_run' with action='resume' to resume this job run.",
        "target_states": [JOB_STATE_RUNNING],
    },
    "resume": {
        "endpoint": "resume",
        "validator": validate_job_state_for_resume,
        "past_tense": "resumed",
        "next_hint": "Use 'pause_resume_or_cancel_mdi_job_run' with action='pause' to pause this job run again if needed.",
        "target_states": [JOB_STATE_PAUSED],
    },
    "cancel": {
        "endpoint": "cancel",
        "validator": validate_job_state_for_cancel,
        "past_tense": "canceled",
        "next_hint": "To start a new import, use 'execute_metadata_import'.",
        "target_states": ACTIVE_JOB_STATES,
    },
}


async def _pause_resume_or_cancel_mdi_job_run(input: PauseResumeOrCancelMdiJobRunRequest) -> PauseResumeOrCancelMdiJobRunResponse:
    """Execute a pause, resume, or cancel operation on an MDI job run."""
    LOGGER.info(
        "Calling tool 'pause_resume_or_cancel_mdi_job_run' - action=%s, projectName=%s, metadata_import_name=%s, job_run_id=%s",
        input.action,
        input.project_name,
        input.metadata_import_name,
        input.job_run_id,
    )

    config = _ACTION_CONFIG[input.action]

    project_id, metadata_import_id, job_id, job_run_id, current_state = await resolve_job_run_ids(
        input.project_name,
        input.metadata_import_name,
        input.job_run_id,
        find_job_id_in_metadata_import,
        target_states=config["target_states"],
    )

    config["validator"](current_state)

    post_url = f"{tool_helper_service.base_url}/v2/metadata_imports/job_runs/{config['endpoint']}"
    query_params = {"jobrun_id": job_run_id, "project_id": project_id}
    request_body = {"entity": {"job_run": {"job_ref": job_id}}}

    LOGGER.debug("POST request URL: %s, params: %s, body: %s", post_url, query_params, request_body)

    try:
        await tool_helper_service.execute_post_request(
            url=post_url,
            params=query_params,
            json=request_body,
            tool_name="pause_resume_or_cancel_mdi_job_run",
        )

        # NOTE: The state returned here is a best-effort read immediately after the operation.
        # There is an eventual-consistency window where the API may still show the prior state
        # transiently. The UI URL in the response provides the authoritative live state.
        _, new_state, mdi_job_run_url = await fetch_job_run_details(job_id, job_run_id, project_id)

        message = (
            f"The metadata import job run has been successfully {config['past_tense']}. "
            f"Job run ID: {job_run_id}, State: {new_state}. "
            f"You can view the job run at [{mdi_job_run_url}]({mdi_job_run_url}). "
            f"{config['next_hint']}"
        )

        LOGGER.info("Job run %s successfully: job_run_id=%s", config['past_tense'], job_run_id)

        return PauseResumeOrCancelMdiJobRunResponse(
            message=message,
            metadata_import_id=metadata_import_id,
            metadata_import_name=input.metadata_import_name,
            job_id=job_id,
            job_run_id=job_run_id,
            job_state=new_state,
            metadata_import_job_run_ui_url=mdi_job_run_url,
        )

    except ServiceError:
        raise
    except Exception as e:
        LOGGER.error(
            "Failed to %s job run: job_run_id=%s, error=%s",
            input.action, job_run_id, str(e),
        )
        raise ServiceError(
            f"Failed to {input.action} job run '{job_run_id}': {str(e)}",
            remediation_steps=(
                "Check that the metadata import and project are accessible. "
                "Use 'search_metadata_import' to verify the MDI exists in the project."
            ),
        )


@service_registry.tool(
    name="pause_resume_or_cancel_mdi_job_run",
    annotations={
        "destructiveHint": True,
        "title": "Pause, Resume, or Cancel a Metadata Import Job Run",
    },
    description="""Pause, resume, or cancel a metadata import (MDI) job run.

    Use this single tool to control the lifecycle of an active metadata import job.
    Pass the desired 'action' parameter to specify the operation:

    - action='pause'  — Temporarily pause a Running job. Can be resumed later.
                        Only Running jobs can be paused.
    - action='resume' — Continue a previously paused job.
                        Only Paused jobs can be resumed.
    - action='cancel' — Permanently stop a Running, Paused, or Queued job.
                        A canceled job cannot be resumed.

    If no job_run_id is provided, the tool automatically targets the latest
    eligible job run for the requested action.

    PREREQUISITES:
    - The metadata import asset must exist in the project
    - There must be an eligible job run for the requested action

    ERROR HANDLING:
    - If project not found: Use 'list_containers' to find available projects
    - If metadata import not found: Use 'search_metadata_import' to find available MDIs
    - If no eligible job run: Use 'execute_metadata_import' to start a new job run
    - If job is in wrong state for the action: Check current state and choose the correct action

    Returns: Confirmation message, job details, resulting state, and UI URL.""",
    tags={"metadata-import", "job-control","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "metadata-import"},
)
@auto_context
async def pause_resume_or_cancel_mdi_job_run(
    project_name: Annotated[str, Field(description=DESC_PROJECT_NAME)],
    metadata_import_name: Annotated[str, Field(description=DESC_METADATA_IMPORT_NAME)],
    action: Annotated[Literal["pause", "resume", "cancel"], Field(description=DESC_ACTION)],
    job_run_id: Annotated[Optional[str], Field(description=DESC_JOB_RUN_ID)] = None,
) -> PauseResumeOrCancelMdiJobRunResponse:
    """Pause, resume, or cancel a metadata import job run."""
    return await _pause_resume_or_cancel_mdi_job_run(PauseResumeOrCancelMdiJobRunRequest(
        project_name=project_name,
        metadata_import_name=metadata_import_name,
        action=action,
        job_run_id=job_run_id,
    ))

# Made with Bob
