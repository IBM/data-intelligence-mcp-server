# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated, List, Optional, Union
from pydantic import Field

from app.core.registry import service_registry
from app.services.metadata_import.models.edit_metadata_import import (
    EditImportOptions,
    EditMetadataImportRequest,
    EditMetadataImportResponse,
    EditReimportOptions,
)
from app.services.metadata_import.models.create_metadata_import import (
    MetadataImport,
)
from app.services.tool_utils import (
    find_project_id,
    find_metadata_import_id,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service, create_default_headers
from app.services.constants import METADATA_IMPORT_BASE_ENDPOINT, JSON_CONTENT_TYPE
from app.services.metadata_import.tools.create_metadata_import import get_metadata_import_resource_uri


async def _edit_metadata_import(
    request: EditMetadataImportRequest
) -> EditMetadataImportResponse:
    """
    Edit an existing metadata import asset in a project.
    
    This tool allows you to update description, scope, and/or tags
    of a metadata import asset. All fields are optional - provide only
    the fields you want to update. At least one field must be provided.
    
    Args:
        request: EditMetadataImportRequest containing project name,
                 metadata import name, and optional update fields
    
    Returns:
        EditMetadataImportResponse containing success message,
        metadata import ID, name, and UI URL
    
    Raises:
        ServiceError: If project or metadata import not found
        ValidationError: If no fields provided for update or invalid JSON in scope
        ExternalAPIError: If API request fails
    """
    
    LOGGER.info(
        "Editing metadata import '%s' in project '%s'",
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
    
    # Build dynamic PATCH payload based on provided fields
    patch_payload = {}
    updated_fields = []

    if request.description is not None:
        patch_payload["description"] = request.description
        updated_fields.append("description")

    if request.scope is not None:
        patch_payload["scope"] = {"paths": request.scope}
        updated_fields.append("scope to %d path(s)" % len(request.scope))

    if request.tags is not None:
        patch_payload["tags"] = request.tags
        updated_fields.append("tags to %d tag(s)" % len(request.tags))

    if request.import_type is not None:
        patch_payload["import_type"] = request.import_type.value
        updated_fields.append("import_type")

    if request.reimport_options is not None:
        patch_payload["reimport_options"] = request.reimport_options.model_dump()
        updated_fields.append("reimport_options")

    if request.import_options is not None:
        patch_payload["import_options"] = request.import_options.model_dump()
        updated_fields.append("import_options")

    LOGGER.debug("Constructing PATCH payload with fields: %s", updated_fields)
    
    # Execute PATCH request
    patch_url = f"{tool_helper_service.base_url}{METADATA_IMPORT_BASE_ENDPOINT}/{metadata_import_id}"
    
    response = await tool_helper_service.execute_patch_request(
        url=patch_url,
        headers=create_default_headers(content_type=JSON_CONTENT_TYPE),
        json=patch_payload,
        params={"project_id": project_id},
        tool_name="update_metadata_import",
    )
    
    # Parse response
    mdi = MetadataImport.model_validate(response)
    mdi_url = get_metadata_import_resource_uri(
        mdi_id=mdi.metadata.asset_id, project_id=mdi.metadata.project_id
    )
    
    # Build success message
    message = (
        f"The metadata import '{request.metadata_import_name}' has been successfully updated in project '{request.project_name}'. "
        f"Updated: {', '.join(updated_fields)}. "
        f"View the updated metadata import at [{mdi_url}]({mdi_url})."
    )
    
    LOGGER.info(
        "Successfully updated metadata import '%s'",
        request.metadata_import_name,
    )
    
    return EditMetadataImportResponse(
        message=message,
        metadata_import_id=metadata_import_id,
        metadata_import_name=request.metadata_import_name,
        metadata_import_asset_ui_url=mdi_url,
    )


@service_registry.tool(
    name="update_metadata_import",
    description="""Edit an existing metadata import asset in a project.

    This tool allows you to update any combination of: description, scope, tags,
    import_type, reimport_options, and import_options. All fields are optional - provide only
    the fields you want to update. At least one field must be provided.

    For reimport_options and import_options, all keys must be provided when the object is supplied.

    import_options keys (all bool): exclude_tables, exclude_views,
    import_incremental_changes_only, include_foreign_key, include_primary_key,
    include_asset_lifecycle_timestamps, metadata_from_catalog_table_only.

    reimport_options keys (all bool): update_name, update_description,
    update_column_descriptions, delete_when_deleted_at_source, delete_when_removed_from_scope.

    EXAMPLES:
    - Update tags: tags=["new_tag", "another_tag"]
    - Update description: description="Updated description"
    - Update scope: scope=["/schema1", "/schema2"]
    - Enable primary key, disable foreign key (all other import_options fields must also be provided):
      import_options={"include_primary_key": true, "include_foreign_key": false, "exclude_tables": false, "exclude_views": false, "import_incremental_changes_only": false, "include_asset_lifecycle_timestamps": false, "metadata_from_catalog_table_only": false}

    ERROR HANDLING:
    - If project not found: Use 'list_containers' to find available projects
    - If metadata import not found: Use 'search_metadata_import' to find existing imports

    Returns: Success message with updated asset details and UI URL.""",
    tags={"metadata-import", "edit-metadata-import", "update-metadata-import","metadata_management_and_governance"},
    meta={"version": "2.0", "service": "metadata-import"},
    annotations={
        "title": "Edit Metadata Import in a Project",
        "destructiveHint": True
    }
)
@auto_context
async def edit_metadata_import(
    project_name: Annotated[str, Field(description="The name of the project containing the metadata import.")],
    metadata_import_name: Annotated[str, Field(description="The name of the metadata import asset to edit.")],
    description: Annotated[Optional[str], Field(description="New description for the metadata import.")] = None,
    scope: Annotated[Optional[Union[List[str], str]], Field(description="List of schema/table paths to set as the import scope.")] = None,
    tags: Annotated[Optional[List[str]], Field(description="List of tags to assign to the metadata import.")] = None,
    import_type: Annotated[Optional[str], Field(description="The import type to set (e.g. 'metadata').")] = None,
    reimport_options: Annotated[Optional[EditReimportOptions], Field(description="Options controlling re-import behaviour. All keys must be provided when supplied.")] = None,
    import_options: Annotated[Optional[EditImportOptions], Field(description="Options controlling what metadata is imported. All keys must be provided when supplied.")] = None,
) -> EditMetadataImportResponse:
    """Wrapper that expands EditMetadataImportRequest object into individual parameters."""
    request = EditMetadataImportRequest(
        project_name=project_name,
        metadata_import_name=metadata_import_name,
        description=description,
        scope=scope,
        tags=tags,
        import_type=import_type,
        reimport_options=reimport_options,
        import_options=import_options,
    )

    return await _edit_metadata_import(request)
