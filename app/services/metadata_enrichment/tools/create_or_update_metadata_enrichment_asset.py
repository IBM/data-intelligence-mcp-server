# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.


from functools import partial
from typing import Optional, Union

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    MetadataEnrichmentCreationRequest,
    MetadataEnrichmentObjective,
    DataScopeOperation,
    MetadataEnrichmentAssetPatchResponse,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    call_create_metadata_enrichment_asset,
    call_update_metadata_enrichment_asset,
    check_if_datasets_assigned_to_mde,
    generate_metadata_enrichment_asset,
)
from app.services.tool_utils import (
    confirm_list_str,
    find_asset_id_exact_match,
    find_category_id,
    find_metadata_enrichment_id,
    find_project_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import confirm_uuid


@service_registry.tool(
    name="create_or_update_metadata_enrichment_asset",
    description="""Creates a new metadata enrichment asset or updates an existing one within a specified project.

    This tool automatically detects whether to create or update based on whether an MDE with the given name exists:
    - If MDE exists: UPDATE mode (updates existing MDE with new objectives and categories)
    - If MDE doesn't exist: CREATE mode (creates new MDE)

    CREATE MODE (when MDE doesn't exist):
    - Requires: metadata_enrichment_name, objective_names, category_names, dataset_names
    - Creates a new metadata enrichment asset with the specified datasets, categories, and objectives
    - Validates that datasets exist and aren't already assigned to other MDEs
    - Returns DataScopeOperation with details of the newly created asset

    UPDATE MODE (when MDE exists):
    - Requires: metadata_enrichment_name, objective_names
    - Optional: category_names (updates categories if provided)
    - Ignores: dataset_names (datasets cannot be modified after creation - will log warning if provided)
    - Updates the MDE's objectives and optionally categories
    - Returns MetadataEnrichmentAssetPatchResponse with updated MDE details

    The objective_names in MetadataEnrichmentCreationRequest is the list of names of objectives used in the enrichment job.
    Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality', 'assign_terms', 
    'analyze_relationships', 'dq_sla_assessment', and 'semantic_expansion'.
    
    The function assumes that the datasets and categories provided are valid and exist.
    It does not handle the creation of datasets or categories if they do not already exist.""",
)
@auto_context
async def create_or_update_metadata_enrichment_asset(
    request: MetadataEnrichmentCreationRequest,
) -> Union[DataScopeOperation, MetadataEnrichmentAssetPatchResponse]:

    LOGGER.info(
        f"create_or__metadata_enrichment_asset called with project_name: {request.project_name}, "
        f"asset_name: {request.metadata_enrichment_name}, category_names: {request.category_names}, "
        f"dataset_names: {request.dataset_names}, objective_names: {request.objective_names}, "
        f"description: {request.description}, new_name: {request.new_name}"
    )

    project_id = await confirm_uuid(request.project_name, find_project_id)

    metadata_enrichment_id = None
    try:
        metadata_enrichment_id = await confirm_uuid(
            request.metadata_enrichment_name,
            partial(find_metadata_enrichment_id, project_id=project_id)
        )
        LOGGER.info(f"Found existing MDE with ID: {metadata_enrichment_id}. Using UPDATE mode.")
    except ServiceError:
        LOGGER.info(f"MDE '{request.metadata_enrichment_name}' not found. Using CREATE mode.")

    objectives = [
        MetadataEnrichmentObjective(objective)
        for objective in confirm_list_str(request.objective_names)
    ]

    category_ids = []
    if request.category_names:
        category_ids = [
            await confirm_uuid(category_name, find_category_id)
            for category_name in confirm_list_str(request.category_names)
        ]

    if metadata_enrichment_id:
        return await update_mde(category_ids, metadata_enrichment_id, objectives, project_id, request)
    else:
        return await create_mde(category_ids, objectives, project_id, request)


async def create_mde(category_ids: list[str], objectives: list[MetadataEnrichmentObjective], project_id: str,
                     request: MetadataEnrichmentCreationRequest) -> DataScopeOperation:
    # CREATE MODE
    LOGGER.info(f"Creating new MDE '{request.metadata_enrichment_name}'")

    if not request.category_names:
        raise ServiceError(
            "category_names is required when creating a new metadata enrichment asset. "
            "Please provide at least one category."
        )

    if not request.dataset_names:
        raise ServiceError(
            "dataset_names is required when creating a new metadata enrichment asset. "
            "Please provide at least one dataset."
        )

    dataset_names = confirm_list_str(request.dataset_names)
    dataset_ids = [
        await confirm_uuid(
            dataset_name, partial(find_asset_id_exact_match, container_id=project_id)
        )
        for dataset_name in dataset_names
    ]

    await check_if_datasets_assigned_to_mde(dataset_ids, dataset_names, project_id)
    mde_asset = generate_metadata_enrichment_asset(
        asset_name=request.metadata_enrichment_name,
        dataset_uuids=dataset_ids,
        category_uuids=category_ids,
        objectives=objectives,
    )

    return await call_create_metadata_enrichment_asset(project_id, mde_asset)


async def update_mde(category_ids: list[str], metadata_enrichment_id: str, objectives: list[MetadataEnrichmentObjective], project_id: str,
                     request: MetadataEnrichmentCreationRequest) -> MetadataEnrichmentAssetPatchResponse:
    # UPDATE MODE
    LOGGER.info(f"Updating existing MDE {metadata_enrichment_id}")

    if request.dataset_names:
        LOGGER.warning(
            f"dataset_names provided in UPDATE mode but will be ignored. "
            f"Datasets cannot be modified after MDE creation. "
            f"Provided datasets: {request.dataset_names}"
        )

    new_name = request.new_name if request.new_name else None

    return await call_update_metadata_enrichment_asset(
        project_id=project_id,
        metadata_enrichment_id=metadata_enrichment_id,
        category_ids=category_ids,
        objectives=objectives,
        name=new_name,
        description=request.description,
    )


@service_registry.tool(
    name="create_or_update_metadata_enrichment_asset",
    description="""Creates a new metadata enrichment asset or updates an existing one within a specified project.

    This tool automatically detects whether to create or update based on whether an MDE with the given name exists:
    - If MDE exists: UPDATE mode (updates existing MDE)
    - If MDE doesn't exist: CREATE mode (creates new MDE)

    CREATE MODE: Requires metadata_enrichment_name, objective_names, category_names, dataset_names
    UPDATE MODE: Requires metadata_enrichment_name, objective_names; Optional: category_names; Ignores: dataset_names

    The objective_names is the list of names of objectives used in the enrichment job.
    Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality', 'assign_terms', 
    'analyze_relationships', 'dq_sla_assessment', and 'semantic_expansion'.""",
)
@auto_context
async def wxo_create_or_update_metadata_enrichment_asset(
    project_name: str,
    metadata_enrichment_name: str,
    objective_names: list[str] | str,
    category_names: Optional[list[str] | str] = None,
    dataset_names: Optional[list[str] | str] = None,
    description: Optional[str] = None,
    new_name: Optional[str] = None,
) -> Union[DataScopeOperation, MetadataEnrichmentAssetPatchResponse]:
    """Watsonx Orchestrator compatible version that expands MetadataEnrichmentCreationRequest into individual parameters."""

    request = MetadataEnrichmentCreationRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
        objective_names=objective_names,
        category_names=category_names,
        dataset_names=dataset_names,
        description=description,
        new_name=new_name,
    )
    return await create_or_update_metadata_enrichment_asset(request)
