# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Note: This tool integrates with Metadata Enrichment Asset APIs that are actively maintained
# and subject to change. While we strive to keep this tool synchronized with the latest API versions,
# temporary discrepancies in behavior may occur between API updates and tool updates.


from functools import partial
from typing import Annotated, Optional, Union

from pydantic import Field

from app.core.registry import service_registry
from app.services.metadata_enrichment.constants import CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_TOOL_NAME
from app.services.metadata_enrichment.models.metadata_enrichment import (
    MetadataEnrichmentCreationRequest,
    DataScopeOperation,
    MetadataEnrichmentAssetPatchResponse,
)
from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (
    create_metadata_enrichment, update_metadata_enrichment,
)
from app.services.tool_utils import (
    find_metadata_enrichment_id,
    find_project_id, )
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import confirm_uuid


async def _create_or_update_metadata_enrichment_asset(
    request: MetadataEnrichmentCreationRequest,
) -> Union[DataScopeOperation, MetadataEnrichmentAssetPatchResponse]:

    LOGGER.info(
        f"create_or_update_metadata_enrichment_asset called with project_name: {request.project_name}, "
        f"asset_name: {request.metadata_enrichment_name}"
        f"dataset_names: {request.dataset_names}, metadata_import_names: {request.metadata_import_names}, "
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

    if metadata_enrichment_id:
        return await update_metadata_enrichment(metadata_enrichment_id,project_id, request)
    else:
        return await create_metadata_enrichment(project_id, request)

@service_registry.tool(
    name=CREATE_OR_UPDATE_METADATA_ENRICHMENT_ASSET_TOOL_NAME,
    description="""Use this tool when you need to creates a new metadata enrichment (MDE) asset or updates an existing one within a specified project.

    **IMPORTANT:** 
    - Do not make assemptions or add any values the user did not provide in his prompt.
    - FOllow the user instructions to the letter.
    
    This tool automatically detects whether to create or update based on whether an MDE with the given name exists

    CREATE MODE (when MDE doesn't exist):
    - Requires: metadata_enrichment_name, dataset_names or metadata_import_names
    - Creates a new metadata enrichment asset with the specified datasets
    - Validates that datasets exist and aren't already assigned to other MDEs
    - Returns DataScopeOperation with details of the newly created asset

    UPDATE MODE (when MDE exists):
    - Requires: metadata_enrichment_name
    - Optional: dataset_names to specify the datasets to be added and dataset_names_to_remove to specify the datasets to be removed
    - Returns MetadataEnrichmentAssetPatchResponse with updated MDE details
    
    The function assumes that the datasets provided are valid and exist.
    It does not handle the creation of datasets or categories if they do not already exist.
    """,
    annotations={
        "title": "Create or Update Metadata Enrichment Asset Configuration",
        "destructiveHint": True
    }
)
@auto_context
async def create_or_update_metadata_enrichment_asset(
    project_name: Annotated[str, Field(description="The name of the project.")],
    metadata_enrichment_name: Annotated[str, Field(description="The name of the metadata enrichment asset. Used to find existing MDE (for update) or as the name for new MDE (for create).")],
    dataset_names: Annotated[Optional[list[str] | str], Field(description="""Dataset names to include in the metadata enrichment asset. 
                                                              - CREATE mode: Required (must be provided)""")] = None,
    dataset_names_to_remove: Annotated[Optional[list[str]], Field(description="""Dataset names to remove from the metadata enrichment asset. 
                                                                  - CREATE mode: Ignored (should not be provided) 
                                                                  - UPDATE mode: Optional (only updates if provided)""")] = None,
    metadata_import_names: Annotated[Optional[list[str] | str], Field(description="List of names of metadata imports to import into the metadata enrichment asset.")] = None,
    description: Annotated[Optional[str], Field(description="Description of the metadata enrichment asset. Used in both create and update modes.")] = None,
    new_name: Annotated[Optional[str], Field(description="New name for the metadata enrichment asset. Only used in UPDATE mode to rename the MDE. Ignored in CREATE mode.")] = None,
    tags: Annotated[Optional[list[str]], Field(description="A list of tags to assign. Max items: 1000")] = None,
) -> Union[DataScopeOperation, MetadataEnrichmentAssetPatchResponse]:
    """Wrapper that expands MetadataEnrichmentCreationRequest into individual parameters."""

    request = MetadataEnrichmentCreationRequest(
        project_name=project_name,
        metadata_enrichment_name=metadata_enrichment_name,
        dataset_names=dataset_names,
        dataset_names_to_remove=dataset_names_to_remove,
        metadata_import_names=metadata_import_names,
        description=description,
        new_name=new_name,
        tags=tags,
    )
    return await _create_or_update_metadata_enrichment_asset(request)
