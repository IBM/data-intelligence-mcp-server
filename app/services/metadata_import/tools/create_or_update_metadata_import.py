# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json
import uuid
from typing import Annotated, List, Optional, Union

from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import JSON_CONTENT_TYPE, METADATA_IMPORT_BASE_ENDPOINT
from app.services.metadata_import.models.create_metadata_import import (
    CreateMetadataImportResponse,
    ImportOptions,
    MetadataImport,
    MetadataImportRequest,
    MetadataImportScope,
    ReimportOptions,
)
from app.services.metadata_import.models.edit_metadata_import import (
    EditImportOptions,
    EditMetadataImportResponse,
    EditReimportOptions,
)
from app.services.tool_utils import (
    find_catalog_id,
    find_connection_id,
    find_metadata_import_id,
    find_project_id,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import create_default_headers, tool_helper_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _create_mdi(
    project_name: str,
    connection_name: str,
    scope: Union[List[str], str],
    name: Optional[str],
    catalog_name: Optional[str],
    tags: Optional[List[str]],
    migrate_tags: Optional[bool],
    reimport_options: Optional[ReimportOptions],
    import_options: Optional[ImportOptions],
) -> CreateMetadataImportResponse:
    """Execute the POST (create) path."""
    LOGGER.info(
        "create_or_update_metadata_import → CREATE mode: project=%s connection=%s scope=%s",
        project_name, connection_name, scope,
    )

    normalized = _normalize_scope(scope)
    if normalized is None or len(normalized) == 0:
        normalized = ["/"]

    project_id = await find_project_id(project_name)
    connection_id = await find_connection_id(connection_name, project_id, "project")

    target_catalog_id = None
    if catalog_name:
        target_catalog_id = await find_catalog_id(catalog_name)
        LOGGER.info("Resolved catalog '%s' → %s", catalog_name, target_catalog_id)

    target_project_id = None if target_catalog_id else project_id

    import_name = name if name else f"{project_name}_{connection_name}_import_{uuid.uuid4().hex[:2]}"

    _reimport_defaults = MetadataImportRequest.model_fields["reimport_options"].default_factory()
    if reimport_options is not None:
        _reimport_defaults.update(reimport_options.model_dump(exclude_none=True))

    _import_defaults = MetadataImportRequest.model_fields["import_options"].default_factory()
    if import_options is not None:
        _import_defaults.update(import_options.model_dump(exclude_none=True))

    request_body = MetadataImportRequest(
        name=import_name,
        description=f"Import from {connection_name} into {project_name}",
        import_type="metadata",
        connection_id=connection_id,
        target_project_id=target_project_id,
        target_catalog_id=target_catalog_id,
        unified_lineage=True,
        tags=tags if tags is not None else [],
        migrate_tags=migrate_tags if migrate_tags is not None else False,
        reimport_options=_reimport_defaults,
        import_options=_import_defaults,
        scope=MetadataImportScope(paths=normalized),
    )

    payload = request_body.model_dump(exclude_none=True)
    LOGGER.info("POST payload: %s", payload)

    response = await tool_helper_service.execute_post_request(
        url=get_metadata_import_service_url(),
        json=payload,
        params={
            "project_id": project_id,
            "job_name": request_body.name + "_job",
            "create_job": True,
        },
        tool_name="create_or_update_metadata_import",
    )

    mdi = MetadataImport(**response)
    mdi_url = get_metadata_import_resource_uri(
        mdi_id=mdi.metadata.asset_id, project_id=mdi.metadata.project_id
    )

    scope_str = '", "'.join(normalized)
    catalog_info = f" and catalog {catalog_name}" if catalog_name else ""
    message = (
        f'The metadata import has been created in your project {project_name}{catalog_info} '
        f'with connection {connection_name}. The scope of the import is "{scope_str}". '
        f'The URL of the metadata import is [{mdi_url}]({mdi_url}). '
        f'Please review the draft metadata-import at the link above. You may edit the scope, '
        f'advanced options, or import options'
    )
    LOGGER.info("CREATE response: %s", message)
    return CreateMetadataImportResponse(
        message=message,
        metadata_import_asset_ui_url=mdi_url,
        metadata_import_name=import_name,
    )


def _parse_scope_for_update(scope: Optional[Union[List[str], str]]) -> Optional[List[str]]:
    """Normalise scope for the update path (JSON string or list → list)."""
    if scope is None:
        return None
    if isinstance(scope, list):
        return scope
    try:
        parsed = json.loads(scope)
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in scope parameter: {exc}. "
            "Expected a list of path strings, e.g. [\"/schema1\", \"/schema2\"]."
        ) from exc


async def _update_mdi(
    project_name: str,
    metadata_import_name: str,
    description: Optional[str],
    scope: Optional[Union[List[str], str]],
    tags: Optional[List[str]],
    import_type: Optional[str],
    reimport_options: Optional[EditReimportOptions],
    import_options: Optional[EditImportOptions],
) -> EditMetadataImportResponse:
    """Execute the PATCH (update) path."""
    LOGGER.info(
        "create_or_update_metadata_import → UPDATE mode: project=%s mdi=%s",
        project_name, metadata_import_name,
    )

    project_id = await find_project_id(project_name)
    metadata_import_id = await find_metadata_import_id(metadata_import_name, project_id)

    parsed_scope = _parse_scope_for_update(scope)

    patch_payload: dict = {}
    updated_fields: list = []

    if description is not None:
        patch_payload["description"] = description
        updated_fields.append("description")
    if parsed_scope is not None:
        patch_payload["scope"] = {"paths": parsed_scope}
        updated_fields.append("scope to %d path(s)" % len(parsed_scope))
    if tags is not None:
        patch_payload["tags"] = tags
        updated_fields.append("tags to %d tag(s)" % len(tags))
    if import_type is not None:
        patch_payload["import_type"] = import_type
        updated_fields.append("import_type")
    if reimport_options is not None:
        patch_payload["reimport_options"] = reimport_options.model_dump()
        updated_fields.append("reimport_options")
    if import_options is not None:
        patch_payload["import_options"] = import_options.model_dump()
        updated_fields.append("import_options")

    patch_url = f"{tool_helper_service.base_url}{METADATA_IMPORT_BASE_ENDPOINT}/{metadata_import_id}"

    response = await tool_helper_service.execute_patch_request(
        url=patch_url,
        headers=create_default_headers(content_type=JSON_CONTENT_TYPE),
        json=patch_payload,
        params={"project_id": project_id},
        tool_name="create_or_update_metadata_import",
    )

    mdi = MetadataImport.model_validate(response)
    mdi_url = get_metadata_import_resource_uri(
        mdi_id=mdi.metadata.asset_id, project_id=mdi.metadata.project_id
    )

    message = (
        f"The metadata import '{metadata_import_name}' has been successfully updated "
        f"in project '{project_name}'. "
        f"Updated: {', '.join(updated_fields)}. "
        f"View the updated metadata import at [{mdi_url}]({mdi_url})."
    )
    LOGGER.info("UPDATE response: %s", message)
    return EditMetadataImportResponse(
        message=message,
        metadata_import_id=metadata_import_id,
        metadata_import_name=metadata_import_name,
        metadata_import_asset_ui_url=mdi_url,
    )


# ---------------------------------------------------------------------------
# Registered tool
# ---------------------------------------------------------------------------

@service_registry.tool(
    name="create_or_update_metadata_import",
    description=(
        "Create a new metadata import (MDI) in a project, or update an existing one. "
        "Mode is auto-detected: if metadata_import_name is omitted, a new MDI is created (POST); "
        "if metadata_import_name is provided, the existing MDI is updated (PATCH). "
        "PREREQUISITE for create mode: call list_connection_paths FIRST if schemas are not "
        "explicitly provided by the user. "
        "connection_name is required in create mode; ignored in update mode. "
        "Optional import_options keys (all bool, default False): exclude_tables, exclude_views, "
        "import_incremental_changes_only, include_foreign_key, include_primary_key, "
        "include_asset_lifecycle_timestamps, metadata_from_catalog_table_only. "
        "Optional reimport_options keys (all bool): update_name (default True), "
        "update_description (default True), update_column_descriptions (default True), "
        "delete_when_deleted_at_source (default True), delete_when_removed_from_scope (default False). "
        "In update mode all keys must be provided when reimport_options or import_options are supplied. "
        "ERROR HANDLING: if project not found use list_containers; "
        "if metadata import not found use search_metadata_import."
    ),
    tags={"metadata-import", "create-metadata-import", "update-metadata-import", "metadata_management_and_governance"},
    meta={"version": "1.0", "service": "metadata-import"},
    annotations={
        "title": "Create or Update Metadata Import in a Project",
        "destructiveHint": True,
    },
)
@auto_context
async def create_or_update_metadata_import(
    project_name: Annotated[str, Field(description="The name of the project.")],
    scope: Annotated[Optional[Union[List[str], str]], Field(description="List of schema/table paths. Use ['/'] to import all schemas. Required in create mode.")] = None,
    metadata_import_name: Annotated[Optional[str], Field(description="Name of an existing metadata import to update. Omit to create a new one.")] = None,
    connection_name: Annotated[Optional[str], Field(description="Connection to use. Required in create mode; ignored in update mode.")] = None,
    name: Annotated[Optional[str], Field(description="Custom name for the new metadata import (create mode only). Auto-generated if not provided.")] = None,
    catalog_name: Annotated[Optional[str], Field(description="Target catalog name (create mode only). If provided, metadata is stored in this catalog instead of the project.")] = None,
    description: Annotated[Optional[str], Field(description="Description to set or update on the metadata import.")] = None,
    tags: Annotated[Optional[List[str]], Field(description="Tags to assign to the metadata import.")] = None,
    migrate_tags: Annotated[Optional[bool], Field(description="Whether to migrate tags from source during import (create mode only). Defaults to False.")] = False,
    import_type: Annotated[Optional[str], Field(description="The import type to set, e.g. 'metadata' (update mode only).")] = None,
    reimport_options: Annotated[Optional[ReimportOptions], Field(description="Re-import behaviour options. In create mode partial keys are merged with defaults; in update mode all keys must be supplied.")] = None,
    import_options: Annotated[Optional[ImportOptions], Field(description="Import options. In create mode partial keys are merged with defaults; in update mode all keys must be supplied.")] = None,
) -> Union[CreateMetadataImportResponse, EditMetadataImportResponse]:
    """Auto-dispatch to create (POST) or update (PATCH) based on whether metadata_import_name is supplied."""
    if metadata_import_name:
        # UPDATE mode — validate at least one editable field is provided.
        if all(f is None for f in (description, scope, tags, import_type, reimport_options, import_options)):
            raise ValueError(
                "At least one field (description, scope, tags, import_type, "
                "reimport_options, import_options) must be provided to update a metadata import."
            )

        # EditReimportOptions/EditImportOptions require all fields (no defaults).
        # ReimportOptions/ImportOptions have Optional fields — a partially populated
        # instance may contain None values. Merge non-None values onto the known
        # defaults so EditReimportOptions/EditImportOptions can always be constructed.
        _REIMPORT_DEFAULTS = {
            "update_name": True,
            "update_description": True,
            "update_column_descriptions": True,
            "delete_when_deleted_at_source": True,
            "delete_when_removed_from_scope": False,
        }
        _IMPORT_DEFAULTS = {
            "exclude_tables": False,
            "exclude_views": False,
            "import_incremental_changes_only": False,
            "include_foreign_key": False,
            "include_primary_key": False,
            "include_asset_lifecycle_timestamps": False,
            "metadata_from_catalog_table_only": False,
        }

        edit_reimport: Optional[EditReimportOptions] = None
        if reimport_options is not None:
            merged = {**_REIMPORT_DEFAULTS, **reimport_options.model_dump(exclude_none=True)}
            edit_reimport = EditReimportOptions(**merged)

        edit_import: Optional[EditImportOptions] = None
        if import_options is not None:
            merged = {**_IMPORT_DEFAULTS, **import_options.model_dump(exclude_none=True)}
            edit_import = EditImportOptions(**merged)

        return await _update_mdi(
            project_name=project_name,
            metadata_import_name=metadata_import_name,
            description=description,
            scope=scope,
            tags=tags,
            import_type=import_type,
            reimport_options=edit_reimport,
            import_options=edit_import,
        )

    # CREATE mode
    if not connection_name:
        raise ValueError("connection_name is required when creating a new metadata import.")
    if scope is None:
        raise ValueError("scope is required when creating a new metadata import.")

    return await _create_mdi(
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
