# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Shared utilities for MDI job control operations (pause, resume, cancel)."""

from string import Template  # noqa: I001 # Baseline
from typing import Any, Dict, Optional, Tuple  # noqa: UP035 # Baseline
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.helpers import confirm_uuid, append_context_to_url
from app.shared.exceptions.base import ServiceError
from app.services.tool_utils import find_project_id, find_metadata_import_id


# Job states
JOB_STATE_RUNNING = "Running"
JOB_STATE_PAUSED = "Paused"
JOB_STATE_COMPLETED = "Completed"
JOB_STATE_FAILED = "Failed"
JOB_STATE_CANCELED = "Canceled"
JOB_STATE_QUEUED = "Queued"

# Active states that can be controlled
ACTIVE_JOB_STATES = [JOB_STATE_RUNNING, JOB_STATE_PAUSED, JOB_STATE_QUEUED]


async def find_latest_job_run_id(
    job_id: str,
    project_id: str,
    target_states: list[str] | None = None,
) -> Tuple[str, str]:  # noqa: UP006 # Baseline
    """
    Find the latest job run for a metadata import job that matches the target states.

    Args:
        job_id: The ID of the metadata import job
        project_id: The ID of the project containing the job
        target_states: States to search for. Defaults to ACTIVE_JOB_STATES when None.
                       Pass a specific subset (e.g. [JOB_STATE_PAUSED]) to filter by
                       the states relevant to the requested action.

    Returns:
        Tuple[str, str]: A tuple containing (job_run_id, current_state)

    Raises:
        ServiceError: If no matching job run is found or if the API call fails
    """
    states = target_states or ACTIVE_JOB_STATES
    LOGGER.info(
        "Finding latest job run in states %s: job_id=%s, project_id=%s",
        states,
        job_id,
        project_id,
    )

    get_url = f"{tool_helper_service.base_url}/v2/jobs/{job_id}/runs"
    query_params = {
        "project_id": project_id,
        "limit": 1,
        "target_states": states,
    }

    try:
        response = await tool_helper_service.execute_get_request(
            url=get_url,
            params=query_params,
        )

        results = response.get("results", [])

        if results:
            job_run = results[0]
            job_run_id = job_run.get("metadata", {}).get("asset_id")
            state = job_run.get("entity", {}).get("job_run", {}).get("state")
            LOGGER.info(
                "Found job run in target state: job_run_id=%s, state=%s",
                job_run_id,
                state,
            )
            return job_run_id, state

        LOGGER.warning(
            "No job run found in states %s for job_id=%s.",
            states,
            job_id,
        )
        raise ServiceError(
            f"No job run found in states {states} for job '{job_id}'. "
            "All recent job runs may be in a different state.",
            remediation_steps=(
                "Check the current state of the job runs. "
                "For 'resume', the job must be Paused. "
                "For 'pause', the job must be Running. "
                "For 'cancel', the job must be Running, Paused, or Queued. "
                "Use 'execute_metadata_import' to start a new run if needed."
            ),
        )

    except ServiceError:
        raise
    except Exception as e:
        LOGGER.error(
            "Failed to find latest job run: job_id=%s, error=%s",
            job_id,
            str(e),
        )
        raise ServiceError(  # noqa: B904 # Baseline
            f"Failed to retrieve job runs for job '{job_id}': {e!s}",
            remediation_steps=(
                "Verify the project_name and metadata_import_name are correct. "
                "Use 'search_metadata_import' to list available MDIs in the project."
            ),
        )


async def get_job_run_state(job_id: str, job_run_id: str, project_id: str) -> str:
    """
    Get the current state of a specific job run.

    Args:
        job_id: The ID of the metadata import job
        job_run_id: The ID of the specific job run
        project_id: The ID of the project containing the job

    Returns:
        str: The current state of the job run

    Raises:
        ServiceError: If the job run is not found or if the API call fails

    Example:
        >>> state = await get_job_run_state("job-123", "run-456", "proj-789")
        >>> print(f"Job run state: {state}")
    """
    LOGGER.info(
        "Getting job run state: job_id=%s, job_run_id=%s, project_id=%s",
        job_id,
        job_run_id,
        project_id,
    )

    get_url = f"{tool_helper_service.base_url}/v2/jobs/{job_id}/runs/{job_run_id}"
    query_params = {
        "project_id": project_id,
    }

    try:
        response = await tool_helper_service.execute_get_request(
            url=get_url,
            params=query_params,
        )

        state = response.get("entity", {}).get("job_run", {}).get("state")

        if state:
            LOGGER.info("Job run state: %s", state)
            return state
        raise ServiceError(
            f"Could not determine state for job run '{job_run_id}'.",
            remediation_steps=(
                "Verify the job_run_id is valid. "
                "Use 'search_metadata_import' to find the MDI and confirm job details."
            ),
        )

    except ServiceError:
        raise
    except Exception as e:
        LOGGER.error(
            "Failed to get job run state: job_run_id=%s, error=%s",
            job_run_id,
            str(e),
        )
        raise ServiceError(  # noqa: B904 # Baseline
            f"Failed to retrieve state for job run '{job_run_id}': {e!s}",
            remediation_steps=(
                "Verify the job_run_id is correct. "
                "Use 'search_metadata_import' to find the MDI and confirm available job runs."
            ),
        )


def validate_job_state_for_pause(current_state: str) -> None:
    """
    Validate that a job can be paused based on its current state.

    A job can only be paused if it's currently Running.
    """
    if current_state == JOB_STATE_PAUSED:
        raise ServiceError(
            f"Job is already paused (state: {current_state}).",
            remediation_steps=(
                "The job is already paused. "
                "Use 'pause_resume_or_cancel_mdi_job_run' with action='resume' to resume it."
            ),
        )
    if current_state in [JOB_STATE_COMPLETED, JOB_STATE_FAILED, JOB_STATE_CANCELED]:
        raise ServiceError(
            f"Cannot pause a job that is {current_state}. "
            "Only Running jobs can be paused.",
            remediation_steps=(
                f"The job has already finished ({current_state}). "
                "Use 'execute_metadata_import' to start a new run."
            ),
        )
    if current_state != JOB_STATE_RUNNING:
        raise ServiceError(
            f"Cannot pause job in state '{current_state}'. "
            "Only Running jobs can be paused.",
            remediation_steps=(
                "Check the current state of the job. Only Running jobs can be paused."
            ),
        )


def validate_job_state_for_resume(current_state: str) -> None:
    """
    Validate that a job can be resumed based on its current state.

    A job can only be resumed if it's currently Paused.
    """
    if current_state == JOB_STATE_RUNNING:
        raise ServiceError(
            f"Job is already running (state: {current_state}).",
            remediation_steps=(
                "The job is currently running and does not need to be resumed. "
                "Use 'pause_resume_or_cancel_mdi_job_run' with action='pause' to pause it if needed."
            ),
        )
    if current_state in [JOB_STATE_COMPLETED, JOB_STATE_FAILED, JOB_STATE_CANCELED]:
        raise ServiceError(
            f"Cannot resume a job that is {current_state}. "
            "Only Paused jobs can be resumed.",
            remediation_steps=(
                f"The job has already finished ({current_state}). "
                "Use 'execute_metadata_import' to start a new run."
            ),
        )
    if current_state != JOB_STATE_PAUSED:
        raise ServiceError(
            f"Cannot resume job in state '{current_state}'. "
            "Only Paused jobs can be resumed.",
            remediation_steps=(
                "Check the current state of the job. Only Paused jobs can be resumed."
            ),
        )


def validate_job_state_for_cancel(current_state: str) -> None:
    """
    Validate that a job can be canceled based on its current state.

    A job can be canceled if it's Running, Paused, or Queued.
    """
    if current_state == JOB_STATE_CANCELED:
        raise ServiceError(
            f"Job is already canceled (state: {current_state}).",
            remediation_steps=(
                "The job is already canceled. "
                "Use 'execute_metadata_import' to start a new run."
            ),
        )
    if current_state in [JOB_STATE_COMPLETED, JOB_STATE_FAILED]:
        raise ServiceError(
            f"Cannot cancel a job that is {current_state}. "
            "Only Running, Paused, or Queued jobs can be canceled.",
            remediation_steps=(
                f"The job has already finished ({current_state}). "
                "No cancel action is needed."
            ),
        )
    if current_state not in ACTIVE_JOB_STATES:
        raise ServiceError(
            f"Cannot cancel job in state '{current_state}'. "
            "Only Running, Paused, or Queued jobs can be canceled.",
            remediation_steps=(
                "Check the current state of the job. "
                "Only Running, Paused, or Queued jobs can be canceled."
            ),
        )


UI_JOB_RUN_URL_TEMPLATE = (
    "/gov/metadata-imports/jobs/runs"
    "?project_id=${project_id}&job_id=${job_id}&jobrun_id=${jobrun_id}"
)


async def resolve_job_run_ids(
    project_name: str,
    metadata_import_name: str,
    job_run_id: Optional[str],  # noqa: UP045 # Baseline
    find_job_id_in_mdi,  # noqa: ANN001 # Baseline
    target_states: list[str] | None = None,
) -> Tuple[str, str, str, str, str]:  # noqa: UP006 # Baseline
    """
    Resolve all IDs needed for a job control operation.

    Args:
        project_name: Name or ID of the project
        metadata_import_name: Name or ID of the metadata import
        job_run_id: Specific job run ID, or None to auto-find
        find_job_id_in_mdi: Callable to find the job ID from the MDI
        target_states: Eligible states for auto-discovery. When job_run_id is None,
                       only runs in these states are considered. Defaults to ACTIVE_JOB_STATES.

    Returns:
        Tuple of (project_id, metadata_import_id, job_id, job_run_id, current_state)
    """
    project_id = await confirm_uuid(project_name, find_project_id)
    metadata_import_id = await find_metadata_import_id(metadata_import_name, project_id)
    LOGGER.info(
        "Found metadata import: metadata_import_id=%s, project_id=%s",
        metadata_import_id,
        project_id,
    )

    job_id = await find_job_id_in_mdi(metadata_import_id, project_id)

    if job_run_id:
        current_state = await get_job_run_state(job_id, job_run_id, project_id)
        LOGGER.info(
            "Using provided job_run_id=%s with state=%s", job_run_id, current_state
        )
    else:
        job_run_id, current_state = await find_latest_job_run_id(
            job_id, project_id, target_states
        )
        LOGGER.info("Found job run: job_run_id=%s, state=%s", job_run_id, current_state)

    return project_id, metadata_import_id, job_id, job_run_id, current_state


async def fetch_job_run_details(
    job_id: str, job_run_id: str, project_id: str
) -> Tuple[Dict[str, Any], str, str]:  # noqa: UP006 # Baseline
    """
    Fetch job run details after a control operation and build the UI URL.

    Returns:
        Tuple of (job_run_data, new_state, ui_url)
    """
    get_url = f"{tool_helper_service.base_url}/v2/jobs/{job_id}/runs/{job_run_id}"
    job_run_data: Dict[str, Any] = await tool_helper_service.execute_get_request(  # noqa: UP006 # Baseline
        url=get_url,
        params={"project_id": project_id},
    )
    # NOTE: "Unknown" is a safe non-empty fallback; the operation itself succeeded.
    # The UI URL in the response provides the authoritative live state.
    new_state = (
        job_run_data.get("entity", {}).get("job_run", {}).get("state", "Unknown")
    )
    ui_base = str(tool_helper_service.ui_base_url)
    url = Template(ui_base + UI_JOB_RUN_URL_TEMPLATE).substitute(
        job_id=job_id, jobrun_id=job_run_id, project_id=project_id
    )
    return job_run_data, new_state, append_context_to_url(url)


# Made with Bob
