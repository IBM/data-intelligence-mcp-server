# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Tool for checking the status of a glossary CSV import process."""

from fastmcp import Context

from app.core.registry import service_registry
from app.core.settings import settings
from app.services.glossary.models.import_status import (
    ImportGlossaryStatusResult,
    ImportStatusApiResponse,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.glossary_import_utils import (
    build_failed_error_message,
    build_warning_messages,
    count_operations,
    log_children_statuses,
)
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.glossary.constants import (
    GLOSSARY_IMPORT_STATUS_ENDPOINT
)
from typing import Annotated
from pydantic import Field


@service_registry.tool(
    name="import_glossary_status",
    description="""Check the status of a glossary CSV import process.

Returns:
- Current status of the import
- Counts of created/modified artifacts
- Any errors that occurred

Status values:
- SUCCEEDED: Import completed successfully
- COMPLETED: Import completed (alternative success state)
- FAILED: Import failed with errors
- ERROR: Import encountered an error
- TIMEOUT: Import timed out
- IN_PROGRESS: Import still running""",
    annotations={
        "readOnlyHint": True,
        "title": "Check the Status of a Glossary Import Process"
    },
    tags={"metadata_management_and_governance"}
)
@auto_context
async def import_glossary_status(
    process_id: Annotated[str, Field(description="process_id for on going glossary import")],
    ctx: Context | None = None,
) -> ImportGlossaryStatusResult:
    LOGGER.info(f"import_glossary_status called for process_id={process_id}")

    try:
        url = f"{settings.di_service_url}{GLOSSARY_IMPORT_STATUS_ENDPOINT}/{process_id}"

        raw_response = await tool_helper_service.execute_get_request(
            url=url,
            tool_name="import_glossary_status",
        )

        status_response = ImportStatusApiResponse.model_validate(raw_response)
        warning_messages: list[str] = []
        error_message: str | None = None

        if status_response.children_statuses:
            log_children_statuses(status_response.children_statuses)

        operations_by_type: dict[str, dict[str, int]] = {}
        if status_response.operations_count:
            operations_by_type = count_operations(status_response.operations_count, "glossary")

        # Handle completion statuses
        if status_response.status == "SUCCEEDED":
            warning_messages = build_warning_messages(
                "glossary",
                process_id,
                status_response.operations_count,
                status_response.messages,
            )
        elif status_response.status == "FAILED":
            error_message = build_failed_error_message(
                "glossary",
                status_response.step_number,
                status_response.step_message,
                status_response.children_statuses,
                status_response.operations_count,
            )

        result = ImportGlossaryStatusResult(
            process_id=process_id,
            workflow_id=status_response.workflow_id,
            status=status_response.status,
            step_number=status_response.step_number,
            step_message=status_response.step_message,
            total_steps=status_response.total_steps,
            operations_by_type=operations_by_type,
            warning_msgs=warning_messages,
            error_message=error_message,
        )

        LOGGER.info(f"import_glossary_status: status={status_response.status}")
        return result

    except ServiceError:
        raise
    except Exception as e:
        raise ServiceError(f"Failed to get import_glossary_status: {e!s}")