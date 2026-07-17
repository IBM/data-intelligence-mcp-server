from typing import Annotated

from pydantic import Field
from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import JobRunStatus
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import call_get_job_status
from app.services.tool_utils import find_project_id
from app.shared.logging import auto_context
from app.shared.utils.helpers import confirm_uuid


async def _monitor_job_status(job_id: str, project: str) -> JobRunStatus:
    project_id = await confirm_uuid(project, find_project_id)

    return await call_get_job_status(job_id, project_id)


@service_registry.tool(
    name="get_metadata_enrichment_job_status",
    annotations={
        "readOnlyHint": True,
        "title": "Get Metadata Enrichment Job Execution Status"
    },
    description="""Use this tool when you need to monitors a given job's status in a given project."

                This tool checks the job status, it accepts:
                - job_id: the job id of the job to check
                - project: the project id or project name
                Return: The current job run status and the job run/asset ID.
                """,
)
@auto_context
async def get_metadata_enrichment_job_status(
    job_id: Annotated[str, Field(description="The unique identifier of the metadata enrichment job.")],
    project: Annotated[str, Field(description="The name or ID of the project containing the job")],
) -> JobRunStatus:

    return await _monitor_job_status(job_id, project)
