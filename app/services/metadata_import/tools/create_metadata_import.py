# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
import json
import uuid
from typing import Optional, List, Union, Annotated
from pydantic import Field
from app.shared.logging import LOGGER, auto_context
from app.core.registry import service_registry
from app.services.tool_utils import find_project_id, find_connection_id, find_catalog_id
from app.shared.utils.tool_helper_service import tool_helper_service

from app.services.metadata_import.models.create_metadata_import import (
    CreateMetadataImportRequest,
    CreateMetadataImportResponse,
    ImportOptions,
    MetadataImportRequest,
    MetadataImport,
    MetadataImportScope,
    ReimportOptions,
)


def get_metadata_import_service_url() -> str:
    """Get the metadata import service URL."""
    return f"{tool_helper_service.base_url}/v2/metadata_imports"


def get_metadata_import_resource_uri(mdi_id: str, project_id: str) -> str:
    """Get the metadata import resource URI."""
    return f"{tool_helper_service.ui_base_url}/gov/metadata-imports/{mdi_id}?project_id={project_id}"


def _normalize_scope(raw_scope) -> Optional[List[str]]:
    """Normalize scope which may be provided as a JSON string, list, or MetadataImportScope object."""
    if isinstance(raw_scope, MetadataImportScope):
        return raw_scope.paths
    if isinstance(raw_scope, list):
        return raw_scope
    try:
        parsed = json.loads(str(raw_scope))
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            return parsed
    except Exception:
        pass
    return None


async def _create_metadata_import(input: CreateMetadataImportRequest) -> CreateMetadataImportResponse:
    """
    Create a metadata import after determining the desired scope of schemas/tables to import.
    Returns:
         str: A descriptive confirmation message with the draft metadata import details,
             including project, connection, scope, and the draft MDI URL
    """

    LOGGER.info(
        "Calling tool 'create_metadata_import' to create a new metadata import - projectName=%s, connectionName=%s, scope=%s",
        input.project_name,
        input.connection_name,
        input.scope,
    )

    scope = _normalize_scope(input.scope)

    if scope is None or len(scope) == 0:
        scope = ["/"]

    project_id = await find_project_id(input.project_name)
    connection_id = await find_connection_id(input.connection_name, project_id, "project")

    target_catalog_id = None
    if input.catalog_name:
        target_catalog_id = await find_catalog_id(input.catalog_name)
        LOGGER.info("Resolved catalog '%s' to ID: %s", input.catalog_name, target_catalog_id)

    # Determine target_project_id based on whether catalog is specified
    target_project_id = None if target_catalog_id else project_id

    # Construct the payload for the service call
    import_name = input.name if input.name else f"{input.project_name}_{input.connection_name}_import_{uuid.uuid4().hex[:2]}"
    
    _reimport_defaults = MetadataImportRequest.model_fields["reimport_options"].default_factory()
    if input.reimport_options is not None:
        _reimport_defaults.update(input.reimport_options.model_dump(exclude_none=True))

    _import_defaults = MetadataImportRequest.model_fields["import_options"].default_factory()
    if input.import_options is not None:
        _import_defaults.update(input.import_options.model_dump(exclude_none=True))

    metadata_import_request = MetadataImportRequest(
        name=import_name,
        description=f"Import from {input.connection_name} into {input.project_name}",
        import_type="metadata",
        connection_id=connection_id,
        target_project_id=target_project_id,
        target_catalog_id=target_catalog_id,
        unified_lineage=True,
        tags=input.tags if input.tags is not None else [],
        migrate_tags=input.migrate_tags,
        reimport_options=_reimport_defaults,
        import_options=_import_defaults,
        scope=MetadataImportScope(paths=scope)
    )

    # Exclude None values from payload - API doesn't accept null for target_project_id
    payload = metadata_import_request.model_dump(exclude_none=True)
    LOGGER.info("Final payload: %s", payload)
    
    response = await tool_helper_service.execute_post_request(
        url=get_metadata_import_service_url(),
        json=payload,
        params={
            "project_id": project_id,
            "job_name": metadata_import_request.name + "_job",
            "create_job": True,
        },
        tool_name="create_metadata_import",
    )

    mdi = MetadataImport(**response)
    mdi_url = get_metadata_import_resource_uri(
        mdi_id=mdi.metadata.asset_id, project_id=mdi.metadata.project_id
    )

    scope_str = '", "'.join(scope)
    catalog_info = f" and catalog {input.catalog_name}" if input.catalog_name else ""
    message = (
        f'The metadata import has been created in your project {input.project_name}{catalog_info} '
        f'with connection {input.connection_name}. The scope of the import is "{scope_str}". '
        f'The URL of the metadata import is [{mdi_url}]({mdi_url}). '
        f'Please review the draft metadata-import at the link above. You may edit the scope, advanced options, or import options'
    )

    LOGGER.info("Returning user-friendly message: %s", message)
    return CreateMetadataImportResponse(
        message=message, 
        metadata_import_asset_ui_url=mdi_url,
        metadata_import_name=import_name)


@service_registry.tool(
    name="create_metadata_import",
    description=(
        "Create a metadata import (MDI) in a project. Optionally specify a catalog to import metadata there instead of the project. "
        "PREREQUISITE: Must call list_connection_paths FIRST if schemas are not explicitly provided by user. "
        "Optional import_options: pass as a JSON object e.g. {\"include_primary_key\": true, \"exclude_views\": true}. "
        "Supported import_options keys (all bool, default False): exclude_tables, exclude_views, "
        "import_incremental_changes_only, include_foreign_key, include_primary_key, "
        "include_asset_lifecycle_timestamps, metadata_from_catalog_table_only. "
        "Optional reimport_options: pass as a JSON object e.g. {\"delete_when_deleted_at_source\": false, \"update_name\": false}. "
        "Supported reimport_options keys (all bool): update_name (default True), update_description (default True), "
        "update_column_descriptions (default True), delete_when_deleted_at_source (default True), "
        "delete_when_removed_from_scope (default False)."
    ),
    tags={"metadata-import","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "metadata-import"},
    annotations={
        "title": "Create Metadata Import in a Project",
        "destructiveHint": True
    }
)
@auto_context
async def create_metadata_import(
    project_name: Annotated[str, Field(description="The name of the project to create the metadata import in.")],
    connection_name: Annotated[str, Field(description="The name of the connection to use for the metadata import.")],
    scope: Annotated[Union[List[str], str], Field(description="List of schema/table paths to import. Use ['/'] to import all schemas.")],
    name: Annotated[Optional[str], Field(description="Optional custom name for the metadata import. Auto-generated if not provided.")] = None,
    catalog_name: Annotated[Optional[str], Field(description="Optional name of a target catalog to import metadata into instead of the project.")] = None,
    tags: Annotated[Optional[List[str]], Field(description="Optional list of tags to assign to the metadata import.")] = None,
    migrate_tags: Annotated[Optional[bool], Field(description="Whether to migrate tags from the source during import. Defaults to False.")] = False,
    reimport_options: Annotated[Optional[ReimportOptions], Field(description="Options controlling re-import behaviour (e.g. update_name, delete_when_deleted_at_source).")] = None,
    import_options: Annotated[Optional[ImportOptions], Field(description="Options controlling what metadata is imported (e.g. include_primary_key, exclude_views).")] = None,
) -> CreateMetadataImportResponse:
    """Wrapper that expands CreateMetadataImportRequest object into individual parameters."""
    request = CreateMetadataImportRequest(
        project_name=project_name,
        connection_name=connection_name,
        scope=scope,
        name=name,
        catalog_name=catalog_name,
        tags=tags,
        migrate_tags=migrate_tags,
        reimport_options=reimport_options,
        import_options=import_options,
    )

    return await _create_metadata_import(request)

