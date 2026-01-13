# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import asyncio
from functools import partial
from string import Template
from typing import Final, Optional

from tenacity import RetryError

from app.services.constants import GS_BASE_ENDPOINT
from app.services.metadata_enrichment.models.metadata_enrichment import (
    CAMS_ASSET_BASE_URL,
    JOBS_BASE_URL,
    MDE_START_SELECTIVE_ASSETS_TEMPLATE,
    MDE_UI_URL_TEMPLATE,
    METADATA_ENRICHMENT_SERVICE_URL,
    DataScopeAssetSelection,
    DataScopeOperation,
    GovernanceScopeCategory,
    MetadataEnrichmentAsset,
    MetadataEnrichmentAssetDataScopeUpdateRequest,
    MetadataEnrichmentAssetInfo,
    MetadataEnrichmentAssetPatch,
    MetadataEnrichmentAssetPatchResponse,
    MetadataEnrichmentObjective,
    MetadataEnrichmentRun,
    OperationStatusEnum,
    QualityOrigins,
    SuggestedDataQualityCheck,
)
from app.services.tool_utils import (
    ARTIFACT_TYPE_DATA_ASSET,
    ENTITY_ASSETS_PROJECT_ID,
    METADATA_ARTIFACT_TYPE,
    confirm_list_str,
    find_asset_id_exact_match,
    find_category_id,
    find_metadata_enrichment_id,
    find_project_id,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import append_context_to_url, confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service

TOOL_NAME: Final = "metadata_enrichment_tool"
DEFAULT_MDE_NAME = "Metadata_Enrichment_for_MCP_Agent"
ARTIFACT_TYPE_MDE = "metadata_enrichment_area"
CHECK_MDE_OPERATION_INTERVAL = 5  # sec
CHECK_MDE_OPERATION_MAX_TRIAL = 5


async def find_job_id_in_metadata_enrichment(
    metadata_enrichment_id: str, project_id: str
) -> str:
    """
    Find ID of the job in a metadata enrichment

    Args:
        metadata_enrichment_id (str): The ID of the metadata enrichment.
        project_id (uuid.UUID): The ID of the project you want to execute a metadata enrichment.

    Returns:
        str: The unique identifier of the job in the metadata enrichment.

    Raises:
        ToolProcessFailedError: If the job ID is not found in the metadata enrichment.
    """

    get_url = f"{CAMS_ASSET_BASE_URL}/{metadata_enrichment_id}"
    query_params = {
        "project_id": project_id,
    }
    response = await tool_helper_service.execute_get_request(
        url=get_url,
        params=query_params,
        tool_name=TOOL_NAME,
    )

    result_id = (
        response.get("entity", {})
        .get("metadata_enrichment_area", {})
        .get("job", {})
        .get("id", {})
    )
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"The job ID in the metadata enrichment with ID:{metadata_enrichment_id} was not found."
        )


async def execute_metadata_enrichment_job(job_id: str, project_id: str) -> str:
    """
    Execute the metadata enrichment with the job ID

    Args:
        job_id (str): The ID of the job in the metadata enrichment.
        project_id (uuid.UUID): The ID of the project you want to execute a metadata enrichment.

    Returns:
        str: The unique identifier of the job run in the metadata enrichment.

    Raises:
        ToolProcessFailedError: If the metadata enrichment job fails to execute.
        ExternalServiceError: If an unexpected error occurs while communicating with the external service.
    """

    post_url = f"{JOBS_BASE_URL}/{job_id}/runs"
    query_params = {
        "project_id": project_id,
    }

    try:
        response = await tool_helper_service.execute_post_request(
            url=post_url,
            params=query_params,
            tool_name=TOOL_NAME,
        )
        jobrun_id = response.get("metadata", {}).get("asset_id", None)
        if jobrun_id:
            return jobrun_id
        else:
            raise ServiceError(
                f"The execution of metadata enrichment with the Job ID:'{job_id}' failed."
            )
    except ExternalAPIError as eae:
        LOGGER.error(
            "An unexpected exception occurs during executing Metadata Enrichment. (Cause=%s)",
            str(eae),
        )
        raise ServiceError(
            f"The execution of metadata enrichment with the Job ID:'{job_id}' failed due to {str(eae)}."
        )


async def execute_metadata_enrichment_with_assets(
    mde_id: str, project_id: str, dataset_uuids: list[str] | str
) -> str:
    """
    Execute the metadata enrichment with the job ID

    Args:
        job_id (str): The ID of the job in the metadata enrichment.
        project_id (uuid.UUID): The ID of the project you want to execute a metadata enrichment.
        dataset_uuids (list[str]): List of UUIDs of target datasets to be enriched with metadata.

    Returns:
        str: The unique identifier of the job run in the metadata enrichment.

    Raises:
        ToolProcessFailedError: If the metadata enrichment job fails to execute.
        ExternalServiceError: If an unexpected error occurs while communicating with the external service.
    """

    template = Template(MDE_START_SELECTIVE_ASSETS_TEMPLATE)
    post_url = template.substitute(mde_id=mde_id)
    query_params = {
        "project_id": project_id,
    }
    payload = {"data_asset_selection": {"ids": dataset_uuids}}

    try:
        response = await tool_helper_service.execute_post_request(
            url=post_url,
            params=query_params,
            json=payload,
            tool_name=TOOL_NAME,
        )
        jobrun_id = response.get("job_run_id", None)
        if jobrun_id:
            return jobrun_id
        else:
            raise ServiceError(
                f"The execution of metadata enrichment with the Metadata Enrichment ID:'{mde_id}' failed."
            )
    except ExternalAPIError as ese:
        LOGGER.error(
            "An unexpected exception occurs during executing Metadata Enrichment. (Cause=%s)",
            str(ese),
        )
        raise ServiceError(
            f"The execution of metadata enrichment with the Metadata Enrichment ID:'{mde_id}' failed due to {str(ese)}."
        )


def set_metadata_enrichment_objective(
    mde_asset: MetadataEnrichmentAsset | MetadataEnrichmentAssetPatch,
    objectives: list[MetadataEnrichmentObjective],
):
    mde_options = mde_asset.objective.enrichment_options.structured
    for objective in objectives:
        match objective:
            case MetadataEnrichmentObjective.PROFILE:
                mde_options.profile = True
            case MetadataEnrichmentObjective.DQ_GEN_CONSTRAINTS:
                mde_options.dq_gen_constraints = True
            case MetadataEnrichmentObjective.ANALYZE_QUALITY:
                mde_options.analyze_quality = True
            case MetadataEnrichmentObjective.SEMANTIC_EXPANSION:
                mde_options.semantic_expansion = True
            case MetadataEnrichmentObjective.ASSIGN_TERMS:
                mde_options.assign_terms = True
            case MetadataEnrichmentObjective.ANALYZE_RELATIONSHIPS:
                mde_options.analyze_relationships = True
            case MetadataEnrichmentObjective.DQ_SLA_ASSESSMENT:
                mde_options.dq_sla_assessment = True
            case _:
                raise ValueError(f"Invalid objective: {objective}")


def generate_metadata_enrichment_asset(
    asset_name: str,
    dataset_uuids: list[str],
    category_uuids: list[str],
    objectives: list[MetadataEnrichmentObjective],
) -> MetadataEnrichmentAsset:
    """
    Generates a default MetadataEnrichmentAsset with specified parameters.

    Args:
        asset_name (str): The name of the MetadataEnrichmentAsset.
        dataset_uuids (list[str]): List of dataset UUIDs for the asset.
        category_uuids (list[str]): List of category UUIDs for governance scope.
        objectives (list[MetadataEnrichmentObjective]): List of objectives of the MetadataEnrichmentAsset.

    Returns:
        MetadataEnrichmentAsset: A default configured MetadataEnrichmentAsset.
    """
    mde_asset = MetadataEnrichmentAsset(name=asset_name)
    mde_asset.data_scope.enrichment_assets = dataset_uuids
    set_metadata_enrichment_objective(mde_asset, objectives)
    for category_uuid in category_uuids:
        mde_asset.objective.governance_scope.append(
            GovernanceScopeCategory(id=category_uuid)
        )
    # sets data quality parameters
    list_of_dq_checks_suggested = [
        SuggestedDataQualityCheck(id="case", enabled=True),
        SuggestedDataQualityCheck(id="completeness", enabled=True),
        SuggestedDataQualityCheck(id="data_type", enabled=True),
        SuggestedDataQualityCheck(id="format", enabled=True),
        SuggestedDataQualityCheck(id="uniqueness", enabled=True),
        SuggestedDataQualityCheck(id="range", enabled=True),
        SuggestedDataQualityCheck(id="regex", enabled=True),
        SuggestedDataQualityCheck(id="length", enabled=True),
        SuggestedDataQualityCheck(id="possible_values", enabled=True),
        SuggestedDataQualityCheck(id="data_class", enabled=True),
        SuggestedDataQualityCheck(id="nonstandard_missing_values", enabled=True),
        SuggestedDataQualityCheck(id="rule", enabled=True),
        SuggestedDataQualityCheck(id="suspect_values", enabled=True),
        SuggestedDataQualityCheck(id="referential_integrity", enabled=True),
        SuggestedDataQualityCheck(id="history_stability", enabled=True),
    ]
    quality_origins = QualityOrigins(
        profiling=True, business_terms=False, relationships=False
    )
    mde_asset.objective.data_quality.structured.dq_checks_suggested = (
        list_of_dq_checks_suggested
    )
    mde_asset.objective.data_quality.structured.quality_origins = quality_origins
    return mde_asset


async def do_metadata_enrichment_process(
    project_name: str,
    dataset_names: list[str] | str,
    category_names: list[str] | str,
    objectives: list[MetadataEnrichmentObjective],
) -> list[MetadataEnrichmentRun]:
    """
    Initiates the metadata enrichment process for specified datasets within a project.

    This function performs the following steps:
    1. Confirms the project ID using the provided project_name.
    2. Confirms the dataset IDs using the provided dataset_names.
    3. Confirms the category IDs using the provided category_names.
    4. Creates or finds metadata enrichment assets based on the confirmed data asset and category IDs.
    5. Executes the metadata enrichment objectives for each asset and collects the results.

    Args:
        project_name (str): The name of the project for metadata enrichment.
        dataset_names (list[str] | str): Names of datasets for metadata enrichment.
            If a single string is provided, it will be treated as a list containing that string.
        category_names (list[str] | str): Names of categories for metadata enrichment.
            If a single string is provided, it will be treated as a list containing that string.
        objectives (list[MetadataEnrichmentObjective]): List of metadata enrichment objectives.

    Returns:
        list[MetadataEnrichmentRun]: A list of results from executing metadata enrichment objectives.
    """

    project_id = await confirm_uuid(project_name, find_project_id)
    dataset_ids = [
        await confirm_uuid(
            dataset_uuid, partial(find_asset_id_exact_match, container_id=project_id)
        )
        for dataset_uuid in confirm_list_str(dataset_names)
    ]
    category_ids = [
        await confirm_uuid(category_name, find_category_id)
        for category_name in confirm_list_str(category_names)
    ]

    list_of_mde_assets = (
        await create_or_find_metadata_enrichment_assets_from_data_asset_ids(
            project_id=project_id,
            data_asset_ids=dataset_ids,
            category_ids=category_ids,
            objectives=objectives,
        )
    )

    response_operation = []
    for mde_asset in list_of_mde_assets:
        result = await execute_mde_objective(project_id, mde_asset)
        response_operation.append(result)
    return response_operation


async def call_create_metadata_enrichment_asset(
    project_id: str, mde_asset: MetadataEnrichmentAsset
) -> DataScopeOperation:
    """
    Create a new metadata enrichment asset in the system.

    This function sends a POST request to the metadata enrichment service URL with the provided project_id and the metadata enrichment asset details.

    Args:
        project_id (str): The ID of the project to which the metadata enrichment asset belongs.
        mde_asset (MetadataEnrichmentAsset): The metadata enrichment asset object containing the necessary details for creation.

    Returns:
        DataScopeOperation: An instance of DataScopeOperation representing the result of the operation.

    Raises:
        Exception: If the request execution fails.
    """

    query_params = {
        "project_id": project_id,
    }
    response = await tool_helper_service.execute_post_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets",
        json=mde_asset.model_dump(exclude_none=True),
        params=query_params,
    )
    LOGGER.info(f"Successfully created metadata enrichment asset. Response: {response}")
    return DataScopeOperation.model_validate(response)


async def check_if_datasets_assigned_to_mde(
    dataset_ids: list[str], dataset_names: list[str], project_id: str
):
    dataset_names_in_mde = []
    for dataset_id, dataset_name in zip(dataset_ids, dataset_names):
        mde_id = await find_metadata_enrichment_id_containing_dataset(
            dataset_id, project_id
        )
        if mde_id:
            dataset_names_in_mde.append(dataset_name)
    if dataset_names_in_mde:
        raise ServiceError(
            f"The following dataset(s) are already assigned to other Metadata Enrichment Assets: {dataset_names_in_mde}"
        )


async def create_or_find_metadata_enrichment_assets_from_data_asset_ids(
    project_id: str,
    data_asset_ids: list[str],
    category_ids: list[str],
    objectives: list[MetadataEnrichmentObjective],
) -> list[MetadataEnrichmentAssetInfo]:
    """
    Create or find Metadata Enrichment Assets based on provided data asset IDs.

    This function either finds existing Metadata Enrichment Assets for given data assets or creates new ones if they don't exist.

    Args:
        project_id (str): The ID of the project where the Metadata Enrichment Assets will be created or found.
        data_asset_ids (list[str]): A list of data asset IDs for which to find or create Metadata Enrichment Assets.
        category_ids (list[str]): A list of category IDs associated with the Metadata Enrichment Assets.
        objectives (list[MetadataEnrichmentObjective]): A list of objectives for the Metadata Enrichment Assets.

    Returns:
        list[MetadataEnrichmentAssetInfo]: A list of MetadataEnrichmentAssetInfo objects containing the metadata enrichment IDs and their corresponding data asset IDs.
    """

    default_mde_id = None
    try:
        default_mde_id = await find_metadata_enrichment_id(DEFAULT_MDE_NAME, project_id)
    except ServiceError:
        LOGGER.info(
            f"Default Metadata Enrichment asset {DEFAULT_MDE_NAME} is not found."
        )

    mde_to_datasets: dict[str, list[str]] = {}
    # find metadata enrichment assets for each data asset
    data_asset_ids_not_belonging_to_mde = []
    for data_asset_id in data_asset_ids:
        mde_id = await find_metadata_enrichment_id_containing_dataset(
            data_asset_id, project_id
        )
        if mde_id is None:
            data_asset_ids_not_belonging_to_mde.append(data_asset_id)
        else:
            # if a mde exists, the data asset ids are passed as is.
            mde_to_datasets.setdefault(mde_id, []).append(data_asset_id)

    # update existing mde with defined objectives
    for mde_id in mde_to_datasets:
        await call_update_metadata_enrichment_asset(
            project_id, mde_id, category_ids, objectives
        )

    if data_asset_ids_not_belonging_to_mde:
        if default_mde_id:
            # update default mde with defined objectives,
            await call_update_metadata_enrichment_asset(
                project_id, default_mde_id, category_ids, objectives
            )
            # and add data assets not belonging to mde to default mde
            result_operation = await call_update_data_scope(
                project_id, default_mde_id, data_asset_ids_not_belonging_to_mde
            )
            mde_to_datasets.setdefault(default_mde_id, []).extend(
                data_asset_ids_not_belonging_to_mde
            )
        else:
            # create new metadata enrichment asset
            # for data asset not belonging to mde if default MDE doesn't exist
            mde_asset = generate_metadata_enrichment_asset(
                asset_name=DEFAULT_MDE_NAME,
                dataset_uuids=data_asset_ids_not_belonging_to_mde,
                category_uuids=category_ids,
                objectives=objectives,
            )
            result_operation = await call_create_metadata_enrichment_asset(
                project_id, mde_asset
            )
            mde_to_datasets[result_operation.target_resource_id] = (
                data_asset_ids_not_belonging_to_mde
            )
        # created/updated metadata enrichment will be executed later
        # so confirm data scope operation is ready
        try:
            await confirm_ready_data_scope_operation(project_id, result_operation.id)
        except RetryError:
            raise ServiceError(
                f"The data scope background operation of metadata enrichment asset: {result_operation.target_resource_id} did not finish."
            )

    return [
        MetadataEnrichmentAssetInfo(
            metadata_enrichment_id=mde_id, dataset_ids=mde_to_datasets[mde_id]
        )
        for mde_id in mde_to_datasets
    ]


async def call_retrieve_data_scope_operation(
    project_id: str, operation_id: str
) -> DataScopeOperation:
    response = await tool_helper_service.execute_get_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/data_scope_operations/{operation_id}",
        params={"project_id": project_id},
    )
    LOGGER.info(
        f"Successfully retrieve metadata enrichment asset data scope operation. Response: {response}"
    )
    return DataScopeOperation.model_validate(response)


async def confirm_ready_data_scope_operation(
    project_id: str,
    operation_id: str,
    check_max_trial: int = CHECK_MDE_OPERATION_MAX_TRIAL,
    check_interval: int = CHECK_MDE_OPERATION_INTERVAL,
):
    for _ in range(check_max_trial):
        await asyncio.sleep(check_interval)
        result_operation = await call_retrieve_data_scope_operation(
            project_id, operation_id
        )
        if result_operation.status == OperationStatusEnum.SUCCEEDED:
            return
    raise ServiceError(
        f"The metadata enrichment asset data scope background operation: {operation_id} did not finish. The last status: {result_operation.status}"
    )


async def execute_mde_objective(
    project_id: str, metadata_enrichment_asset: MetadataEnrichmentAssetInfo
) -> MetadataEnrichmentRun:
    """
    Executes the Metadata Enrichment (MDE) objective for a given project and asset.

    This function initiates the execution of an MDE job by finding the corresponding job ID,
    executing the metadata enrichment with specified assets, and creating a response object
    containing job and run IDs, project ID, and the MDE UI URL.

    Args:
        project_id (str): The ID of the project for which the MDE objective is to be executed.
        metadata_enrichment_asset (MetadataEnrichmentAssetInfo): The asset information containing
            datasets to be enriched.

    Returns:
        MetadataEnrichmentRun: An object containing job and run IDs, project ID, and MDE UI URL.
    """

    mde_id = metadata_enrichment_asset.metadata_enrichment_id
    job_id = await find_job_id_in_metadata_enrichment(mde_id, project_id)
    job_run_id = await execute_metadata_enrichment_with_assets(
        mde_id=mde_id,
        project_id=project_id,
        dataset_uuids=metadata_enrichment_asset.dataset_ids,
    )

    mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
        mde_id=mde_id, project_id=project_id
    )
    mde_url = append_context_to_url(mde_url)
    response_operation = MetadataEnrichmentRun(
        metadata_enrichment_id=mde_id,
        job_id=job_id,
        job_run_id=job_run_id,
        project_id=project_id,
        metadata_enrichment_ui_url=mde_url,
    )
    return response_operation


async def call_update_metadata_enrichment_asset(
    project_id: str,
    metadata_enrichment_id: str,
    category_ids: list[str],
    objectives: list[MetadataEnrichmentObjective],
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> MetadataEnrichmentAssetPatchResponse:
    """
    Update an existing metadata enrichment asset.
    
    Args:
        project_id: The ID of the project containing the MDE
        metadata_enrichment_id: The ID of the MDE to update
        category_ids: List of category IDs for governance scope
        objectives: List of objectives to set
        name: Optional new name for the MDE
        description: Optional new description for the MDE
        
    Returns:
        MetadataEnrichmentAssetPatchResponse with updated MDE details
    """
    mde_patch = MetadataEnrichmentAssetPatch()
    set_metadata_enrichment_objective(mde_patch, objectives)
    for category_id in category_ids:
        mde_patch.objective.governance_scope.append(
            GovernanceScopeCategory(id=category_id)
        )

    # Build the patch payload with optional name and description
    patch_payload = mde_patch.model_dump(exclude_none=True)
    
    # Add name and description to the patch if provided
    if name is not None:
        patch_payload["name"] = name
    if description is not None:
        patch_payload["description"] = description

    response = await tool_helper_service.execute_patch_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{metadata_enrichment_id}",
        json=patch_payload,
        params={"project_id": project_id},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    LOGGER.info(f"Successfully updated metadata enrichment asset. Response: {response}")
    return MetadataEnrichmentAssetPatchResponse.model_validate(response)


async def call_update_data_scope(
    project_id: str, metadata_enrichment_id: str, assets_to_add: list[str]
):
    update_data_scope = MetadataEnrichmentAssetDataScopeUpdateRequest(
        assets_to_add=DataScopeAssetSelection(ids=assets_to_add)
    )

    response = await tool_helper_service.execute_post_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{metadata_enrichment_id}/update_data_scope",
        json=update_data_scope.model_dump(exclude_none=True),
        params={"project_id": project_id},
    )
    LOGGER.info(
        f"Successfully updated data scope of metadata enrichment asset. Response: {response}"
    )
    return DataScopeOperation.model_validate(response)


async def find_metadata_enrichment_id_containing_dataset(
    dataset_id: str, project_id: str
) -> Optional[str]:
    must_match = [
        {"match": {METADATA_ARTIFACT_TYPE: ARTIFACT_TYPE_DATA_ASSET}},
        {"match": {"artifact_id": dataset_id}},
        {"match": {ENTITY_ASSETS_PROJECT_ID: project_id}},
    ]
    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json={"query": {"bool": {"must": must_match}}},
    )

    for row in response.get("rows", []):
        metadata = row["metadata"]
        if metadata["artifact_type"] == ARTIFACT_TYPE_DATA_ASSET:
            return row["entity"]["assets"].get("metadata_enrichment_area_id", None)
    raise ServiceError(
        f"Couldn't find any metadata enrichment assets with the dataset '{dataset_id}' in project '{project_id}'"
    )
