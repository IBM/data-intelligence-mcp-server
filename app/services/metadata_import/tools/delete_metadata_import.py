# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated
from pydantic import Field
from app.core.registry import service_registry
from app.services.metadata_import.models.delete_metadata_import import (
    DeleteMetadataImportRequest,
    DeleteMetadataImportResponse,
)
from app.services.tool_utils import find_project_id, find_metadata_import_id
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import METADATA_IMPORT_BASE_ENDPOINT


async def _delete_metadata_import(
    request: DeleteMetadataImportRequest
) -> DeleteMetadataImportResponse:
    """
    Permanently delete a metadata import asset from a project.
    
    This action cannot be undone. The metadata import asset and its
    configuration will be removed from the project.
    
    Args:
        request: DeleteMetadataImportRequest containing project name
                 and metadata import name
        
    Returns:
        DeleteMetadataImportResponse containing confirmation message,
        metadata import ID, and name
        
    Raises:
        ServiceError: If project or metadata import not found
        ExternalAPIError: If API request fails
    """
    
    LOGGER.info(
        "Deleting metadata import '%s' from project '%s'",
        request.metadata_import_name,
        request.project_name,
    )
    
    # Resolve project_id and metadata_import_id
    project_id = await find_project_id(request.project_name)
    LOGGER.debug("Found project ID: %s", project_id)
    
    metadata_import_id = await find_metadata_import_id(
        request.metadata_import_name, project_id
    )
    LOGGER.debug("Found metadata import ID: %s", metadata_import_id)
    
    # Execute DELETE request
    delete_url = f"{tool_helper_service.base_url}{METADATA_IMPORT_BASE_ENDPOINT}/{metadata_import_id}"
    
    await tool_helper_service.execute_delete_request(
        url=delete_url,
        params={"project_id": project_id},
        tool_name="delete_metadata_import",
    )
    
    message = (
        f"The metadata import '{request.metadata_import_name}' has been successfully deleted "
        f"from project '{request.project_name}'."
    )
    
    LOGGER.info(
        "Successfully deleted metadata import '%s'",
        request.metadata_import_name,
    )
    
    return DeleteMetadataImportResponse(
        message=message,
        metadata_import_id=metadata_import_id,
        metadata_import_name=request.metadata_import_name,
    )


@service_registry.tool(
    name="delete_metadata_import",
    description="""Destructive: This tool permanently deletes a metadata import asset. This action cannot be undone.
    
    ERROR HANDLING:
    - If project not found: Use 'list_containers' to find available projects
    - If metadata import not found: Use 'search_metadata_import' to find existing imports
    
    Returns: Success message confirming the deletion.""",
    tags={"metadata-import", "delete-metadata-import","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "metadata-import"},
    annotations={
        "title": "Delete Metadata Import from a Project",
        "destructiveHint": True
    }
)
@auto_context
async def delete_metadata_import(
    project_name: Annotated[str, Field(description="The name of the project containing the metadata import.")],
    metadata_import_name: Annotated[str, Field(description="The name of the metadata import asset to delete.")],
) -> DeleteMetadataImportResponse:
    """Wrapper that expands DeleteMetadataImportRequest object into individual parameters."""
    request = DeleteMetadataImportRequest(
        project_name=project_name,
        metadata_import_name=metadata_import_name,
    )
    
    return await _delete_metadata_import(request)