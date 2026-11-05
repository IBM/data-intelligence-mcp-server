# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Glossary CSV import utilities for the glossary curator.

Provides the result model, the async import function, and the polling
function that together cover the full import lifecycle:
  1. ``import_csv_file`` — POST the CSV to the IKC import endpoint.
  2. ``poll_import_status`` — poll until the job completes or times out.
"""

import asyncio
import io
import time

from pydantic import BaseModel, Field

from app.core.settings import settings
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service

_IMPORT_STATUS_ENDPOINT = "/v3/governance_artifact_types/import/status"
_COMPLETION_STATUSES = {"SUCCEEDED", "FAILED", "COMPLETED", "CANCELED"}
_DEFAULT_POLL_MAX_WAIT = 3300  # seconds (55 minutes)
_DEFAULT_POLL_INTERVAL = 5.0  # seconds

# GIM codes that are informational notices, not genuine per-term failures.
# GIM00103E fires on every import that contains Business Start/End date columns and does not indicate failure.
# GIM00013E fires when a column is unrecgonised which creates unnessary warnings for the user with the after-csv as it contains specific columns for review that are not imported
_INFORMATIONAL_CODES = frozenset({"GIM00103E", "GIM00013E"})


class ImportRowError(BaseModel):
    """A single per-term error entry returned by the IKC import status API."""

    code: str = Field(default="", description="GIM error code, e.g. GIM00010E")
    error_message: str = Field(
        default="", description="Full error message from the API"
    )
    term_name: str = Field(
        default="", description="Term name extracted from parameters[1], if available"
    )
    line_number: int = Field(
        default=0, description="1-based CSV row number from locations[0].line_number"
    )


class ImportStatusResult(BaseModel):
    """Result of a glossary CSV import operation."""

    process_id: str = Field(default="", description="Import process identifier")
    workflow_id: str = Field(
        default="", description="Workflow ID from the import status response"
    )
    status: str = Field(
        ..., description="Current status (SUCCEEDED, FAILED, IN_PROGRESS, etc.)"
    )
    categories_created: int = Field(0)
    terms_created: int = Field(0)
    categories_updated: int = Field(0)
    terms_updated: int = Field(0)
    errors: list[ImportRowError] = Field(
        default_factory=list,
        description="List of error objects with an error_message field",
    )


def _parse_import_result(process_id: str, response: dict) -> ImportStatusResult:
    """Build an :class:`ImportStatusResult` from a completed status response."""
    ops = response.get("operations_count", {})

    errors: list[ImportRowError] = []
    for resource in response.get("messages", {}).get("resources", []):
        code = resource.get("code", "")
        msg = resource.get("message", "")
        if not msg:
            continue
        if code in _INFORMATIONAL_CODES:
            LOGGER.info("Skipping informational import message code=%s: %s", code, msg)
            continue
        params = resource.get("parameters", [])
        locations = resource.get("locations", [])
        # parameters[1] is the term name for row-level errors (e.g. GIM00010E).
        # parameters[0] is used for header-level errors — no meaningful term name there.
        term_name = params[1] if len(params) >= 2 else ""  # noqa: PLR2004 # Baseline
        line_number = locations[0].get("line_number", 0) if locations else 0
        errors.append(
            ImportRowError(
                code=code,
                error_message=msg,
                term_name=term_name,
                line_number=line_number,
            )
        )

    return ImportStatusResult(
        process_id=process_id,
        workflow_id=response.get("workflow_id", ""),
        status=response.get("status", "UNKNOWN"),
        categories_created=ops.get("category", {}).get("IMPORT_CREATE", 0),
        categories_updated=ops.get("category", {}).get("IMPORT_MODIFY", 0),
        terms_created=ops.get("glossary_term", {}).get("IMPORT_CREATE", 0),
        terms_updated=ops.get("glossary_term", {}).get("IMPORT_MODIFY", 0),
        errors=errors,
    )


async def poll_import_status(process_id: str) -> ImportStatusResult:
    """Poll the IKC import status endpoint until the job completes or times out.

    Args:
        process_id: The process ID returned by the import API.

    Returns:
        :class:`ImportStatusResult` with final counts and any errors.

    Raises:
        TimeoutError: If the job does not complete within ``_DEFAULT_POLL_MAX_WAIT`` seconds.
    """
    url = f"{settings.di_service_url}{_IMPORT_STATUS_ENDPOINT}/{process_id}"
    start = time.monotonic()

    LOGGER.info(f"[import_utils] Polling import status for process_id={process_id}")

    while True:
        elapsed = time.monotonic() - start
        if elapsed >= _DEFAULT_POLL_MAX_WAIT:
            raise TimeoutError(
                f"Import process timed out after {_DEFAULT_POLL_MAX_WAIT}s. "
                f"process_id={process_id}"
            )

        try:
            response = await tool_helper_service.execute_get_request(
                url=url,
                headers={},
                params={},
                tool_name="glossary_curator",
            )
            status = response.get("status", "UNKNOWN")
            LOGGER.info(
                f"[import_utils] process_id={process_id} status={status} elapsed={elapsed:.1f}s"
            )
            if status in _COMPLETION_STATUSES:
                return _parse_import_result(process_id, response)

        except Exception as exc:
            LOGGER.warning(f"[import_utils] Poll error (will retry): {exc}")
            if time.monotonic() - start >= _DEFAULT_POLL_MAX_WAIT:
                raise

        await asyncio.sleep(_DEFAULT_POLL_INTERVAL)


_IMPORT_TERM_ENDPOINT = "/v3/governance_artifact_types/glossary_term/import"


async def import_csv_file(
    csv_content: str, merge_option: str = "all"
) -> ImportStatusResult:
    """POST a glossary CSV to the IKC import endpoint and poll until complete."""
    LOGGER.info("Attempting CSV file import")

    csv_bytes = csv_content.encode("utf-8")
    files = {"file": ("glossary_import.csv", io.BytesIO(csv_bytes), "text/csv")}
    params = {
        "merge_option": merge_option,
        "async_mode": "true",
    }

    response = await tool_helper_service.execute_post_request(
        url=f"{settings.di_service_url}{_IMPORT_TERM_ENDPOINT}",
        headers={},
        files=files,
        tool_name="glossary_curator",
        params=params,
    )

    if not isinstance(response, dict):
        raise ServiceError(f"Unexpected response type: {type(response)}")

    process_id = response.get("process_id") or response.get("processId")
    if not process_id:
        raise ServiceError("process_id not found")
    LOGGER.info(f"glossary_curation import started with process_id: {process_id}")

    return await poll_import_status(process_id)
