# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.


from functools import partial

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    MetadataEnrichmentCreationRequest,
    MetadataEnrichmentObjective,
    DataScopeOperation,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    call_create_metadata_enrichment_asset,
    check_if_datasets_assigned_to_mde,
    generate_metadata_enrichment_asset,
)
from app.services.tool_utils import (
    confirm_list_str,
    find_asset_id_exact_match,
    find_category_id,
    find_project_id,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import confirm_uuid


@service_registry.tool(
    name="create_metadata_enrichment_asset",
    description="""Creates a new metadata enrichment asset within a specified project.

    This tool allows the creation of a new metadata enrichment asset, defining its name, associated categories,
    datasets, and objectives. It ensures that the datasets specified exist within the project and are correctly
    assigned to the new asset. The function returns a DataScopeOperation object containing details of the newly created asset.
    
    The objective_names in MetadataEnrichmentCreationRequest is the list of names of objectives used in the enrichment job.
    Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality', and 'semantic_expansion'"
    
    The creation process involves:
    1. Confirming the project ID based on the provided project name.
    2. Retrieving or confirming the UUIDs for each dataset specified, ensuring they exist within the project.
    3. Confirming the UUIDs for each category specified.
    4. Generating the metadata enrichment asset with the provided name, linked datasets, categories, and objectives.
    5. Creating the asset within the project using the generated configuration.
    
    The function assumes that the datasets and categories provided are valid and exist.
    It does not handle the creation of datasets or categories if they do not already exist.""",
)
@auto_context
async def create_metadata_enrichment_asset(
    request: MetadataEnrichmentCreationRequest,
) -> DataScopeOperation:

    LOGGER.info(
        f"The create metadata_enrichment_asset was called with project_name: {request.project_name}, asset_name: {request.metadata_enrichment_name}, category_names: {request.category_names}, dataset_names: {request.dataset_names}, objective_names: {request.objective_names}"
    )

    project_id = await confirm_uuid(request.project_name, find_project_id)
    category_ids = [
        await confirm_uuid(category_name, find_category_id)
        for category_name in confirm_list_str(request.category_names)
    ]
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
        objectives=[
            MetadataEnrichmentObjective(objective)
            for objective in confirm_list_str(request.objective_names)
        ],
    )

    return await call_create_metadata_enrichment_asset(project_id, mde_asset)


@service_registry.tool(
    name="create_metadata_enrichment_asset",
    description="""Creates a new metadata enrichment asset within a specified project.

    This tool allows the creation of a new metadata enrichment asset, defining its name, associated categories,
    datasets, and objectives. It ensures that the datasets specified exist within the project and are correctly
    assigned to the new asset. The function returns a DataScopeOperation object containing details of the newly created asset.

    The objective_names is the list of names of objectives used in the enrichment job.
    Supported objectives are 'profile', 'dq_gen_constraints', 'analyze_quality', and 'semantic_expansion'"
    
    The creation process involves:
    1. Confirming the project ID based on the provided project name.
    2. Retrieving or confirming the UUIDs for each dataset specified, ensuring they exist within the project.
    3. Confirming the UUIDs for each category specified.
    4. Generating the metadata enrichment asset with the provided name, linked datasets, categories, and objectives.
    5. Creating the asset within the project using the generated configuration.
    
    The function assumes that the datasets and categories provided are valid and exist.
    It does not handle the creation of datasets or categories if they do not already exist.""",
)
@auto_context
async def wxo_create_metadata_enrichment_asset(
    project_name: str,
    metadata_enrichment_name: str,
    category_names: list[str] | str,
    dataset_names: list[str] | str,
    objective_names: list[str] | str,
) -> DataScopeOperation:
    """Watsonx Orchestrator compatible version that MetadataEnrichmentCreationRequest expands object into individual parameters."""

    request = MetadataEnrichmentCreationRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
        category_names=category_names,
        objective_names=objective_names,
        dataset_names=dataset_names,
    )
    return await create_metadata_enrichment_asset(request)
