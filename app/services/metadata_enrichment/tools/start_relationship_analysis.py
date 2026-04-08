# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.

# This file has been modified with the assistance of IBM Bob AI tool

from functools import partial
from typing import Optional

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import (
    RelationshipAnalysisKeyObjectives,
    RelationshipAnalysisOverwrittenConfig,
    RelationshipAnalysisOverwrittenConfigOptions,
    RelationshipAnalysisType,
    StartRelationshipAnalysisRequest,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    METADATA_ENRICHMENT_SERVICE_URL,
)
from app.services.tool_utils import (
    confirm_list_str,
    find_asset_id_exact_match,
    find_metadata_enrichment_id,
    find_project_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service

TOOL_NAME = "start_metadata_relationship_analysis"


@service_registry.tool(
    name="start_metadata_relationship_analysis",
    description="""Starts a relationship analysis for a metadata enrichment area (MDE).

    This tool initiates relationship analysis on datasets within a metadata enrichment area.
    It supports various analysis types including primary key (PK) and foreign key (FK) analysis
    at both shallow and deep levels, as well as overlap analysis.

    Analysis Types:
    - pk_deep: Deep primary key analysis
    - fk_shallow: Shallow foreign key analysis
    - fk_deep: Deep foreign key analysis
    - overlap: Overlap analysis between datasets

    The tool can analyze either all datasets in the MDE area or specific datasets.
    Optional configuration parameters allow fine-tuning of the analysis behavior.

    The execution process involves:
    1. Confirming the project ID based on the provided project name.
    2. Finding the metadata enrichment area ID based on the MDE area name.
    3. Optionally confirming dataset IDs if specific datasets are provided.
    4. Building the analysis configuration with optional parameters.
    5. Executing the relationship analysis via the API.

    Returns a response containing the job run ID and status of the analysis.""",
)
@auto_context
async def start_relationship_analysis(
    request: StartRelationshipAnalysisRequest,
) -> dict:
    """
    Start relationship analysis for a metadata enrichment area.

    Args:
        request: StartRelationshipAnalysisRequest containing analysis parameters

    Returns:
        dict: Response from the API containing job run information

    Raises:
        ServiceError: If the analysis fails to start or required resources are not found
    """

    LOGGER.info(
        f"start_relationship_analysis called with project_name: {request.project_name}, "
        f"mde_area_name: {request.mde_area_name}, analysis_type: {request.analysis_type}, "
        f"is_all_dataset: {request.is_all_dataset}, dataset_names: {request.dataset_names}, "
        f"sampling_percent: {request.sampling_percent}"
    )

    # Confirm project ID
    project_id = await confirm_uuid(request.project_name, find_project_id)

    # Find metadata enrichment area ID
    mde_area_id = await confirm_uuid(
        request.mde_area_name,
        partial(find_metadata_enrichment_id, project_id=project_id)
    )

    # Prepare dataset IDs if specific datasets are provided
    dataset_ids: Optional[list[str]] = None
    if not request.is_all_dataset:
        if not request.dataset_names:
            raise ServiceError(
                "dataset_names must be provided when is_all_dataset is False"
            )
        dataset_names = confirm_list_str(request.dataset_names)
        dataset_ids = [
            await confirm_uuid(
                dataset_name,
                partial(find_asset_id_exact_match, container_id=project_id)
            )
            for dataset_name in dataset_names
        ]

    # Build overwritten config options based on analysis type requirements
    # API requires ALL common fields to be present if ANY config field is provided
    overwritten_config = None

    # Check if any config field is provided
    has_any_config = any([
        request.max_number_of_multiple_columns is not None,
        request.min_confidence is not None,
        request.auto_selection is not None,
        request.auto_selection_threshold is not None,
        request.pk_min_confidence is not None,
        ])

    # Build config dict - API requires ALL common fields when ANY config is provided
    # Start with defaults for all common fields
    config_dict = {
        'max_number_of_multiple_columns': 3,
        'min_confidence': 0.8,
        'auto_selection': True,
        'auto_selection_threshold': 0.9,
        'pk_min_confidence': 0.9,
    }
    if has_any_config:

        # Override with explicitly provided values
        if request.max_number_of_multiple_columns is not None:
            config_dict['max_number_of_multiple_columns'] = request.max_number_of_multiple_columns
        if request.min_confidence is not None:
            config_dict['min_confidence'] = float(request.min_confidence)
        if request.auto_selection is not None:
            config_dict['auto_selection'] = request.auto_selection
        if request.auto_selection_threshold is not None:
            config_dict['auto_selection_threshold'] = request.auto_selection_threshold
        if request.pk_min_confidence is not None:
            config_dict['pk_min_confidence'] = request.pk_min_confidence

    # Create config options with all required fields
    config_options = RelationshipAnalysisOverwrittenConfigOptions(**config_dict)
    overwritten_config = RelationshipAnalysisOverwrittenConfig(options=config_options)

    # Build key analysis objectives
    key_objectives = RelationshipAnalysisKeyObjectives(
        type=request.analysis_type,
        overwritten_config=overwritten_config,
        is_all_dataset=request.is_all_dataset,
        sampling_percent=request.sampling_percent,
        dataset_ids=dataset_ids,
        updated_dataset_ids=None,  # Not used in initial request
    )

    # Prepare API request
    url = f"{METADATA_ENRICHMENT_SERVICE_URL}/metadata_enrichment_assets/{mde_area_id}/start_relationship_analysis"
    query_params = {"project_id": project_id}
    payload = {
        "key_analysis_objectives": key_objectives.model_dump(
            exclude_none=True, by_alias=True
        )
    }

    LOGGER.info(f"Sending relationship analysis request to: {url}")
    LOGGER.debug(f"Request payload: {payload}")

    try:
        response = await tool_helper_service.execute_post_request(
            url=url,
            params=query_params,
            json=payload,
            tool_name=TOOL_NAME,
        )
        LOGGER.info(f"Successfully started relationship analysis. Response: {response}")
        return response
    except Exception as e:
        LOGGER.error(
            f"Failed to start relationship analysis for MDE area {mde_area_id}: {str(e)}"
        )
        raise ServiceError(
            f"Failed to start relationship analysis: {str(e)}"
        )


@service_registry.tool(
    name="start_metadata_relationship_analysis",
    description="""Starts a relationship analysis for a metadata enrichment area (MDE).

    This tool initiates relationship analysis on datasets within a metadata enrichment area.
    It supports various analysis types including primary key (PK) and foreign key (FK) analysis
    at both shallow and deep levels, as well as overlap analysis.

    Analysis Types:
    - pk_deep: Deep primary key analysis
    - fk_shallow: Shallow foreign key analysis
    - fk_deep: Deep foreign key analysis
    - overlap: Overlap analysis between datasets

    The tool can analyze either all datasets in the MDE area or specific datasets.
    Optional configuration parameters allow fine-tuning of the analysis behavior.""",
)
@auto_context
async def wxo_start_relationship_analysis(
    project_name: str,
    mde_area_name: str,
    analysis_type: str,
    is_all_dataset: bool = True,
    dataset_names: Optional[list[str] | str] = None,
    sampling_percent: int = 0,
    max_number_of_multiple_columns: Optional[int] = None,
    min_confidence: Optional[float] = None,
    auto_selection: Optional[bool] = None,
    auto_selection_threshold: Optional[float] = None,
    pk_min_confidence: Optional[float] = None,
) -> dict:
    """Watsonx Orchestrator compatible version that expands StartRelationshipAnalysisRequest into individual parameters."""

    request = StartRelationshipAnalysisRequest(
        project_name=project_name,
        mde_area_name=mde_area_name,
        analysis_type=RelationshipAnalysisType(analysis_type),
        is_all_dataset=is_all_dataset,
        dataset_names=dataset_names,
        sampling_percent=sampling_percent,
        max_number_of_multiple_columns=max_number_of_multiple_columns,
        min_confidence=min_confidence,
        auto_selection=auto_selection,
        auto_selection_threshold=auto_selection_threshold,
        pk_min_confidence=pk_min_confidence,
    )
    return await start_relationship_analysis(request)