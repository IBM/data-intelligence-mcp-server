# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset and Workflow APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.


from functools import partial
from typing import Any, Optional
from string import Template

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    TermGenerationRequest,
    TermGenerationResult,
    MetadataEnrichmentResult,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    MDE_UI_URL_TEMPLATE,
    TASK_INBOX_UI_URL_TEMPLATE,
    call_term_generation_on_metadata_enrichment_asset,
    find_data_asset_ids_for_mde_id,
    find_mdes_for_project_id,
    get_workflow_ids_from_project_id,
    get_draft_terms_from_workflow_ids,
    process_mdes_for_user_message,
    get_governance_base_url,
)
from app.services.tool_utils import (
    find_metadata_enrichment_id,
    find_project_id,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import confirm_uuid


@service_registry.tool(
    name="execute_term_generation",
    description="""Executes term generation on an existing metadata enrichment asset within a specified project.

    This tool executes term generation on an metadata enrichment asset (MDE), running for all the data assets and data asset columns that are associated with the metadata enrichment asset.
    This tool has two modes depending on if a metadata_enrichment_name was provided by the user:
    - If the metadata_enrichment_name IS NOT provided, the tool will get all the MDEs in the project and return this information back to the user. The user is then instructred to choose an MDE to run term generation on.
    - If the metadata_enrichment_name IS provided, the tool will get all the associated data assets to the MDE and run term generation on them in batches.

    metadata_enrichment_name IS NOT provided:
    - Requires: project_identifier
    - Searches for MDEs in the project and extracts relevant data.
    - Gets the data assets associated with the MDE and returns: 
        1. A list of objectives
        2. The name of the MDE
        3. The id of the associated data assets, the count of missing terms, published terms and draft terms
    - Returns MetadataEnrichmentResult with details of each MDE found in the project. Provide all details of the MDE in a user friendly format such as a table.

    metadata_enrichment_name IS provided:
    - Requires: project_identifier, metadata_enrichment_name
    - Gets all the data assets associated with the MDE
    - Gets a count of how many draft terms are currently in the workflow, prior to running term generation
    - Executes term generation in batches on the data assets, if there are any failures these are reported back to the user
    - Gets a count of how many draft terms are now in the workflow, after running term generation
    - Returns TermGenerationResult with the count of term generated, the failed term generation attempts and URLs to the UI. Provide the response in a user friendly format such as a table""",
)
@auto_context
async def execute_term_generation(
    request: TermGenerationRequest,
) -> TermGenerationResult | MetadataEnrichmentResult:

    LOGGER.info(
        f"term_generation called with project_name: {request.project_name}, "
        f"metadata_enrichment_asset_name: {request.metadata_enrichment_name}"
    )

    project_id = await confirm_uuid(request.project_name, find_project_id)
    LOGGER.info(f"Found project with ID: {project_id}")

    if request.metadata_enrichment_name is None:
        mdes_in_project = await find_mdes_for_project_id(project_id)
        LOGGER.info(f"Number of Metadata Enrichment assets found in project: {len(mdes_in_project)}")

        mde_info, failed_mde_ids = await process_mdes_for_user_message(mdes_in_project, project_id)
        LOGGER.info(f"Number of Metadata Enrichment assets processed in project: {len(mde_info)}")
        
        if failed_mde_ids:
            LOGGER.warning(f"Failed to process {len(failed_mde_ids)} metadata enrichment assets: {failed_mde_ids}")
        
        return MetadataEnrichmentResult(
            metadata_enrichments=mde_info,
            message="Please specify which Metadata Enrichment Term Generation should run against",
            failures=failed_mde_ids if failed_mde_ids else None
        )

    metadata_enrichment_id = await confirm_uuid(
        request.metadata_enrichment_name,
        partial(find_metadata_enrichment_id, project_id=project_id)
    )
    LOGGER.info(f"Found MDE with ID: {metadata_enrichment_id}")

    data_asset_ids = await find_data_asset_ids_for_mde_id(metadata_enrichment_id, project_id)
    LOGGER.info(f"Found data assets with IDs: {data_asset_ids}")

    workflow_ids_before_term_generation = await get_workflow_ids_from_project_id(project_id)
    draft_terms_before_term_generation = await get_draft_terms_from_workflow_ids(workflow_ids_before_term_generation)
    
    term_generation_responses = await call_term_generation_on_metadata_enrichment_asset(project_id, metadata_enrichment_id, data_asset_ids)
    LOGGER.info(f"Term generation completed successfully for {len(term_generation_responses.successes)} assets and failed for {len(term_generation_responses.failures)} assets")
    
    workflow_ids_after_term_generation = await get_workflow_ids_from_project_id(project_id)
    draft_terms_after_term_generation = await get_draft_terms_from_workflow_ids(workflow_ids_after_term_generation)

    count_of_draft_terms_from_term_generation = len(draft_terms_after_term_generation) - len(draft_terms_before_term_generation)
    LOGGER.info(f"Count of draft terms generated from running term generation: {count_of_draft_terms_from_term_generation}")

    mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
        mde_id=metadata_enrichment_id, project_id=project_id
    )

    task_inbox_url = Template(TASK_INBOX_UI_URL_TEMPLATE).substitute(
        governance_base=get_governance_base_url()
    )

    return TermGenerationResult(
        metadata_enrichment_name=request.metadata_enrichment_name,
        project_name=request.project_name,
        metadata_enrichment_ui_url=mde_url,
        task_inbox=task_inbox_url,
        failures=term_generation_responses.failures,
        count_of_draft_terms_from_term_generation=count_of_draft_terms_from_term_generation
    )


@service_registry.tool(
    name="execute_term_generation",
    description="""Executes term generation on an existing metadata enrichment asset within a specified project.

    This tool executes term generation on an metadata enrichment asset (MDE), running for all the data assets and data asset columns that are associated with the metadata enrichment asset.
    This tool has two modes depending on if a metadata_enrichment_name was provided by the user:
    - If the metadata_enrichment_name IS NOT provided, the tool will get all the MDEs in the project and return this information back to the user. The user is then instructred to choose an MDE to run term generation on.
    - If the metadata_enrichment_name IS provided, the tool will get all the associated data assets to the MDE and run term generation on them in batches.

    metadata_enrichment_name IS NOT provided:
    - Requires: project_identifier
    - Searches for MDEs in the project and extracts relevant data.
    - Gets the data assets associated with the MDE and returns: 
        1. A list of objectives
        2. The name of the MDE
        3. The id of the associated data assets, the count of missing terms, published terms and draft terms
    - Returns MetadataEnrichmentResult with details of each MDE found in the project. Provide all details of the MDE in a user friendly format such as a table.

    metadata_enrichment_name IS provided:
    - Requires: project_identifier, metadata_enrichment_name
    - Gets all the data assets associated with the MDE
    - Gets a count of how many draft terms are currently in the workflow, prior to running term generation
    - Executes term generation in batches on the data assets, if there are any failures these are reported back to the user
    - Gets a count of how many draft terms are now in the workflow, after running term generation
    - Returns TermGenerationResult with the count of term generated, the failed term generation attempts and URLs to the UI. Provide the response in a user friendly format such as a table""",
)
@auto_context
async def wxo_execute_term_generation(
    project_name: str,
    metadata_enrichment_name: Optional[str] = None,
) -> TermGenerationResult | MetadataEnrichmentResult:
    """Watsonx Orchestrator compatible version that expands TermGenerationRequest into individual parameters."""

    request = TermGenerationRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
    )
    return await execute_term_generation(request)