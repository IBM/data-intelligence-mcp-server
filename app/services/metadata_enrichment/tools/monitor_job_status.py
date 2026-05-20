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
    name="monitor_job_status",
    description="""Monitors a given job's status in a given project."

                This tool checks the job status, it accepts:
                - job_id: the job id of the job to check
                - project: the project id or project name
                """,
)
@auto_context
async def monitor_job_status(job_id: str, project: str) -> JobRunStatus:

    return await _monitor_job_status(job_id, project)
