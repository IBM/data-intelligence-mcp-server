# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset and Workflow APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.


from functools import partial
from typing import Annotated, Optional
from string import Template

from pydantic import Field
from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    TermGenerationRequest,
    TermGenerationResult,
    MetadataEnrichmentResult,
    TermGenerationJobSelectionResult,
    CategorySelectionResult,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    MDE_UI_URL_TEMPLATE,
    TASK_INBOX_UI_URL_TEMPLATE,
    CATEGORY_UI_URL_TEMPLATE,
    find_data_asset_ids_for_mde_id,
    find_mdes_for_project_id,
    get_governance_base_url,
)
from app.services.metadata_enrichment.utils.term_generation_utils import (
    is_mde_v3,
    execute_term_generation_legacy,
    execute_term_generation_v3,
    resolve_target_category_v3,
)
from app.services.tool_utils import (
    find_metadata_enrichment_id,
    find_project_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import confirm_uuid


async def _list_mdes_with_data_assets(
    project_id: str
) -> MetadataEnrichmentResult:
    """
    List MDEs that have data assets with missing terms count.
    Uses process_mdes_for_user_message to get detailed asset information including missing terms.
    
    Args:
        project_id: The project ID to search for MDEs
        
    Returns:
        MetadataEnrichmentResult with MDE listing including missing terms count
    """
    LOGGER.info("Listing MDEs with data assets for project: %s", project_id)
    
    mdes_in_project = await find_mdes_for_project_id(project_id)
    LOGGER.info(f"Total MDEs found in project: {len(mdes_in_project)}")
    
    # Use process_mdes_for_user_message to get detailed info including missing terms
    from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
        process_mdes_for_user_message
    )
    
    mde_info, failed_mde_ids = await process_mdes_for_user_message(
        mdes_in_project,
        project_id
    )
    
    LOGGER.info(
        f"MDEs with data assets: {len(mde_info)}, "
        f"failed: {len(failed_mde_ids)}"
    )
    
    if not mde_info:
        message = (
            "No Metadata Enrichment assets with data assets found in this project. "
            "Please add data assets to an MDE before running term generation."
        )
    else:
        message = (
            "Select ONE Metadata Enrichment from the list below to run Term Generation on. "
            "Re-run the tool with metadata_enrichment_name parameter set to your selected MDE. "
            "DO NOT attempt to run on multiple MDEs simultaneously - only ONE MDE can be processed per execution. "
            "Only MDEs with data assets are shown."
        )
    
    return MetadataEnrichmentResult(
        metadata_enrichments=mde_info,
        message=message,
        failures=failed_mde_ids if failed_mde_ids else None
    )


async def _execute_term_generation(
    request: TermGenerationRequest,
) -> TermGenerationResult | MetadataEnrichmentResult | TermGenerationJobSelectionResult | CategorySelectionResult:
    """
    Main orchestration function for term generation.
    
    Handles:
    1. Project validation
    2. MDE listing (if no MDE name provided)
    3. MDE validation and data asset check
    4. Version detection (legacy vs v3)
    5. Routing to appropriate execution flow
    """
    LOGGER.info(
        f"term_generation called with project_name: {request.project_name}, "
        f"metadata_enrichment_name: {request.metadata_enrichment_name}, "
        f"job_name: {request.job_name}, category_name: {request.category_name}"
    )

    # Step 1: Validate project
    project_id = await confirm_uuid(request.project_name, find_project_id)
    LOGGER.info(f"Found project with ID: {project_id}")

    # Step 2: Handle MDE listing mode
    if request.metadata_enrichment_name is None:
        return await _list_mdes_with_data_assets(project_id)

    # Step 3: Get MDE ID
    metadata_enrichment_id = await confirm_uuid(
        request.metadata_enrichment_name,
        partial(find_metadata_enrichment_id, project_id=project_id)
    )
    LOGGER.info(f"Found MDE with ID: {metadata_enrichment_id}")

    # Step 4: Check if MDE has data assets
    data_asset_ids = await find_data_asset_ids_for_mde_id(
        metadata_enrichment_id, project_id
    )
    
    if not data_asset_ids:
        raise ServiceError(
            f"Cannot run term generation: MDE '{request.metadata_enrichment_name}' "
            f"has no data assets. Please add data assets to the MDE first."
        )
    
    LOGGER.info(f"Found {len(data_asset_ids)} data assets in MDE")

    # Step 5: Detect version and route
    is_v3 = await is_mde_v3(metadata_enrichment_id, project_id)
    
    if not is_v3:
        # Legacy flow
        LOGGER.info("Executing legacy term generation flow")
        term_generation_responses, count_of_draft_terms, category_id, category_name = await execute_term_generation_legacy(
            project_id, metadata_enrichment_id, data_asset_ids
        )
        
        # Build result
        mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
            mde_id=metadata_enrichment_id, project_id=project_id
        )
        task_inbox_url = Template(TASK_INBOX_UI_URL_TEMPLATE).substitute(
            governance_base=get_governance_base_url()
        )
        
        # Build category URL if category was configured in MDE
        category_url = None
        if category_id and category_name:
            category_url = Template(CATEGORY_UI_URL_TEMPLATE).substitute(
                governance_base=get_governance_base_url(),
                target_category_id=category_id
            )
            LOGGER.info(f"Legacy MDE used target category: {category_name} ({category_id})")
        
        return TermGenerationResult(
            metadata_enrichment_name=request.metadata_enrichment_name,
            project_name=request.project_name,
            metadata_enrichment_ui_url=mde_url,
            task_inbox=task_inbox_url,
            target_category_url=category_url,
            failures=term_generation_responses.failures,
            count_of_draft_terms_from_term_generation=count_of_draft_terms
        )
    
    else:
        # V3 flow
        LOGGER.info("Executing v3 term generation flow")
        
        # Resolve target category
        category_id, category_name, _, job_selection_result = await resolve_target_category_v3(
            mde_id=metadata_enrichment_id,
            project_id=project_id,
            mde_name=request.metadata_enrichment_name,
            project_name=request.project_name,
            job_name=request.job_name,
            category_name=request.category_name
        )
        
        # If job selection is needed, return that result
        if job_selection_result is not None:
            LOGGER.info("Returning job selection result for user input")
            return job_selection_result
        
        # At this point, category_id and category_name must be set
        if not category_id or not category_name:
            raise ServiceError(
                "Internal error: category_id and category_name must be set after resolution"
            )
        
        # Execute term generation with category
        LOGGER.info(f"Executing v3 term generation with category: {category_name} ({category_id})")
        term_generation_responses, count_of_draft_terms = await execute_term_generation_v3(
            project_id, metadata_enrichment_id, data_asset_ids, category_id
        )
        
        # Build result with category URL
        mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
            mde_id=metadata_enrichment_id, project_id=project_id
        )
        task_inbox_url = Template(TASK_INBOX_UI_URL_TEMPLATE).substitute(
            governance_base=get_governance_base_url()
        )
        
        # Build category URL using template (supports both SaaS and CPD)
        category_url = Template(CATEGORY_UI_URL_TEMPLATE).substitute(
            governance_base=get_governance_base_url(),
            target_category_id=category_id
        )
        
        return TermGenerationResult(
            metadata_enrichment_name=request.metadata_enrichment_name,
            project_name=request.project_name,
            metadata_enrichment_ui_url=mde_url,
            task_inbox=task_inbox_url,
            target_category_url=category_url,
            failures=term_generation_responses.failures,
            count_of_draft_terms_from_term_generation=count_of_draft_terms
        )


@service_registry.tool(
    name="run_term_generation",
    annotations={
        "title": "Execute Term Generation within a Specified Project",
        "destructiveHint": True
    },
    tags={"metadata_management_and_governance"},
    description="""Use this tool when you need to execute term generation on an existing metadata enrichment asset within a specified project.

    This tool executes term generation on a metadata enrichment asset (MDE), running for all data assets and columns associated with the MDE.
    It supports both legacy MDEs and new MDE v3 multi-job architecture.

    **MODES OF OPERATION:**

    **Mode 1: List MDEs (no metadata_enrichment_name provided)**
    - Requires: project_name
    - Lists all MDEs in the project that have data assets
    - Returns: MetadataEnrichmentResult with MDE details (name, data assets, URLs)
    - User should select ONE MDE from the list and re-run the tool
    - DO NOT offer to run on multiple MDEs simultaneously
    - **PRESENTATION**: Always format MDE listing as a markdown table with columns: MDE Name, Data Assets Count, Missing Terms, MDE URL

    **Mode 2: Execute on Legacy MDE**
    - Requires: project_name, metadata_enrichment_name
    - Detects legacy MDE (no "version": "v3" field)
    - Automatically extracts target category from MDE configuration (if configured)
    - Validates category exists in glossary
    - Executes term generation on all data assets with the configured category
    - Returns: TermGenerationResult with count of draft terms generated and category URL
    - NOTE: For legacy MDEs, the target category is pre-configured in the MDE asset settings.
      The tool automatically uses this category - DO NOT call list_glossary_categories
      or prompt user to select a category for legacy MDEs.
    - **PRESENTATION**: Always format results as a markdown table showing: MDE Name, Project, Draft Terms Generated, Target Category (with URL if available), Task Inbox URL, MDE URL

    **Mode 3: Execute on MDE v3 (Direct Mode)**
    - Requires: project_name, metadata_enrichment_name
    - Optional: job_name OR category_name (user provides target)
    - Detects MDE v3 (has "version": "v3" field)
    - If job_name provided: validates job exists and has target category configured
    - If category_name provided: validates category exists in glossary
    - Executes term generation with specified target category
    - Returns: TermGenerationResult with count of draft terms and category URL
    - **PRESENTATION**: Always format results as a markdown table showing: MDE Name, Project, Draft Terms Generated, Target Category (with URL), Task Inbox URL, MDE URL

    **Mode 4: Execute on MDE v3 (Interactive Mode)**
    - Requires: project_name, metadata_enrichment_name
    - No job_name or category_name provided
    - Lists all jobs in the MDE that have target categories configured
    - Returns: TermGenerationJobSelectionResult with job options
    - User should select ONE job from available_jobs OR provide a custom category_name
    - DO NOT offer to run on multiple jobs simultaneously
    - ALWAYS present the option to provide a custom category_name as an alternative
    - **PRESENTATION**: Always format job listing as a markdown table with columns: Job Name, Target Category

    **PARAMETERS:**
    - project_name (required): Name or UUID of the project
    - metadata_enrichment_name (optional): Name or UUID of the MDE
    - job_name (optional, v3 only): Name or UUID of the enrichment job to use
    - category_name (optional, v3 only): Name or UUID of the target glossary category

    **CRITICAL CONSTRAINTS:**
    - Only ONE MDE can be processed per tool execution
    - Only ONE job can be selected per tool execution
    - DO NOT create options to run on "all" MDEs or "all" jobs
    - ALWAYS present custom category option when listing jobs
    - Only MDEs with data assets are shown/processed (empty MDEs are automatically filtered out)
    - For MDE v3, term generation requires a target category to be specified
    - Job selection is only available for jobs that have target categories configured
    - Term names are LLM-generated and may vary between runs
    - The tool returns a delta count (new terms generated), not total terms
    
    **PRESENTATION REQUIREMENTS:**
    - ALWAYS use markdown tables for all results (MDE listings, job listings, execution results)
    - Include clickable URLs in table cells where applicable
    - Keep table formatting clean and aligned
    - Use clear, descriptive column headers""",
)
@auto_context
async def execute_term_generation(
    project_name: Annotated[str, Field(description="The name of the project you want to execute a metadata enrichment.")],
    metadata_enrichment_name: Annotated[Optional[str], Field(description="The name of the metadata enrichment asset to run on.")] = None,
    job_name: Annotated[Optional[str], Field(description="(v3 only) The name or UUID of the enrichment job to use for term generation. If not provided, the tool will list available jobs.")] = None,
    category_name: Annotated[Optional[str], Field(description="(v3 only) The name or UUID of the target glossary category where generated terms will be placed. If a category name matches multiple categories, you will be prompted to select one.")] = None,
) -> TermGenerationResult | MetadataEnrichmentResult | TermGenerationJobSelectionResult | CategorySelectionResult:
    """Wrapper that expands TermGenerationRequest into individual parameters."""

    request = TermGenerationRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
        job_name=job_name,
        category_name=category_name,
    )
    return await _execute_term_generation(request)