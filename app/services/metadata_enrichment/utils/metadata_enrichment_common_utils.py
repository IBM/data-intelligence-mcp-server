# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import asyncio  # noqa: I001 # Baseline
from functools import partial
from string import Template
from typing import Any, Callable, Dict, Final, Optional  # noqa: UP035 # Baseline

from pydantic import TypeAdapter
from tenacity import RetryError

from app.core.settings import ENV_MODE_SAAS, settings
from app.services.constants import (
    ASSET_TYPE_BASE_ENDPOINT,
    CAMS_ASSETS_BASE_ENDPOINT,
    GS_BASE_ENDPOINT,
    JOBS_BASE_ENDPOINT,
    METADATA_ENRICHMENT_BASE_ENDPOINT,
    WORKFLOW_BASE_ENDPOINT,
)
from app.services.metadata_enrichment.constants import (
    CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_TOOL_NAME,
    CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
)
from app.services.metadata_enrichment.models.metadata_enrichment import (
    AssetProcessingResult,
    ContainerAssets,
    DataAssets,
    DataScopeAssetSelection,
    DataScopeOperation,
    EnrichmentAssetsInfo,
    GovernanceScopeCategory,
    JobRunStatus,
    MetadataEnrichmentAsset,
    MetadataEnrichmentAssetDataScopeUpdateRequest,
    MetadataEnrichmentAssetInfo,
    MetadataEnrichmentAssetPatch,
    MetadataEnrichmentAssetPatchResponse,
    MetadataEnrichmentAssetResponse,  # noqa: F401 # Baseline
    MetadataEnrichmentCreationRequest,
    MetadataEnrichmentDetails,
    MetadataEnrichmentObjective,
    MetadataEnrichmentRun,
    OperationStatusEnum,
    QualityOrigins,
    SuggestedDataQualityCheck,
    TermAssignmentObjective,
    TermGenerationBatchResponse,
    MetadataEnrichmentAssetEnrichmentJob,
    MetadataEnrichmentAssetEnrichmentJobResponse,
)
from app.services.tool_utils import (
    ARTIFACT_TYPE_DATA_ASSET,
    ENTITY_ASSETS_PROJECT_ID,
    METADATA_ARTIFACT_TYPE,
    confirm_list_str,
    find_asset_id_exact_match,
    find_category_id,
    find_metadata_enrichment_id,
    find_metadata_import_id,
    find_project_id,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError, ValidationError
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import append_context_to_url, confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service

UI_BASE_URL = str(tool_helper_service.ui_base_url)
BASE_URL = str(tool_helper_service.base_url)

TOOL_NAME: Final = "metadata_enrichment_tool"
DEFAULT_MDE_NAME = "Metadata_Enrichment_for_MCP_Agent"
ARTIFACT_TYPE_MDE = "metadata_enrichment_area"
CHECK_MDE_OPERATION_INTERVAL = 5  # sec
CHECK_MDE_OPERATION_MAX_TRIAL = 5

METADATA_ENRICHMENT_SERVICE_URL = BASE_URL + METADATA_ENRICHMENT_BASE_ENDPOINT
MDE_START_SELECTIVE_ASSETS_TEMPLATE = (
    METADATA_ENRICHMENT_SERVICE_URL
    + "/metadata_enrichment_assets/${mde_id}/jobs/${job_id}/start_enrichment"
)
MDE_WITH_ID_TEMPLATE = (
    METADATA_ENRICHMENT_SERVICE_URL + "/metadata_enrichment_assets/${mde_id}"
)
CAMS_ASSETS_SERVICE_URL = BASE_URL + CAMS_ASSETS_BASE_ENDPOINT
JOBS_SERVICE_URL = BASE_URL + JOBS_BASE_ENDPOINT
MDE_UI_DISPLAY_URL = UI_BASE_URL + "/gov/metadata-enrichments/display"
MDE_UI_DISPLAY_TEMPLATE = (
    MDE_UI_DISPLAY_URL + "/${mde_id}?project_id=${project_id}&context=df"
)
MDE_UI_URL_TEMPLATE = (
    MDE_UI_DISPLAY_URL
    + "/${mde_id}/structured/columns?project_id=${project_id}&context=df"
)
CATEGORY_UI_URL_TEMPLATE = (
    UI_BASE_URL + "/${governance_base}/categories/${target_category_id}?context=df"
)
TASK_INBOX_UI_URL_TEMPLATE = (
    UI_BASE_URL + "/${governance_base}/workflow/tasks?context=df"
)

METADATA_ENRICHMENT_AREA_INFO = "metadata_enrichment_area_info"
AREA_ID = "area_id"
BATCH_SIZE_MDE = 20
BATCH_SIZE_TERM_GEN = 1
GET_WORKFLOWS_FROM_CORRELATION_ID_URL = BASE_URL + WORKFLOW_BASE_ENDPOINT + "/all/query"
GET_TERMS_IN_WORKFLOW_URL = BASE_URL + WORKFLOW_BASE_ENDPOINT


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

    get_url = f"{CAMS_ASSETS_SERVICE_URL}/{metadata_enrichment_id}"
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

    post_url = f"{JOBS_SERVICE_URL}/{job_id}/runs"
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
        raise ServiceError(
            f"The execution of metadata enrichment with the Job ID:'{job_id}' failed."
        )
    except ExternalAPIError as eae:
        LOGGER.error(
            "An unexpected exception occurs during executing Metadata Enrichment. (Cause=%s)",
            str(eae),
        )
        raise ServiceError(  # noqa: B904 # Baseline
            f"The execution of metadata enrichment with the Job ID:'{job_id}' failed due to {eae!s}."
        )


async def execute_metadata_enrichment_with_assets(
    mde_id: str, project_id: str, job_id: str, dataset_uuids: list[str] | str
) -> str:
    """
    Execute the metadata enrichment with the job ID

    Args:
        mde_id (str): The ID of the the metadata enrichment.
        project_id (uuid.UUID): The ID of the project you want to execute a metadata enrichment job.
        job_id (str): The ID of the job in the metadata enrichment.
        dataset_uuids (list[str]): List of UUIDs of target datasets to be enriched with metadata.

    Returns:
        str: The unique identifier of the job run in the metadata enrichment.

    Raises:
        ToolProcessFailedError: If the metadata enrichment job fails to execute.
        ExternalServiceError: If an unexpected error occurs while communicating with the external service.
    """

    template = Template(MDE_START_SELECTIVE_ASSETS_TEMPLATE)
    post_url = template.substitute(mde_id=mde_id, job_id=job_id)
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
        raise ServiceError(
            f"The execution of metadata enrichment with the Metadata Enrichment ID:'{mde_id}' failed."
        )
    except ExternalAPIError as ese:
        LOGGER.error(
            "An unexpected exception occurs during executing Metadata Enrichment. (Cause=%s)",
            str(ese),
        )
        raise ServiceError(  # noqa: B904 # Baseline
            f"The execution of metadata enrichment with the Metadata Enrichment ID:'{mde_id}' failed due to {ese!s}."
        )


def set_metadata_enrichment_objective(  # noqa: ANN201 # Baseline
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
            case MetadataEnrichmentObjective.DATA_SEARCH:
                mde_options.data_search = True
            case _:
                raise ValueError(f"Invalid objective: {objective}")


def set_job_objective(  # noqa: ANN201 # Baseline
    job_run: MetadataEnrichmentAssetEnrichmentJob,
    objectives: list[MetadataEnrichmentObjective],
):
    job_run_options = job_run.delegate_configuration.enrichment_objective.enrichment_options.structured
    for objective in objectives:
        match objective:
            case MetadataEnrichmentObjective.PROFILE:
                job_run_options.profile = True
            case MetadataEnrichmentObjective.DQ_GEN_CONSTRAINTS:
                job_run_options.dq_gen_constraints = True
            case MetadataEnrichmentObjective.ANALYZE_QUALITY:
                job_run_options.analyze_quality = True
            case MetadataEnrichmentObjective.SEMANTIC_EXPANSION:
                job_run_options.semantic_expansion = True
            case MetadataEnrichmentObjective.ASSIGN_TERMS:
                job_run_options.assign_terms = True
            case MetadataEnrichmentObjective.ANALYZE_RELATIONSHIPS:
                job_run_options.analyze_relationships = True
            case MetadataEnrichmentObjective.DQ_SLA_ASSESSMENT:
                job_run_options.dq_sla_assessment = True
            case MetadataEnrichmentObjective.DATA_SEARCH:
                job_run_options.data_search = True
            case _:
                raise ValueError(f"Invalid objective: {objective}")


def generate_metadata_enrichment_asset(
    asset_name: str,
    description: str,
    dataset_uuids: list[str],
    metadata_import_uuids: Optional[list[str]] = None,  # noqa: UP045 # Baseline
    tags: Optional[list[str]] = None,  # noqa: UP045 # Baseline
) -> MetadataEnrichmentAsset:
    """
    Generates a default MetadataEnrichmentAsset with specified parameters.

    Args:
        asset_name (str): The name of the MetadataEnrichmentAsset.
        description (str): The description of the MetadataEnrichmentAsset.
        dataset_uuids (list[str]): List of dataset UUIDs for the asset.
        metadata_import_uuids (list[str]): List of MDI UUIDs for the asset.
        tags (list[str]): List of tags for the asset.

    Returns:
        MetadataEnrichmentAsset: A default configured MetadataEnrichmentAsset.
    """
    mde_asset = MetadataEnrichmentAsset(name=asset_name)
    mde_asset.description = description
    mde_asset.data_scope.enrichment_assets = dataset_uuids
    mde_asset.tags = tags
    if metadata_import_uuids:
        metadata_imports = ContainerAssets(metadata_imports=metadata_import_uuids)
        mde_asset.data_scope.container_assets = metadata_imports
    return mde_asset


def generate_metadata_enrichment_job_run(
    job_name: str,
    category_uuids: list[str],
    objectives: list[MetadataEnrichmentObjective],
    job_description: Optional[str] = None,  # noqa: UP045 # Baseline
    primary_category_uuid: Optional[str] = None,  # noqa: UP045 # Baseline
) -> MetadataEnrichmentAssetEnrichmentJob:
    """
    Generates a default MetadataEnrichmentAssetEnrichmentJob with specified parameters.

    Args:
        job_name (str): The name of the MetadataEnrichmentAssetEnrichmentJob.
        category_uuids (list[str]): List of category UUIDs for governance scope.
        objectives (list[MetadataEnrichmentObjective]): List of objectives of the MetadataEnrichmentAssetEnrichmentJob.
        job_description (Optional[str]): The description of the MetadataEnrichmentAssetEnrichmentJob.
        primary_category_uuid (str): The primary category UUID for the asset.

    Returns:
        MetadataEnrichmentAssetEnrichmentJob: A default configured MetadataEnrichmentAssetEnrichmentJob.
    """
    job_run: MetadataEnrichmentAssetEnrichmentJob = (
        MetadataEnrichmentAssetEnrichmentJob(name=job_name)
    )
    job_run.description = job_description

    set_job_objective(job_run, objectives)
    for category_uuid in category_uuids:
        job_run.delegate_configuration.enrichment_objective.governance_scope.append(
            GovernanceScopeCategory(id=category_uuid)
        )
    # set primary category id if provided
    if primary_category_uuid:
        term_assignement_objective = TermAssignmentObjective(
            term_generation_target_category_id=primary_category_uuid
        )
        job_run.delegate_configuration.enrichment_objective.term_assignment = (
            term_assignement_objective
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
    job_run.delegate_configuration.enrichment_objective.data_quality.structured.dq_checks_suggested = list_of_dq_checks_suggested
    job_run.delegate_configuration.enrichment_objective.data_quality.structured.quality_origins = quality_origins
    return job_run


async def do_metadata_enrichment_process(
    project_name: str,
    dataset_names: list[str] | str,
    category_names: list[str] | str,
    objectives: list[MetadataEnrichmentObjective],
    job_name: str,
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
        job_name (str): The name of the job for metadata enrichment.

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
            job_name=job_name,
        )
    )
    response_operation = []
    for mde_asset in list_of_mde_assets:
        result = await execute_mde_objective(project_id, job_name, mde_asset)
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

    resource_id = response.get("id")
    status = response.get("status")
    target_resource_id = response.get("target_resource_id")
    target_resource_location = response.get("target_resource_location")

    mde_id = ""
    operation_summary = response.get("operation_summary")
    if operation_summary:
        mde_id = operation_summary.get("mde_id", "")

    mde_url_location = ""

    if mde_id and mde_id.strip():
        mde_url_location = Template(MDE_UI_DISPLAY_TEMPLATE).substitute(
            mde_id=mde_id,
            project_id=project_id,
        )

    mde_response: DataScopeOperation = DataScopeOperation(
        id=resource_id,
        status=status,
        target_resource_id=target_resource_id,
        target_resource_location=target_resource_location,
        mde_url_location=mde_url_location,
        operation_summary=operation_summary,
    )

    LOGGER.info(
        f"Successfully created metadata enrichment asset. Response: {mde_response}"
    )

    return mde_response


async def check_if_datasets_assigned_to_mde(  # noqa: ANN201 # Baseline
    dataset_ids: list[str], dataset_names: list[str], project_id: str
):
    dataset_names_in_mde = []
    for dataset_id, dataset_name in zip(dataset_ids, dataset_names):  # noqa: B905 # Baseline
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
    job_name: Optional[str] = None,  # noqa: UP045 # Baseline
) -> list[MetadataEnrichmentAssetInfo]:
    """
    Create or find Metadata Enrichment Assets based on provided data asset IDs.

    This function either finds existing Metadata Enrichment Assets for given data assets or creates new ones if they don't exist.

    Args:
        project_id (str): The ID of the project where the Metadata Enrichment Assets will be created or found.
        data_asset_ids (list[str]): A list of data asset IDs for which to find or create Metadata Enrichment Assets.
        category_ids (list[str]): A list of category IDs associated with the Metadata Enrichment Assets.
        objectives (list[MetadataEnrichmentObjective]): A list of objectives for the Metadata Enrichment Assets.
        job_name (str, optional): The job ID for the Metadata Enrichment Assets. Defaults to None.

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

    # update existing mde with defined objectives if default MDE exists
    for mde_id in mde_to_datasets:
        # No need to update the MDE since is no longer contain the objectives and categories.
        # attempt to update the asset job. If more than one job is defined
        # and the user did not select a job, a ServiceError will be thrown
        await attempt_update_metadata_enrichment_asset_job(
            project_id, mde_id, category_ids, objectives, job_name=job_name
        )

    if data_asset_ids_not_belonging_to_mde:
        if default_mde_id:
            # update default mde with the new assets to be added,
            await call_update_metadata_enrichment_asset(
                project_id,
                default_mde_id,
                datasets_to_add_uuids=data_asset_ids_not_belonging_to_mde,
            )
            # attempt to update the asset job. If more than one job is defined
            # and the user did not select a job, a ServiceError will be thrown
            await attempt_update_metadata_enrichment_asset_job(
                project_id, default_mde_id, category_ids, objectives, job_name=job_name
            )
            mde_to_datasets.setdefault(default_mde_id, []).extend(
                data_asset_ids_not_belonging_to_mde
            )
        else:
            # create new metadata enrichment asset
            # for data asset not belonging to mde if default MDE doesn't exist
            mde_asset = generate_metadata_enrichment_asset(
                asset_name=DEFAULT_MDE_NAME,
                description=DEFAULT_MDE_NAME,
                dataset_uuids=data_asset_ids_not_belonging_to_mde,
            )
            result_operation = await call_create_metadata_enrichment_asset(
                project_id, mde_asset
            )
            # the new MDE V3 API (Multi Jobs support) requires creating the job separetly
            mde_asset_id = result_operation.operation_summary.mde_asset_id
            await attempt_create_metadata_enrichment_asset_job(
                project_id,
                mde_asset_id,
                DEFAULT_MDE_NAME,
                DEFAULT_MDE_NAME,
                category_ids,
                objectives,
            )
            mde_to_datasets[result_operation.target_resource_id] = (
                data_asset_ids_not_belonging_to_mde
            )
            # created/updated metadata enrichment will be executed later
            # so confirm data scope operation is ready
            try:
                await confirm_ready_data_scope_operation(
                    project_id, result_operation.id
                )
            except RetryError:
                raise ServiceError(  # noqa: B904 # Baseline
                    f"The data scope background operation of metadata enrichment asset: {result_operation.target_resource_id} did not finish."
                )

    return [
        MetadataEnrichmentAssetInfo(
            metadata_enrichment_id=mde_id, dataset_ids=mde_to_datasets[mde_id]
        )
        for mde_id in mde_to_datasets
    ]


async def attempt_create_metadata_enrichment_asset_job(  # noqa: ANN201, PLR0913 # Baseline
    project_id: str,
    metadata_enrichment_id: str,
    job_name: str,
    job_description: str,
    category_ids: list[str],
    objectives: list[MetadataEnrichmentObjective],
):
    job_config: MetadataEnrichmentAssetEnrichmentJob = (
        generate_metadata_enrichment_job_run(
            job_name=job_name,
            job_description=job_description,
            objectives=objectives,
            category_uuids=category_ids,
            primary_category_uuid=None,
        )
    )
    await call_create_metadata_enrichment_job_run(
        metadata_enrichment_id, project_id, job_config
    )


async def attempt_update_metadata_enrichment_asset_job(  # noqa: ANN201, PLR0913 # Baseline
    project_id: str,
    metadata_enrichment_id: str,
    category_ids: list[str],
    objectives: list[MetadataEnrichmentObjective],
    job_name: Optional[str] = None,  # noqa: UP045 # Baseline
    job_description: Optional[str] = None,  # noqa: UP045 # Baseline
    job_id: Optional[str] = None,  # noqa: UP045 # Baseline
):

    if job_id is None:
        mde_jobs = await get_metadata_enrichment_asset_jobs(
            project_id, metadata_enrichment_id
        )

        if len(mde_jobs) > 1:
            LOGGER.info(
                f"Found more than one metadata enrichment job for the MDE with ID: {metadata_enrichment_id} Skipping the update."
            )
            raise ServiceError(
                f"Found more than one metadata enrichment job for the MDE with ID: {metadata_enrichment_id}"
                f"the user must select a job to be updated."
            )
        if len(mde_jobs) == 1:
            job_id = mde_jobs[0].id if hasattr(mde_jobs[0], "id") else mde_jobs[0]

    if job_id is None:
        raise ServiceError(
            f"Could not find a job for the MDE with ID: {metadata_enrichment_id}"
        )

    job_config: MetadataEnrichmentAssetEnrichmentJob = (
        generate_metadata_enrichment_job_run(
            job_name=job_name,
            job_description=job_description,
            objectives=objectives,
            category_uuids=category_ids,
            primary_category_uuid=None,
        )
    )
    await call_patch_metadata_enrichment_job_run(
        metadata_enrichment_id, project_id, job_id, job_config
    )


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


async def confirm_ready_data_scope_operation(  # noqa: ANN201 # Baseline
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
    project_id: str,
    job_name: str,
    metadata_enrichment_asset: MetadataEnrichmentAssetInfo,
) -> MetadataEnrichmentRun:
    """
    Executes the Metadata Enrichment (MDE) objective for a given project and asset.

    This function initiates the execution of an MDE job by finding the corresponding job ID,
    executing the metadata enrichment with specified assets, and creating a response object
    containing job and run IDs, project ID, and the MDE UI URL.

    Args:
        project_id (str): The ID of the project for which the MDE objective is to be executed.
        job_name (str): The name of the job to be executed.
        metadata_enrichment_asset (MetadataEnrichmentAssetInfo): The asset information containing
            datasets to be enriched.

    Returns:
        MetadataEnrichmentRun: An object containing job and run IDs, project ID, and MDE UI URL.
    """

    mde_id = metadata_enrichment_asset.metadata_enrichment_id
    if job_name is None:
        mde_jobs = await get_metadata_enrichment_asset_jobs(project_id, mde_id)
        if len(mde_jobs) == 1:
            job_id = mde_jobs[0].id
        else:
            raise ServiceError(
                f"Found multiple jobs for the the MDE {mde_id} and project {project_id}"
                f"Please selected which Job you want to execute"
            )
    else:
        job_id = await confirm_uuid(
            job_name,
            partial(
                find_asset_id_exact_match,
                container_id=project_id,
                artifact_type="job",
                raise_errors=False,
            ),
        )
    if not job_id:
        raise ServiceError(f"No job found with the name {job_name} in the MDE {mde_id}")
    job_run_id = await execute_metadata_enrichment_with_assets(
        mde_id=mde_id,
        project_id=project_id,
        job_id=job_id,
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


async def create_metadata_enrichment(
    project_id: str,
    request: MetadataEnrichmentCreationRequest,
) -> DataScopeOperation:
    LOGGER.info(f"Creating new MDE '{request.metadata_enrichment_name}'")

    if not request.dataset_names and not request.metadata_import_names:
        raise ValidationError(
            message="dataset_names or metadata_import_names are required when creating a new metadata enrichment asset."
            "Please provide at least one dataset.",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_TOOL_NAME,
            remediation_steps="Provide one or more dataset names or metadata import names.",
        )

    dataset_ids: list[str] = await check_and_confirm_dataset_names(
        request.dataset_names, project_id
    )

    metadata_imports_ids = []
    if request.metadata_import_names:
        metadata_import_names = confirm_list_str(request.metadata_import_names)
        metadata_imports_ids = [
            await confirm_uuid(
                metadata_import_name,
                partial(find_metadata_import_id, project_id=project_id),
            )
            for metadata_import_name in metadata_import_names
        ]
    mde_asset: MetadataEnrichmentAsset = generate_metadata_enrichment_asset(
        asset_name=request.metadata_enrichment_name,
        description=request.description,
        dataset_uuids=dataset_ids,
        metadata_import_uuids=metadata_imports_ids,
        tags=request.tags,
    )

    return await call_create_metadata_enrichment_asset(project_id, mde_asset)


async def call_create_metadata_enrichment_job_run(
    mde_asset_id: str,
    project_id: str,
    job_run_config: MetadataEnrichmentAssetEnrichmentJob,
) -> MetadataEnrichmentAssetEnrichmentJobResponse:
    LOGGER.info(f"Creating new Job for MDE '{mde_asset_id}'")

    query_params = {
        "project_id": project_id,
    }
    response = await tool_helper_service.execute_post_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{mde_asset_id}/jobs",
        json=job_run_config.model_dump(exclude_none=True),
        params=query_params,
    )
    LOGGER.info(
        f"Successfully created metadata enrichment asset Job. Response: {response}"
    )
    return MetadataEnrichmentAssetEnrichmentJobResponse.model_validate(response)


async def call_patch_metadata_enrichment_job_run(
    mde_asset_id: str,
    project_id: str,
    job_id: str,
    job_run_config: MetadataEnrichmentAssetEnrichmentJob,
) -> MetadataEnrichmentAssetEnrichmentJobResponse:
    LOGGER.info(f"Patching Job for MDE '{mde_asset_id}'")

    query_params = {
        "project_id": project_id,
    }
    LOGGER.info(
        f"Patching metadata enrichment asset Job with body {job_run_config.model_dump(exclude_none=True)} for job ID:: {job_id}"
    )
    response = await tool_helper_service.execute_patch_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{mde_asset_id}/jobs/{job_id}",
        json=job_run_config.model_dump(exclude_none=True),
        params=query_params,
        headers={"Content-Type": "application/merge-patch+json"},
    )
    LOGGER.info(
        f"Successfully patched metadata enrichment asset Job. Response: {response}"
    )
    return MetadataEnrichmentAssetEnrichmentJobResponse.model_validate(response)


async def update_metadata_enrichment(
    metadata_enrichment_id: str,
    project_id: str,
    request: MetadataEnrichmentCreationRequest,
) -> MetadataEnrichmentAssetPatchResponse:
    LOGGER.info(f"Updating existing MDE {metadata_enrichment_id}")

    if request.dataset_names:
        LOGGER.warning(
            f"dataset_names provided in UPDATE mode but will be ignored. "
            f"Datasets cannot be modified after MDE creation. "
            f"Provided datasets: {request.dataset_names}"
        )

    new_name = request.new_name if request.new_name else None

    datasets_to_add_ids: list[str] = await check_and_confirm_dataset_names(
        request.dataset_names, project_id
    )
    datasets_to_remove_ide: list[str] = await check_and_confirm_dataset_names(
        request.dataset_names_to_remove, project_id, False
    )

    return await call_update_metadata_enrichment_asset(
        project_id=project_id,
        metadata_enrichment_id=metadata_enrichment_id,
        name=new_name,
        description=request.description,
        datasets_to_add_uuids=datasets_to_add_ids,
        datasets_to_remove_uuids=datasets_to_remove_ide,
        tags=request.tags,
    )


async def check_and_confirm_dataset_names(
    dataset_names: list[str], project_id: str, check_mde_assignement: bool = True
) -> list[str]:
    dataset_ids: list[str] = []
    if (isinstance(dataset_names, list) and len(dataset_names) > 0) or (
        isinstance(dataset_names, str) and len(dataset_names) > 0
    ):
        dataset_names = confirm_list_str(dataset_names)
        dataset_ids = [
            await confirm_uuid(
                dataset_name,
                partial(
                    find_asset_id_exact_match,
                    container_id=project_id,
                    raise_errors=False,
                ),
            )
            for dataset_name in dataset_names
        ]
        invalid_count = sum(1 for _id in dataset_ids if not _id)

        if invalid_count > 0:
            LOGGER.warning(
                f"Found {invalid_count} invalid dataset_ids (None or empty) out of {len(dataset_ids)}"
            )

        dataset_ids = [asset_id for asset_id in dataset_ids if asset_id]
        if check_mde_assignement:
            await check_if_datasets_assigned_to_mde(
                dataset_ids, dataset_names, project_id
            )
    return dataset_ids


async def call_update_metadata_enrichment_asset(  # noqa: PLR0913 # Baseline
    project_id: str,
    metadata_enrichment_id: str,
    name: Optional[str] = None,  # noqa: UP045 # Baseline
    description: Optional[str] = None,  # noqa: UP045 # Baseline
    datasets_to_add_uuids: Optional[list[str]] = None,  # noqa: UP045 # Baseline
    datasets_to_remove_uuids: Optional[list[str]] = None,  # noqa: UP045 # Baseline
    tags: Optional[list[str]] = None,  # noqa: UP045 # Baseline
) -> MetadataEnrichmentAssetPatchResponse:
    """
    Update an existing metadata enrichment asset.

    Args:
        project_id: The ID of the project containing the MDE
        metadata_enrichment_id: The ID of the MDE to update
        name: Optional new name for the MDE
        description: Optional new description for the MDE
        datasets_to_add_uuids: Optional list of dataset UUIDs
        datasets_to_remove_uuids: Optional list of dataset UUIDs
        tags: Optional list of tags associated with the governance scope

    Returns:
        MetadataEnrichmentAssetPatchResponse with updated MDE details
    """
    mde_patch = MetadataEnrichmentAssetPatch()
    mde_patch.tags = tags
    # Add name and description to the patch if provided
    if name is not None:
        mde_patch.name = name
    if description is not None:
        mde_patch.description = description

    patch_payload = mde_patch.model_dump(exclude_none=True)

    response = await tool_helper_service.execute_patch_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{metadata_enrichment_id}",
        json=patch_payload,
        params={"project_id": project_id},
        headers={"Content-Type": "application/merge-patch+json"},
    )
    LOGGER.info(f"Successfully updated metadata enrichment asset. Response: {response}")

    if datasets_to_add_uuids or datasets_to_remove_uuids:
        LOGGER.info(
            f"Datasets to add: {datasets_to_add_uuids} | Datasets to remove: {datasets_to_remove_uuids}"
        )
        await call_update_data_scope(
            project_id,
            metadata_enrichment_id,
            datasets_to_add_uuids,
            datasets_to_remove_uuids,
        )

    mde_url_location = Template(MDE_UI_DISPLAY_TEMPLATE).substitute(
        mde_id=metadata_enrichment_id,
        project_id=project_id,
    )

    return MetadataEnrichmentAssetPatchResponse(
        id=metadata_enrichment_id,
        name=response.get("name"),
        mde_url_location=mde_url_location,
    )


async def get_metadata_enrichment_asset_jobs(
    project_id: str, metadata_enrichment_id: str
) -> list[MetadataEnrichmentAssetEnrichmentJobResponse]:

    LOGGER.info(
        f"Retrieving Jobs for project ID: {project_id} AND MDE ID: {metadata_enrichment_id}"
    )

    response = await tool_helper_service.execute_get_request(
        url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{metadata_enrichment_id}/jobs",
        params={"project_id": project_id, "internal": False},
    )

    LOGGER.info(f"Found {len(response.get('jobs'))} jobs. Response: {response}")

    return TypeAdapter(
        list[MetadataEnrichmentAssetEnrichmentJobResponse]
    ).validate_python(response.get("jobs"))


async def call_create_or_update_metadata_enrichment_asset_jobs(  # noqa: PLR0913 # Baseline
    project_name,  # noqa: ANN001 # Baseline
    metadata_enrichment_name,  # noqa: ANN001 # Baseline
    job_name,  # noqa: ANN001 # Baseline
    category_names: list[str],
    objective_names: list[str] | str,
    job_description,  # noqa: ANN001 # Baseline
    primary_category_name,  # noqa: ANN001 # Baseline
) -> MetadataEnrichmentAssetEnrichmentJobResponse:

    project_id = await confirm_uuid(project_name, find_project_id)
    if not project_id:
        LOGGER.info(f"Project ID <{project_name}> not found.")
        raise ServiceError(
            message="Project ID <{project_name}> not found.",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
            remediation_steps="Invoke the tool 'list_containers' with input 'project' to list the available projects.",
        )

    metadata_enrichment_id = await confirm_uuid(
        metadata_enrichment_name,
        partial(find_metadata_enrichment_id, project_id=project_id),
    )

    if not metadata_enrichment_id:
        LOGGER.info(f"MDE '{metadata_enrichment_name}' not found.")
        raise ServiceError(
            message=f"MDE '{metadata_enrichment_name}' not found.",
            tool=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_JOBS_TOOL_NAME,
            remediation_steps="The metadata enrichment with the provided name was not found.",
        )

    LOGGER.info(
        f"Found existing MDE with ID: {metadata_enrichment_id}. Using UPDATE mode."
    )

    objectives = [
        MetadataEnrichmentObjective(objective)
        for objective in confirm_list_str(objective_names)
    ]

    category_ids = [
        await confirm_uuid(category_name, find_category_id)
        for category_name in confirm_list_str(category_names)
    ]

    primary_category_id = None
    if primary_category_name:
        primary_category_id = await confirm_uuid(
            primary_category_name, find_category_id
        )

    job_config: MetadataEnrichmentAssetEnrichmentJob = (
        generate_metadata_enrichment_job_run(
            job_name=job_name,
            job_description=job_description,
            objectives=objectives,
            category_uuids=category_ids,
            primary_category_uuid=primary_category_id,
        )
    )

    job_id = await find_asset_id_exact_match(
        job_name, project_id, "project", "job", raise_errors=False
    )

    if job_id:
        LOGGER.info(f"Found existing job with ID: {job_id}, using UPDATE mode.")
        return await call_patch_metadata_enrichment_job_run(
            metadata_enrichment_id, project_id, job_id, job_config
        )

    LOGGER.info(f"No job was found with the name: {job_name}, using CREATE mode.")
    return await call_create_metadata_enrichment_job_run(
        metadata_enrichment_id, project_id, job_config
    )


async def call_update_data_scope(  # noqa: ANN201 # Baseline
    project_id: str,
    metadata_enrichment_id: str,
    assets_to_add: list[str],
    assets_to_remove: Optional[list[str]] = None,  # noqa: UP045 # Baseline
):
    update_data_scope = MetadataEnrichmentAssetDataScopeUpdateRequest(
        assets_to_add=DataScopeAssetSelection(ids=assets_to_add),
        assets_to_remove=DataScopeAssetSelection(ids=assets_to_remove),
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
) -> Optional[str]:  # noqa: UP045 # Baseline
    must_match = [
        {"match": {METADATA_ARTIFACT_TYPE: ARTIFACT_TYPE_DATA_ASSET}},
        {"match": {"artifact_id": dataset_id}},
        {"match": {ENTITY_ASSETS_PROJECT_ID: project_id}},
    ]
    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json={"query": {"bool": {"must": must_match}}},
        params={"auth_cache": True, "tenant_scope": True},
    )
    LOGGER.info(f"DEBUG:: data_set_id: {dataset_id} ==> metadata result: {response}")
    for row in response.get("rows", []):
        metadata = row["metadata"]
        if metadata["artifact_type"] == ARTIFACT_TYPE_DATA_ASSET:
            return row["entity"]["assets"].get("metadata_enrichment_area_id", None)
    raise ServiceError(
        f"Couldn't find any metadata enrichment assets with the dataset '{dataset_id}' in project '{project_id}'"
    )


async def _paginated_post_request(  # noqa: PLR0913 # Baseline
    url: str,
    payload: Dict[str, Any],  # noqa: UP006 # Baseline
    query_params: Dict[str, Any],  # noqa: UP006 # Baseline
    result_extractor: Callable[[Dict[str, Any]], list],  # noqa: UP006 # Baseline
    limit: Optional[int] = None,  # noqa: UP045 # Baseline
    use_offset: bool = False,
) -> list:
    """
    Helper method for paginated POST requests.

    Args:
        url: The API endpoint URL
        payload: The request payload
        query_params: Query parameters for the request
        result_extractor: Function to extract results from response
        limit: Number of items per page (required when use_offset=True)
        use_offset: Whether to use offset-based pagination (vs bookmark-based)

    Returns:
        List of all collected results across all pages
    """
    all_results = []
    response = None
    offset = 0

    while response is None or response.get("next") is not None:
        # Pagination through offset/limit or bookmark
        if use_offset:
            query_params["limit"] = limit
            query_params["offset"] = offset
        elif response is not None and response.get("next") is not None:
            payload["bookmark"] = response["next"]["bookmark"]

        LOGGER.info(
            f"Executing query with payload: {payload} and query_params: {query_params}"
        )

        response = await tool_helper_service.execute_post_request(
            url=url,
            json=payload,
            params=query_params,
        )

        LOGGER.info("Successfully executed POST request")

        # Extract and collect results
        page_results = result_extractor(response)
        all_results.extend(page_results)

        # Update offset for next iteration if using offset pagination
        if use_offset and response.get("next") is not None:  # noqa: SIM102 # Baseline
            if limit is not None:
                offset += limit

    return all_results


def _check_early_termination(
    batch_number: int,
    has_any_success: bool,
    consecutive_full_failures: int,
    batch_success_count: int,
    batch_total_count: int,
) -> tuple[bool, int]:
    """
    Check if early termination should occur based on failure rate.

    Args:
        batch_number: Current batch number
        has_any_success: Whether any success has been detected
        consecutive_full_failures: Count of consecutive batches with 100% failure
        batch_success_count: Number of successful assets in current batch
        batch_total_count: Total number of assets in current batch

    Returns:
        Tuple of (has_any_success, consecutive_full_failures)

    Raises:
        ServiceError: If early termination criteria is met (without detailed counts)
    """
    # Early termination logic: only check first 2 batches, stop checking after any success
    if not has_any_success and batch_number <= 2:  # noqa: PLR2004 # Baseline
        if batch_success_count > 0:
            has_any_success = True
            consecutive_full_failures = 0
            LOGGER.info(
                "At least one success detected, early termination check disabled"
            )
        elif batch_success_count == 0 and batch_total_count > 0:
            consecutive_full_failures += 1
            LOGGER.warning(
                f"Batch {batch_number} had 100% failure rate (consecutive failures: {consecutive_full_failures})"
            )

            if consecutive_full_failures >= 2:  # noqa: PLR2004 # Baseline
                error_msg = "Batch processing failed: First 2 consecutive batches had 100% failure rate."
                LOGGER.error(error_msg)
                raise ServiceError(error_msg)

    return has_any_success, consecutive_full_failures


async def _run_term_generation_batch(
    batch_asset_ids: list[str],
    metadata_enrichment_asset_id: str,
    query_params: Dict[str, Any],  # noqa: UP006 # Baseline
    category_id: Optional[str] = None,  # noqa: UP045 # Baseline
) -> tuple[list[str], list[AssetProcessingResult]]:
    """
    Process a single batch of assets for term generation.

    Args:
        batch_asset_ids: List of asset IDs to process
        metadata_enrichment_asset_id: The MDE asset ID
        query_params: Query parameters for the API request
        category_id: Optional category ID for V3 MDEs (required for V3, omit for legacy)

    Returns:
        Tuple of (successful_asset_ids, failed_asset_results)
        - successful_asset_ids: list of asset ID strings
        - failed_asset_results: list of AssetProcessingResult with asset_id and error_message

    Raises:
        ValueError: If the MDE is missing required configuration (term_generation_target_category_id)
    """

    # Generates terms for all assets/columns in the batch at the MDE level
    # Note: "columns" is intentionally omitted (not sent as null) — the API
    # rejects a null value for that field with a 400 validation error.
    payload: dict = {"data_asset_ids": batch_asset_ids, "include_columns": True}

    # Add category_id for V3 MDEs
    if category_id:
        payload["term_generation_target_category_id"] = category_id

    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{metadata_enrichment_asset_id}/generate_terms",
            json=payload,
            params=query_params,
        )
    except Exception as e:
        # Check if this is the specific validation error for missing target category
        error_msg = str(e)
        if "400" in error_msg and "term_generation_target_category_id" in error_msg:
            raise ValueError(
                "The Metadata Enrichment Asset is not properly configured. Please add a primary category to the metadata enrichment asset which specifies where the terms should be generated."
            ) from e
        # Re-raise other exceptions
        raise

    successes: list[str] = []
    failures: list[AssetProcessingResult] = []

    for asset_id, asset_result in response.get("asset_results", {}).items():
        status = asset_result.get("status")
        if status and 200 <= status < 300:  # noqa: PLR2004 # Baseline
            successes.append(asset_id)
        else:
            error_msg = asset_result.get("error_message") or None
            LOGGER.warning(
                "Term generation failed for asset %s with status %s: %s",
                asset_id,
                status,
                error_msg,
            )
            failures.append(
                AssetProcessingResult(asset_id=asset_id, error_message=error_msg)
            )

    return successes, failures


async def _retry_failed_assets(
    failed_asset_ids: list[str],
    metadata_enrichment_asset_id: str,
    query_params: Dict[str, Any],  # noqa: UP006 # Baseline
    term_generation_responses: TermGenerationBatchResponse,
    category_id: str | None = None,
) -> None:
    """
    Retry failed assets in batches and update the response object.

    Args:
        failed_asset_ids: List of asset IDs that failed in initial processing
        metadata_enrichment_asset_id: The MDE asset ID
        query_params: Query parameters for the API request
        term_generation_responses: Response object to update with retry results
        category_id: Optional category ID for term generation (for legacy MDEs)
    """
    LOGGER.info(f"Starting retry phase for {len(failed_asset_ids)} failed assets")

    retried_asset_ids = set()
    retry_index = 0
    retry_batch_number = 0

    while retry_index < len(failed_asset_ids):
        retry_batch_end = min(retry_index + BATCH_SIZE_TERM_GEN, len(failed_asset_ids))
        retry_batch_asset_ids = failed_asset_ids[retry_index:retry_batch_end]
        retry_batch_number += 1

        # Filter out already retried assets
        assets_to_retry = [
            aid for aid in retry_batch_asset_ids if aid not in retried_asset_ids
        ]

        if not assets_to_retry:
            retry_index = retry_batch_end
            continue

        LOGGER.info(
            f"Retry batch {retry_batch_number}: retrying {len(assets_to_retry)} assets"
        )

        # Process retry batch using helper function
        retry_successes, retry_failures = await _run_term_generation_batch(
            batch_asset_ids=assets_to_retry,
            metadata_enrichment_asset_id=metadata_enrichment_asset_id,
            query_params=query_params,
            category_id=category_id,  # Pass category_id from parameter
        )

        # Update tracking for retried assets
        for asset_id in retry_successes:
            retried_asset_ids.add(asset_id)
            term_generation_responses.successes.append(
                AssetProcessingResult(asset_id=asset_id)
            )
            # Remove from failures list (was added in initial processing)
            term_generation_responses.failures = [
                f for f in term_generation_responses.failures if f.asset_id != asset_id
            ]

        for failure in retry_failures:
            retried_asset_ids.add(failure.asset_id)
            # Update the existing failure entry with the latest error_message from retry
            for existing in term_generation_responses.failures:
                if existing.asset_id == failure.asset_id:
                    existing.error_message = failure.error_message
                    break

        LOGGER.info(
            f"Retry batch {retry_batch_number} completed: {len(retry_successes)} successes, {len(retry_failures)} final failures"
        )

        # Move to next retry batch
        retry_index = retry_batch_end

    LOGGER.info(
        f"Retry phase completed. Final results: {len(term_generation_responses.successes)} total successes, {len(term_generation_responses.failures)} total failures"
    )


async def _run_term_generation_batch_loop(
    metadata_enrichment_asset_id: str,
    data_asset_ids: list[str],
    query_params: Dict[str, Any],  # noqa: UP006 # Baseline
    category_id: Optional[str],  # noqa: UP045 # Baseline
    log_prefix: str,
) -> TermGenerationBatchResponse:
    """
    Shared batch-loop implementation for term generation (legacy and v3).

    Runs all data assets through batched term generation with retry logic.
    Callers are responsible for building query_params before calling this.

    Args:
        metadata_enrichment_asset_id: The ID of the metadata enrichment asset
        data_asset_ids: List of data asset IDs to process
        query_params: Pre-built query parameters (must include project_id)
        category_id: Optional category ID forwarded to _run_term_generation_batch
        log_prefix: Opening log message distinguishing legacy vs v3 runs

    Returns:
        TermGenerationBatchResponse containing lists of successful and failed asset IDs

    Raises:
        ServiceError: If the first 2 consecutive batches have 100% failure rate
    """
    total_assets = len(data_asset_ids)
    current_index = 0
    term_generation_responses = TermGenerationBatchResponse()

    # Track failed assets for retry and early termination logic
    failed_asset_ids = []
    batch_number = 0
    consecutive_full_failures = 0
    has_any_success = False

    # Phase 1: Initial batch processing
    LOGGER.info(log_prefix)

    while current_index < total_assets:
        batch_end = min(current_index + BATCH_SIZE_TERM_GEN, total_assets)
        batch_asset_ids = data_asset_ids[current_index:batch_end]
        batch_number += 1

        LOGGER.info(
            f"Processing batch {batch_number}: assets {current_index + 1} of {total_assets}"
        )

        batch_successes, batch_failures = await _run_term_generation_batch(
            batch_asset_ids=batch_asset_ids,
            metadata_enrichment_asset_id=metadata_enrichment_asset_id,
            query_params=query_params,
            category_id=category_id,
        )

        # Update response tracking
        for asset_id in batch_successes:
            term_generation_responses.successes.append(
                AssetProcessingResult(asset_id=asset_id)
            )

        for failure in batch_failures:
            failed_asset_ids.append(failure.asset_id)
            term_generation_responses.failures.append(failure)

        LOGGER.info(
            f"Batch {batch_number} completed: {len(batch_successes)} successes, {len(batch_failures)} failures"
        )

        # Check early termination
        has_any_success, consecutive_full_failures = _check_early_termination(
            batch_number=batch_number,
            has_any_success=has_any_success,
            consecutive_full_failures=consecutive_full_failures,
            batch_success_count=len(batch_successes),
            batch_total_count=len(batch_asset_ids),
        )

        current_index = batch_end

    # Phase 2: Retry failed assets once
    if failed_asset_ids:
        await _retry_failed_assets(
            failed_asset_ids=failed_asset_ids,
            metadata_enrichment_asset_id=metadata_enrichment_asset_id,
            query_params=query_params,
            term_generation_responses=term_generation_responses,
            category_id=category_id,
        )
    else:
        LOGGER.info("No failed assets to retry")

    return term_generation_responses


async def call_term_generation_on_metadata_enrichment_asset(
    project_id: str,
    metadata_enrichment_asset_id: str,
    data_asset_ids: list[str],
    category_id: Optional[str] = None,  # noqa: UP045 # Baseline
) -> TermGenerationBatchResponse:
    """
    Call term generation on a legacy metadata enrichment asset.
    Processes asset_ids in batches of 1 with retry logic for failures.

    Args:
        project_id: The ID of the project containing the MDE
        metadata_enrichment_asset_id: The ID of the metadata enrichment asset
        data_asset_ids: List of data asset IDs to generate terms for
        category_id: Optional target category ID (for legacy MDEs that have one configured)

    Returns:
        TermGenerationBatchResponse containing lists of successful and failed asset IDs

    Raises:
        ServiceError: If the first 2 consecutive batches have 100% failure rate
    """
    query_params: Dict[str, Any] = {"project_id": project_id}  # noqa: UP006 # Baseline
    if category_id:
        query_params["category_id"] = category_id

    return await _run_term_generation_batch_loop(
        metadata_enrichment_asset_id=metadata_enrichment_asset_id,
        data_asset_ids=data_asset_ids,
        query_params=query_params,
        category_id=category_id,
        log_prefix=f"Starting initial batch processing for {len(data_asset_ids)} assets",
    )


async def call_term_generation_on_metadata_enrichment_asset_v3(
    project_id: str,
    metadata_enrichment_asset_id: str,
    data_asset_ids: list[str],
    category_id: str,
) -> TermGenerationBatchResponse:
    """
    Call term generation on a V3 metadata enrichment asset with target category.
    Processes asset_ids in batches of 1 with retry logic for failures.

    Args:
        project_id: The ID of the project containing the MDE
        metadata_enrichment_asset_id: The ID of the metadata enrichment asset
        data_asset_ids: List of data asset IDs to generate terms for
        category_id: The target category ID for term generation (required for V3)

    Returns:
        TermGenerationBatchResponse containing lists of successful and failed asset IDs

    Raises:
        ServiceError: If the first 2 consecutive batches have 100% failure rate
    """
    query_params: Dict[str, Any] = {  # noqa: UP006 # Baseline
        "project_id": project_id,
        "category_id": category_id,
    }

    return await _run_term_generation_batch_loop(
        metadata_enrichment_asset_id=metadata_enrichment_asset_id,
        data_asset_ids=data_asset_ids,
        query_params=query_params,
        category_id=category_id,
        log_prefix=f"Starting V3 term generation for {len(data_asset_ids)} assets with category {category_id}",
    )


async def find_data_asset_ids_for_mde_id(
    metadata_enrichment_id: str, project_id: str
) -> list[str]:
    query_params = {
        "project_id": project_id,
    }

    payload = {
        "query": f"({METADATA_ENRICHMENT_AREA_INFO}.{AREA_ID}:{metadata_enrichment_id}) AND (asset.asset_type:data_asset)",
        "limit": 200,
    }

    # Use pagination helper to collect all results
    def extract_asset_ids(response: Dict[str, Any]) -> list[str]:  # noqa: UP006 # Baseline
        return [
            result["metadata"]["asset_id"] for result in response.get("results", [])
        ]

    data_asset_ids = await _paginated_post_request(
        url=BASE_URL + ASSET_TYPE_BASE_ENDPOINT + "/asset/search",
        payload=payload,
        query_params=query_params,
        result_extractor=extract_asset_ids,
    )

    if len(data_asset_ids) == 0:
        raise ServiceError(
            f"Couldn't find any data assets for the metadata enrichment asset with id {metadata_enrichment_id} in project {project_id}"
        )

    return data_asset_ids


async def find_mdes_for_project_id(project_id: str) -> list[str]:
    query_params = {
        "project_id": project_id,
    }

    payload = {"query": "(asset.asset_type:metadata_enrichment_area)", "limit": 200}

    # Use pagination helper to collect all results
    def extract_mdes(response: Dict[str, Any]) -> list:  # noqa: UP006 # Baseline
        return response.get("results", [])

    mdes = await _paginated_post_request(
        url=BASE_URL + ASSET_TYPE_BASE_ENDPOINT + "/asset/search",
        payload=payload,
        query_params=query_params,
        result_extractor=extract_mdes,
    )

    if len(mdes) == 0:
        raise ServiceError(
            f"Couldn't find any MDEs in project {project_id}. Please run the create_metadata_enrichment_area_asset tool to create an MDE"
        )

    return mdes


async def get_workflow_ids_from_project_id(project_id: str) -> list[str]:
    payload = {"conditions": [{"type": "correlation_id", "values": [project_id]}]}

    # Use pagination helper to collect all results
    def extract_workflow_ids(response: Dict[str, Any]) -> list[str]:  # noqa: UP006 # Baseline
        return [
            resource.get("metadata", {}).get("workflow_id")
            for resource in response.get("resources", [])
        ]

    query_params = {"max_number_of_artifacts": 0}

    workflow_ids = await _paginated_post_request(
        url=GET_WORKFLOWS_FROM_CORRELATION_ID_URL,
        payload=payload,
        query_params=query_params,
        result_extractor=extract_workflow_ids,
        limit=1000,
        use_offset=True,
    )

    if len(workflow_ids) > 1:
        raise ServiceError(
            f"Error as there was greater than one workflow id being returned using the project id {project_id}"
        )

    LOGGER.info(f"Workflow Ids: {workflow_ids} returned by project Id: {project_id}")

    return workflow_ids


async def get_draft_terms_from_workflow_ids(workflow_ids: list[str]):  # noqa: ANN201 # Baseline
    draft_terms_in_workflow: list[str] = []
    limit = 1000

    for workflow_id in workflow_ids:
        offset: int = 0
        response = None
        # Loop while there are more pages to fetch
        while response is None or response.get("next") is not None:
            query_params = {"limit": limit, "offset": offset}

            response = await tool_helper_service.execute_get_request(
                url=GET_TERMS_IN_WORKFLOW_URL + f"/{workflow_id}/artifacts",
                params=query_params,
            )

            draft_terms_in_workflow.extend(response.get("resources", []))

            if response.get("next") is not None:
                # 'next' field only exists if pagination is required
                offset += limit

    return draft_terms_in_workflow


def _process_data_asset_resource(resource: Dict[str, Any]) -> DataAssets:  # noqa: UP006 # Baseline
    """
    Process a single data asset resource and count published terms, draft terms and missing terms.

    Args:
        resource: The resource object from /v2/assets/bulk API response

    Returns:
        DataAssets object with id, missing terms, published terms and draft terms counts
    """
    asset_id: str = resource.get("asset_id")  # type: ignore
    entity = resource.get("asset", {}).get("entity", {})

    # Get column_info for published terms
    column_info = entity.get("column_info", {})

    # Get ibm_draft_term_assignments for draft terms
    draft_assignments = entity.get("ibm_draft_term_assignments", {})
    draft_column_info = draft_assignments.get("column_info", {})

    published_count = 0
    draft_count = 0
    missing_count = 0

    # Get all unique column keys from both sources
    all_columns = set(column_info.keys()) | set(draft_column_info.keys())

    for column_key in all_columns:
        # Check published terms
        published_terms = column_info.get(column_key, {}).get("column_terms", [])
        published_len = len(published_terms)

        # Check draft terms
        draft_terms = draft_column_info.get(column_key, {}).get("column_terms", [])
        draft_len = len(draft_terms)

        # Count based on the logic:
        # - If published terms exist, count them
        # - If draft terms exist, count them
        # - If both are 0, it's a gap
        if published_len > 0:
            published_count += published_len

        if draft_len > 0:
            draft_count += draft_len

        if published_len == 0 and draft_len == 0:
            missing_count += 1

    return DataAssets(
        id=asset_id,
        missing_terms_count=missing_count,
        published_terms_count=published_count,
        draft_terms_count=draft_count,
    )


async def _get_and_process_data_assets_in_batches(
    asset_ids: list[str], project_id: str, batch_size: int
) -> tuple[list[DataAssets], list[str]]:
    """
    Fetch and process data assets in batches to count terms and gaps.

    Args:
        asset_ids: List of data asset IDs to fetch and process
        project_id: Project ID for the request
        batch_size: Maximum number of assets per batch

    Returns:
        Tuple of (processed_data_assets list, failed_asset_ids list)

    Raises:
        ServiceError: If the first 2 consecutive batches have 100% failure rate
    """
    # Get assets in batches
    successful_resources, failed_asset_ids = await _get_assets_in_batches(
        asset_ids=asset_ids, project_id=project_id, batch_size=batch_size
    )

    # Process each successful resource
    processed_assets = []
    for resource in successful_resources:
        try:
            data_asset = _process_data_asset_resource(resource)
            processed_assets.append(data_asset)
        except Exception as e:
            asset_id = resource.get("asset_id", "unknown")
            LOGGER.error(f"Failed to process data asset {asset_id}: {e!s}")
            failed_asset_ids.append(asset_id)

    return processed_assets, failed_asset_ids


async def _process_mde_resource(
    resource: Dict[str, Any],  # noqa: UP006 # Baseline
    project_id: str,  # noqa: UP006 # Baseline
) -> MetadataEnrichmentDetails:
    """
    Process a single MDE resource and extract metadata enrichment details.

    Args:
        resource: The resource object from the API response
        project_id: The project ID for URL generation

    Returns:
        MetadataEnrichmentDetails object with extracted information
    """
    asset_id = resource.get("asset_id")

    metadata_enrichment_area = (
        resource.get("asset", {}).get("entity", {}).get("metadata_enrichment_area", {})
    )

    # NOTE: Objectives are no longer extracted for MDE listing.
    # For V3 MDEs, objectives are job-specific (not MDE-level) and shown during job selection.
    # For legacy MDEs, objectives are MDE-level but not critical for initial listing.
    # This design is future-proof for when legacy APIs are deprecated.
    objective = []

    data_assets = metadata_enrichment_area.get("data_scope", {}).get(
        "enrichment_assets", []
    )

    mde_url = Template(MDE_UI_URL_TEMPLATE).substitute(
        mde_id=asset_id, project_id=project_id
    )

    # Fetch and process data assets in batches to get actual term counts
    (
        data_assets_list,
        failed_data_assets,
    ) = await _get_and_process_data_assets_in_batches(
        asset_ids=data_assets, project_id=project_id, batch_size=BATCH_SIZE_MDE
    )

    # Log any failures
    if failed_data_assets:
        LOGGER.warning(
            f"Failed to process {len(failed_data_assets)} data assets for MDE {asset_id}: {failed_data_assets}"
        )

    # Create EnrichmentAssetsInfo object
    enrichment_assets_info = EnrichmentAssetsInfo(
        asset_ids=data_assets_list, asset_count=len(data_assets)
    )

    # Create and return MetadataEnrichmentDetails object
    return MetadataEnrichmentDetails(
        objective=objective,
        name=resource.get("asset", {}).get("metadata", {}).get("name", ""),
        data_assets=enrichment_assets_info,
        mde_url=mde_url,
    )


async def _get_assets_in_batches(
    asset_ids: list[str],
    project_id: str,
    batch_size: int,
) -> tuple[list[dict], list[str]]:
    """
    Fetch assets in batches with early termination.
    Returns raw resources and failed asset IDs.

    Args:
        asset_ids: List of asset IDs to fetch
        project_id: Project ID for the request
        batch_size: Maximum number of assets per batch

    Returns:
        Tuple of (successful_resources list, failed_asset_ids list)

    Raises:
        ServiceError: If the first 2 consecutive batches have 100% failure rate
    """
    successful_resources = []
    failed_asset_ids = []

    # Early termination tracking
    batch_number = 0
    consecutive_full_failures = 0
    has_any_success = False
    total_assets = len(asset_ids)

    LOGGER.info(f"Starting batch processing for {total_assets} assets")

    for i in range(0, len(asset_ids), batch_size):
        batch_asset_ids = asset_ids[i : i + batch_size]
        batch = ",".join(batch_asset_ids)
        batch_number += 1  # noqa: SIM113 # Baseline

        LOGGER.info(
            f"Processing batch {batch_number}: assets {i + 1}-{min(i + batch_size, total_assets)} of {total_assets}"
        )

        query_params = {"project_id": project_id, "asset_ids": batch}

        response = await tool_helper_service.execute_get_request(
            url=BASE_URL + "/v2/assets/bulk",
            params=query_params,
        )

        # Track batch results
        batch_successes = 0
        batch_failures = 0

        for resource in response.get("resources", []):
            asset_id = resource.get("asset_id")
            http_status = resource.get("http_status")

            if http_status != 200:  # noqa: PLR2004 # Baseline
                failed_asset_ids.append(asset_id)
                batch_failures += 1
            else:
                successful_resources.append(resource)
                batch_successes += 1

        LOGGER.info(
            f"Batch {batch_number} completed: {batch_successes} successes, {batch_failures} failures"
        )

        # Check early termination
        has_any_success, consecutive_full_failures = _check_early_termination(
            batch_number=batch_number,
            has_any_success=has_any_success,
            consecutive_full_failures=consecutive_full_failures,
            batch_success_count=batch_successes,
            batch_total_count=len(batch_asset_ids),
        )

    return successful_resources, failed_asset_ids


async def _get_and_process_mde_assets_in_batches(
    asset_ids: list[str], project_id: str, batch_size: int
) -> tuple[dict[str, MetadataEnrichmentDetails], list[str]]:
    """
    Fetch and process MDE assets in batches with early termination.

    Args:
        asset_ids: List of asset IDs to fetch and process
        project_id: Project ID for the request
        batch_size: Maximum number of assets per batch (default: 20)

    Returns:
        Tuple of (mde_details dict, failed_asset_ids list)

    Raises:
        ServiceError: If the first 2 consecutive batches have 100% failure rate
    """
    # Get full MDEs
    successful_resources, failed_asset_ids = await _get_assets_in_batches(
        asset_ids=asset_ids, project_id=project_id, batch_size=batch_size
    )

    # Process full MDE to extract relevant data for user message
    # Filter out MDEs with no data assets
    mde_details: dict[str, MetadataEnrichmentDetails] = {}
    for resource in successful_resources:
        asset_id = resource.get("asset_id")
        if asset_id:
            mde_detail = await _process_mde_resource(resource, project_id)
            # Only include MDEs that have data assets
            if mde_detail.data_assets.asset_count > 0:
                mde_details[asset_id] = mde_detail
            else:
                LOGGER.info(f"Skipping MDE {asset_id} - no data assets found")

    return mde_details, failed_asset_ids


async def process_mdes_for_user_message(
    mdes: list, project_id: str
) -> tuple[dict[str, MetadataEnrichmentDetails], list[str]]:
    """
    Process metadata enrichment assets for user message generation.

    Fetches MDE asset details in batches, processes them, and retries any failures.

    Args:
        mdes: List of MDE objects to process
        project_id: Project ID for the request

    Returns:
        Tuple of (mde_details dict, still_failed_asset_ids list)

    Raises:
        ServiceError: If the first 2 consecutive batches have 100% failure rate
    """
    mde_ids = [mde["metadata"]["asset_id"] for mde in mdes]

    # Process all MDEs in batches
    mde_details, failed_asset_ids = await _get_and_process_mde_assets_in_batches(
        mde_ids, project_id, BATCH_SIZE_MDE
    )

    # Retry failed MDEs
    still_failed_asset_ids = []
    if failed_asset_ids:
        LOGGER.info(f"Retrying {len(failed_asset_ids)} failed MDE assets")
        try:
            (
                retry_mde_details,
                still_failed_asset_ids,
            ) = await _get_and_process_mde_assets_in_batches(
                failed_asset_ids, project_id, BATCH_SIZE_MDE
            )
            # Merge successful retries into main results
            mde_details.update(retry_mde_details)
        except ServiceError:
            # If retry also hits early termination, all failed assets remain failed
            LOGGER.error(
                "Retry phase hit early termination - all failed assets remain failed"
            )
            raise

    LOGGER.info(
        f"Processed {len(mde_details)} metadata enrichment assets, {len(still_failed_asset_ids)} failed"
    )
    return mde_details, still_failed_asset_ids


def get_governance_base_url() -> str:
    """
    Construct the base URL to the governance catalog depending on the enviroment

    Returns:
        The constructed base URL
    """
    if settings.di_env_mode.upper() != ENV_MODE_SAAS:
        return "gov"
    return "governance"


async def call_get_job_status(job_id: str, project_id: str) -> JobRunStatus:
    query_params = {
        "project_id": project_id,
    }
    response = await tool_helper_service.execute_get_request(
        url=f"{BASE_URL}/v2/jobs/{job_id}/runs",
        params=query_params,
    )
    LOGGER.info(f"Successfully retrieved job status. Response: {response}")

    if "results" in response:
        res_results = response["results"]
        if len(res_results) > 0:
            res_result = res_results[0]
            res_job_run = res_result["entity"]["job_run"]
            status = res_job_run["state"]
            run_id = res_result["metadata"]["asset_id"]
            return JobRunStatus(
                status=status,
                run_id=run_id,
            )
    raise AssertionError(f"Could not extract job status from response: {response}")
