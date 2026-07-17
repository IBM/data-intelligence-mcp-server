from functools import partial
from typing import Annotated

from pydantic import Field

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import MetadataEnrichmentAssetEnrichmentJobResponse
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import get_metadata_enrichment_asset_jobs
from app.services.tool_utils import find_project_id, find_metadata_enrichment_id
from app.shared.exceptions.base import ServiceError
from app.shared.logging import auto_context
from app.shared.utils.helpers import confirm_uuid
from app.shared.utils.http_client import LOGGER


async def _list_metadata_enrichment_asset_jobs(
        project_name: str,
        metadata_enrichment_name: str
) -> list[MetadataEnrichmentAssetEnrichmentJobResponse]:
    try:
        project_id = await confirm_uuid(project_name, find_project_id)
        metadata_enrichment_id = await confirm_uuid(
            metadata_enrichment_name,
            partial(find_metadata_enrichment_id, project_id=project_id)
        )
        LOGGER.info(f"Found project ID: {project_id} and metadata enrichment ID: {metadata_enrichment_id}")

        return await get_metadata_enrichment_asset_jobs(project_id, metadata_enrichment_id)
    except ServiceError:
        LOGGER.info(f"MDE '{metadata_enrichment_name}' not found.")
    return []

@service_registry.tool(
    name="list_metadata_enrichment_asset_jobs",
    description="""
    Lists all metadata enrichment jobs for a given metadata enrichment asset.
    The tool retrieves the list of all the available jobs for a given metadata enrichment asset.
    The user should provide the MDE name or its UUID and the project name or its UUID.
    The tool will return a list of job details: id, name, description, schedule_info, objectives, categories, ... or an empty list if no job is defined.
    For the user only show the name, description and the ID of the job
    """,
    annotations={
        "title": "List all metadata enrichment jobs for a given project",
        "destructiveHint": True
    }
)
@auto_context
async def list_metadata_enrichment_asset_jobs(
        project_name: Annotated[str, Field(description="The name of the project.")],
        metadata_enrichment_name: Annotated[str, Field(description="The name of the metadata enrichment asset.")],
) -> list[MetadataEnrichmentAssetEnrichmentJobResponse]:

    return await _list_metadata_enrichment_asset_jobs(project_name, metadata_enrichment_name)