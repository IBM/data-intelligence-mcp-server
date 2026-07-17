from typing import Optional, Annotated

from pydantic import Field

from app.core.registry import service_registry
from app.services.metadata_enrichment.constants import CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME
from app.services.metadata_enrichment.models.metadata_enrichment import MetadataEnrichmentAssetEnrichmentJobResponse
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import call_create_or_update_metadata_enrichment_asset_jobs
from app.shared.exceptions.base import ServiceError, ValidationError
from app.shared.logging import auto_context


async def _create_or_metadata_enrichment_asset_jobs(
        project_name: str,
        metadata_enrichment_name: str,
        job_name: str,
        category_names: list[str] |str,
        objectives: list[str] | str,
        job_description: Optional[str],
        primary_category_name: Optional[str]
) -> MetadataEnrichmentAssetEnrichmentJobResponse:
    if not project_name:
        raise ValidationError(
            message="Project name is required",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
            remediation_steps="Please provide project name",
        )
    if not metadata_enrichment_name:
        raise ValidationError(
            message="Metadata enrichment name is required",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
            remediation_steps="Please provide metadata enrichment name",
        )
    if not job_name:
        raise ValidationError(
            message="Job name is required",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
            remediation_steps="Please provide a job name",
        )
    if len(category_names) == 0:
        raise ValidationError(
            message="At least one category is required",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
            remediation_steps="Please provide at least one category name",
        )
    if len(objectives) == 0:
        raise ValidationError(
            message="At least one objective is required",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
            remediation_steps="Please provide at least one objective name",
        )

    return await call_create_or_update_metadata_enrichment_asset_jobs(
        project_name,
        metadata_enrichment_name,
        job_name,
        category_names,
        objectives,
        job_description,
        primary_category_name)


@service_registry.tool(
    name=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
    description="""Creates or update metadata enrichment jobs within a specified project for a specific Metadata Enrichment (MDE)
    If the job exists by name (using exact match), the tool will update the existing job otherwise it will create a new job.
    
    **IMPORTANT:**
    - The user must select at least one objective
    - The user must provide category_names
    - If the categry_names are not provided use the 'list_enrichment_categories' tool to find the list of the available categories.
    - Return the **FULL** list to the user and ask him to choose one or more categories to be used to create or update the MDE.
    - Do not assume or select categories, the user MUST choose.
    
    The objectives is the list of names of objectives used in the enrichment job.
    Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality', 'assign_terms',
    'analyze_relationships', 'dq_sla_assessment', 'semantic_expansion', and 'data_search'.
    """,
    annotations={
        "title": "Create or update a MDE job",
        "destructiveHint": True
    }
)
@auto_context
async def create_or_update_metadata_enrichment_asset_jobs(
        project_name: Annotated[str, Field(description="The name of the project.")],
        metadata_enrichment_name: Annotated[str, Field(description="The name of the metadata enrichment asset.")],
        job_name: Annotated[str, Field(description="The name of the job.")],
        objectives: Annotated[list[str] | str, Field(description="""List of names of objectives for the enrichment job.
                                                      Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality', 'assign_terms', 'analyze_relationships', 'dq_sla_assessment', 'semantic_expansion', and 'data_search'.""")],
        category_names: Annotated[list[str] | str, Field(description="""Category names for governance scope.""")],
        job_description: Optional[str] = None,
        primary_category_name: Annotated[Optional[str], Field(description="Identifier of the category that is used to store generated terms.")] = None,
) -> MetadataEnrichmentAssetEnrichmentJobResponse:

    return await _create_or_metadata_enrichment_asset_jobs(
        project_name,
        metadata_enrichment_name,
        job_name,
        category_names,
        objectives,
        job_description,
        primary_category_name
    )
