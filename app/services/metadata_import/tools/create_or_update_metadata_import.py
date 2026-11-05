# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json  # noqa: I001 # Baseline
import uuid
from dataclasses import dataclass
from typing import Annotated, List, Optional, Union  # noqa: UP035 # Baseline

from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import JSON_CONTENT_TYPE, METADATA_IMPORT_BASE_ENDPOINT
from app.services.metadata_import.models.create_metadata_import import (
    CreateMetadataImportRequest,
    CreateMetadataImportResponse,
    DatasourceDefinitionInfo,
    FileListItem,
    ImportOptions,
    ImportType,
    LineageMetadataImportRequest,
    MetadataImport,
    MetadataImportRequest,
    MetadataImportScope,
    MetadataImportScopeWithIncludeExclude,
    ReimportOptions,
)
from app.services.metadata_import.models.edit_metadata_import import (
    EditImportOptions,
    EditMetadataImportResponse,
    EditReimportOptions,
)
from app.services.metadata_import.models.get_connection_technology_details import (
    GetConnectionTechnologyDetailsRequest,
    GetConnectionTechnologyDetailsResponse,
    Technology,
)
from app.services.metadata_import.tools.get_connection_technology_details import (
    _get_connection_technology_details,
    get_asset_expansion_set,
    get_phases_for_technology,
)
from app.services.search.tools import search_asset
from app.services.tool_utils import (
    find_catalog_id,
    find_metadata_import_id,
    find_project_id,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import (
    create_default_headers,
    tool_helper_service,
)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def get_metadata_import_service_url() -> str:
    """Get the metadata import service URL."""
    return f"{tool_helper_service.base_url}/v2/metadata_imports"


def get_metadata_import_resource_uri(mdi_id: str, project_id: str) -> str:
    """Get the metadata import resource URI."""
    return f"{tool_helper_service.ui_base_url}/gov/metadata-imports/{mdi_id}?project_id={project_id}"


# ---------------------------------------------------------------------------
# Scope normalisation helpers
# ---------------------------------------------------------------------------


def normalize_scope(
    scope_input: Union[List[str], str, MetadataImportScope, MetadataImportScopeWithIncludeExclude, None],  # noqa: UP006, UP007, UP045 # Baseline
) -> List[str]:  # noqa: UP006 # Baseline
    """Normalize scope input to a list of strings. Returns ["/"] when input is None or empty."""
    if scope_input is None:
        return ["/"]
    if isinstance(scope_input, MetadataImportScope):
        return scope_input.paths
    if isinstance(scope_input, list):
        return scope_input if scope_input else ["/"]
    if isinstance(scope_input, str):
        try:
            parsed = json.loads(scope_input)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                return parsed if parsed else ["/"]
        except Exception:  # noqa: S110 # Baseline
            pass
        return [scope_input]
    return ["/"]


def normalize_lineage_scope(
    include_list: Optional[List[str]],  # noqa: UP006, UP045 # Baseline
    exclude_list: Optional[List[str]],  # noqa: UP006, UP045 # Baseline
) -> tuple[MetadataImportScope | MetadataImportScopeWithIncludeExclude, str]:
    """
    Normalize lineage scope from include/exclude lists.

    Returns MetadataImportScope when the include list resolves to ["/"] and no
    exclude list is provided. Otherwise returns MetadataImportScopeWithIncludeExclude.
    """
    paths = normalize_scope(include_list)
    if paths == ["/"] and not exclude_list:
        return MetadataImportScope(paths=["/"]), "/"
    scope_obj = MetadataImportScopeWithIncludeExclude(
        include_list=paths,
        exclude_list=exclude_list or None,
    )
    scope_message = f'include_list: {", ".join(paths)}'
    if exclude_list:
        scope_message += f', exclude_list: {", ".join(exclude_list)}'
    return scope_obj, scope_message


def _parse_scope_for_update(
    scope: Optional[Union[List[str], str]],  # noqa: UP006, UP007, UP045 # Baseline
) -> Optional[List[str]]:  # noqa: UP006, UP045 # Baseline
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
            'Expected a list of path strings, e.g. ["/schema1", "/schema2"].'
        ) from exc


# ---------------------------------------------------------------------------
# Fixed DSD for OpenLineage imports
# ---------------------------------------------------------------------------

_OPENLINEAGE_DSD_INFO = DatasourceDefinitionInfo(
    data_source_asset_id=None,
    technology=Technology.OPEN_LINEAGE.value,
    scanner=Technology.OPEN_LINEAGE.value,
)


# ---------------------------------------------------------------------------
# Build-context dataclass — bundles shared state for the builder helpers
# ---------------------------------------------------------------------------

@dataclass
class _ImportBuildContext:
    import_name: str
    conn_label: str
    discovery_scope: List[str]  # noqa: UP006 # Baseline
    discovery_scope_message: str
    scope_lineage_obj: MetadataImportScope | MetadataImportScopeWithIncludeExclude | None
    lineage_scope_message: str | None
    target_project_id: Optional[str]  # noqa: UP045 # Baseline
    target_catalog_id: Optional[str]  # noqa: UP045 # Baseline
    effective_scan_phases: Optional[List[str]]  # noqa: UP006, UP045 # Baseline
    tags: List[str]  # noqa: UP006 # Baseline
    migrate_tags: bool
    reimport_defaults: dict
    import_defaults: dict


# ---------------------------------------------------------------------------
# CREATE path — private helpers
# ---------------------------------------------------------------------------

async def _resolve_technology_details(
    request: CreateMetadataImportRequest,
) -> GetConnectionTechnologyDetailsResponse:
    """Resolve technology details for OpenLineage or real-connection paths."""
    if request.is_openlineage:
        project_id = await find_project_id(request.project_name)
        return GetConnectionTechnologyDetailsResponse(
            project_id=project_id,
            connection_id=None,
            dsd=None,
            uses_unified_lineage_discovery=True,
            uses_only_manual_inputs=True,
            imported_asset_types=get_asset_expansion_set(technology=Technology.OPEN_LINEAGE.value),
            scan_phases=get_phases_for_technology(technology=Technology.OPEN_LINEAGE.value),
            technology=Technology.OPEN_LINEAGE.value,
        )
    return await _get_connection_technology_details(
        GetConnectionTechnologyDetailsRequest(
            connection_name=request.connection_name,
            project_name=request.project_name,
        )
    )


def _resolve_scopes(
    request: CreateMetadataImportRequest,
    technology_details: GetConnectionTechnologyDetailsResponse,
) -> tuple[list[str], str, MetadataImportScope | MetadataImportScopeWithIncludeExclude | None, str | None]:
    """Compute discovery and lineage scope objects from the request."""
    if request.scope is not None:
        discovery_scope = normalize_scope(request.scope)
        discovery_scope_message = '", "'.join(discovery_scope)
    else:
        discovery_scope = ["/"]
        discovery_scope_message = 'Scope not found, defaulting to entire datasource ["/"]'

    scope_lineage_obj: MetadataImportScope | MetadataImportScopeWithIncludeExclude | None = None
    lineage_scope_message: str | None = None

    if technology_details.uses_only_manual_inputs:
        scope_lineage_obj = MetadataImportScope(paths=["/"])
        lineage_scope_message = "This technology uses only manual inputs, so scope does not apply"
    elif request.scope_lineage_include_list is not None:
        scope_lineage_obj, lineage_scope_message = normalize_lineage_scope(
            request.scope_lineage_include_list, request.scope_lineage_exclude_list
        )

    return discovery_scope, discovery_scope_message, scope_lineage_obj, lineage_scope_message


def _validate_requirements(
    request: CreateMetadataImportRequest,
    technology_details: GetConnectionTechnologyDetailsResponse,
    discovery_goal_included: bool,
) -> None:
    """Raise ServiceError if any required inputs are missing for the given configuration."""
    dsd = technology_details.dsd
    is_uld_technology = technology_details.uses_unified_lineage_discovery

    if is_uld_technology and discovery_goal_included and not request.is_openlineage:
        if not request.scope_lineage_include_list and not request.scope:
            raise ServiceError(
                "scope or scope_lineage is required when the connection technology uses Unified Lineage Discovery and the import includes discovery",
                remediation_steps=(
                    "Provide either the 'scope' parameter (a schema/database filter) or "
                    "'scope_lineage_include_list' (a list of asset paths to include in lineage discovery) and retry."
                ),
            )
        if not request.catalog_name:
            raise ServiceError(
                "catalog_name is required when the connection technology uses Unified Lineage Discovery and the import includes discovery",
                remediation_steps=(
                    "Provide the 'catalog_name' parameter identifying the catalog where discovered assets will be published and retry."
                ),
            )
        if dsd is None:
            raise _missing_dsd_error()

    if not request.scope and not is_uld_technology and discovery_goal_included:
        raise ServiceError(
            "scope is required when the connection technology does not use Unified Lineage Discovery and the import includes discovery",
            remediation_steps=(
                "Provide the 'scope' parameter (e.g. a schema or database name) to limit the discovery scan and retry."
            ),
        )


def _missing_dsd_error() -> ServiceError:
    """Build the ServiceError raised when a connection has no datasource definition mapping."""
    return ServiceError(
        "Connection does not have mapping to a datasource definition",
        remediation_steps=(
            "Use get_connection_technology_details to inspect the connection and verify it is mapped to a data source definition. "
            "If no mapping exists, create or assign a data source definition for this connection first."
        ),
    )


def _build_dsd_info(
    request: CreateMetadataImportRequest,
    technology_details: GetConnectionTechnologyDetailsResponse,
    require_dsd: bool = True,
) -> Optional[DatasourceDefinitionInfo]:  # noqa: UP045 # Baseline
    """Build DatasourceDefinitionInfo; raises ServiceError when DSD is absent and required."""
    if request.is_openlineage:
        return _OPENLINEAGE_DSD_INFO
    dsd = technology_details.dsd
    if dsd is None:
        if require_dsd:
            raise _missing_dsd_error()
        return None
    return DatasourceDefinitionInfo(
        data_source_asset_id=dsd.id,
        technology=dsd.datasource_type_name,
        scanner=technology_details.technology,
    )


async def _resolve_file_list(
    request: CreateMetadataImportRequest,
    project_id: str,
    technology: str,
) -> Optional[List[FileListItem]]:  # noqa: UP006, UP045 # Baseline
    """Resolve the optional file_list from asset names to FileListItem objects."""
    if not request.file_list:
        return None

    file_list_items: list[FileListItem] = []
    for asset_name in request.file_list:
        found_assets = await search_asset.search_asset(
            search_prompt=asset_name,
            container_type="project",
            container_name=request.project_name,
        )
        for asset in found_assets:
            if asset.name == asset_name and asset.project_id == project_id:
                file_list_items.append(FileListItem(asset_id=asset.id, technology=technology))
                break
        else:
            raise ServiceError(f"Asset with name '{asset_name}' in project '{request.project_name}' was not found")

    return file_list_items


def _merge_options(request: CreateMetadataImportRequest) -> tuple[dict, dict]:
    """Merge caller-supplied reimport_options and import_options into their defaults."""
    reimport_defaults: dict = MetadataImportRequest.model_fields["reimport_options"].default_factory()
    if request.reimport_options is not None:
        reimport_defaults.update(request.reimport_options.model_dump(exclude_none=True))

    import_defaults: dict = MetadataImportRequest.model_fields["import_options"].default_factory()
    if request.import_options is not None:
        import_defaults.update(request.import_options.model_dump(exclude_none=True))

    return reimport_defaults, import_defaults


def _build_metadata_import_for_metadata_type(
    request: CreateMetadataImportRequest,
    technology_details: GetConnectionTechnologyDetailsResponse,
    ctx: _ImportBuildContext,
) -> tuple[MetadataImportRequest | LineageMetadataImportRequest, str, bool]:
    """Build the import request object for ImportType.METADATA."""
    dsd = technology_details.dsd
    is_uld_technology = technology_details.uses_unified_lineage_discovery

    if is_uld_technology and (dsd or request.is_openlineage):
        effective_lineage_scope = ctx.scope_lineage_obj
        effective_lineage_message = ctx.lineage_scope_message
        if not request.scope_lineage_include_list or not ctx.lineage_scope_message:
            effective_lineage_scope = MetadataImportScope(paths=ctx.discovery_scope)
            effective_lineage_message = ctx.discovery_scope_message

        dsd_info = _build_dsd_info(request, technology_details, require_dsd=False)
        dsd_label = Technology.OPEN_LINEAGE.value if request.is_openlineage else dsd.name
        description = f"Import from DSD {dsd_label}, connection {ctx.conn_label} into catalog {request.catalog_name}"
        metadata_import_request = LineageMetadataImportRequest(
            name=ctx.import_name,
            description=description,
            import_type="metadata",
            connection_id=technology_details.connection_id,
            target_project_id=ctx.target_project_id,
            target_catalog_id=ctx.target_catalog_id,
            use_lineage_for_discovery=True,
            scope_lineage=effective_lineage_scope,
            datasource_definition_info=dsd_info,
            lineage_scanning_phases=ctx.effective_scan_phases,
            tags=ctx.tags,
            migrate_tags=ctx.migrate_tags,
            reimport_options=ctx.reimport_defaults,
            import_options=ctx.import_defaults,
        )
        return metadata_import_request, effective_lineage_message, True  # type: ignore[return-value]

    dsd_info = None if not dsd else DatasourceDefinitionInfo(
        data_source_asset_id=dsd.id,
        technology=dsd.datasource_type_name,
        scanner=technology_details.technology,
    )
    metadata_import_request = MetadataImportRequest(
        name=ctx.import_name,
        description=f"Import from {request.connection_name} into {request.project_name if ctx.target_project_id else request.catalog_name}",
        import_type="metadata",
        connection_id=technology_details.connection_id,
        target_project_id=ctx.target_project_id,
        target_catalog_id=ctx.target_catalog_id,
        datasource_definition_info=dsd_info,
        scope=MetadataImportScope(paths=ctx.discovery_scope),
        tags=ctx.tags,
        migrate_tags=ctx.migrate_tags,
        reimport_options=ctx.reimport_defaults,
        import_options=ctx.import_defaults,
    )
    return metadata_import_request, ctx.discovery_scope_message, False


async def _build_metadata_import_for_lineage_types(
    request: CreateMetadataImportRequest,
    technology_details: GetConnectionTechnologyDetailsResponse,
    ctx: _ImportBuildContext,
) -> tuple[LineageMetadataImportRequest, str, bool]:
    """Build the import request object for ImportType.LINEAGE or LINEAGE_AND_DISCOVERY."""
    is_uld_technology = technology_details.uses_unified_lineage_discovery

    scope_lineage_obj = ctx.scope_lineage_obj
    lineage_scope_message = ctx.lineage_scope_message
    if scope_lineage_obj is None or lineage_scope_message is None:
        scope_lineage_obj, lineage_scope_message = normalize_lineage_scope(
            request.scope_lineage_include_list, request.scope_lineage_exclude_list  # type: ignore[arg-type]
        )

    dsd_info = _build_dsd_info(request, technology_details, require_dsd=True)
    if request.is_openlineage:
        dsd_label = Technology.OPEN_LINEAGE.value
    elif technology_details.dsd is not None:
        dsd_label = technology_details.dsd.name
    else:
        raise _missing_dsd_error()

    file_list_items = await _resolve_file_list(request, technology_details.project_id, technology_details.technology)

    if request.import_type == ImportType.LINEAGE:
        description = f"Lineage Import from DSD {dsd_label} and connection {ctx.conn_label} into project {request.project_name}"
        scope_message = lineage_scope_message
        use_lineage_for_discovery = False
        effective_target_catalog_id = None
        discovery_scope_obj = None
    else:
        description = f"Discovery and Lineage Import from {dsd_label} and {ctx.conn_label} into project {request.project_name} and catalog {request.catalog_name}"
        if is_uld_technology:
            discovery_scope_obj = None
            scope_message = lineage_scope_message
            use_lineage_for_discovery = True
        else:
            discovery_scope_obj = MetadataImportScope(paths=ctx.discovery_scope)
            scope_message = f"Discovery: {ctx.discovery_scope_message}, Lineage: {lineage_scope_message}"
            use_lineage_for_discovery = False
        effective_target_catalog_id = ctx.target_catalog_id

    metadata_import_request = LineageMetadataImportRequest(
        name=ctx.import_name,
        description=description,
        connection_id=technology_details.connection_id,
        target_project_id=ctx.target_project_id,
        target_catalog_id=effective_target_catalog_id,
        use_lineage_for_discovery=use_lineage_for_discovery,
        scope=discovery_scope_obj,
        scope_lineage=scope_lineage_obj,
        datasource_definition_info=dsd_info,
        file_list=file_list_items,
        lineage_scanning_phases=ctx.effective_scan_phases,
        tags=ctx.tags,
        migrate_tags=ctx.migrate_tags,
        reimport_options=ctx.reimport_defaults,
        import_options=ctx.import_defaults,
    )

    if request.import_type == ImportType.LINEAGE_AND_DISCOVERY:
        metadata_import_request.import_type = ImportType.LINEAGE_AND_DISCOVERY

    return metadata_import_request, scope_message, use_lineage_for_discovery  # type: ignore[return-value]


async def _create_mdi(request: CreateMetadataImportRequest) -> CreateMetadataImportResponse:
    """Execute the POST (create) path — supports metadata, lineage, and lineage_and_discovery."""
    LOGGER.info(
        "create_or_update_metadata_import → CREATE mode: project=%s connection=%s import_type=%s is_openlineage=%s",
        request.project_name, request.connection_name, request.import_type, request.is_openlineage,
    )

    technology_details = await _resolve_technology_details(request)

    effective_scan_phases = request.scan_phases if request.scan_phases is not None else technology_details.scan_phases

    if not request.imported_asset_types and technology_details.imported_asset_types.default:
        imported_asset_types = technology_details.imported_asset_types.default
    else:
        imported_asset_types = request.imported_asset_types

    project_id = technology_details.project_id
    target_catalog_id = await find_catalog_id(request.catalog_name) if request.catalog_name else None
    target_project_id = None if target_catalog_id else project_id

    conn_label = request.connection_name or Technology.OPEN_LINEAGE.value
    import_name = request.name if request.name else f"{request.project_name}_{conn_label}_import_{uuid.uuid4().hex[:2]}"
    discovery_goal_included = request.import_type in {ImportType.METADATA, ImportType.LINEAGE_AND_DISCOVERY}

    discovery_scope, discovery_scope_message, scope_lineage_obj, lineage_scope_message = _resolve_scopes(
        request, technology_details
    )
    _validate_requirements(request, technology_details, discovery_goal_included)
    reimport_defaults, import_defaults = _merge_options(request)

    ctx = _ImportBuildContext(
        import_name=import_name,
        conn_label=conn_label,
        discovery_scope=discovery_scope,
        discovery_scope_message=discovery_scope_message,
        scope_lineage_obj=scope_lineage_obj,
        lineage_scope_message=lineage_scope_message,
        target_project_id=target_project_id,
        target_catalog_id=target_catalog_id,
        effective_scan_phases=effective_scan_phases,
        tags=request.tags if request.tags is not None else [],
        migrate_tags=request.migrate_tags if request.migrate_tags is not None else False,
        reimport_defaults=reimport_defaults,
        import_defaults=import_defaults,
    )

    if request.import_type == ImportType.METADATA:
        metadata_import_request, scope_message, use_lineage_for_discovery = _build_metadata_import_for_metadata_type(request, technology_details, ctx)
    else:
        metadata_import_request, scope_message, use_lineage_for_discovery = await _build_metadata_import_for_lineage_types(request, technology_details, ctx)

    if imported_asset_types and use_lineage_for_discovery:
        metadata_import_request.import_options["imported_asset_types"] = imported_asset_types

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
        tool_name="create_or_update_metadata_import",
    )

    mdi = MetadataImport(**response)
    mdi_url = get_metadata_import_resource_uri(
        mdi_id=mdi.metadata.asset_id, project_id=mdi.metadata.project_id
    )

    import_type_desc = {
        ImportType.METADATA: "metadata discovery",
        ImportType.LINEAGE: "lineage",
        ImportType.LINEAGE_AND_DISCOVERY: "metadata discovery and lineage",
    }[request.import_type]

    catalog_info = f" and catalog {request.catalog_name}" if request.catalog_name else ""
    message = (
        f"The {import_type_desc} import has been created in your project {request.project_name}{catalog_info} "
        f'with connection {conn_label}. The scope of the import is "{scope_message}". '
        f"The URL of the metadata import is [{mdi_url}]({mdi_url}). "
        f"Please review the draft metadata-import at the link above. You may edit the scope, "
        f"advanced options, or import options"
    )
    LOGGER.info("CREATE response: %s", message)
    return CreateMetadataImportResponse(
        message=message,
        metadata_import_asset_ui_url=mdi_url,
        metadata_import_name=import_name,
    )


# ---------------------------------------------------------------------------
# UPDATE path — private helpers
# ---------------------------------------------------------------------------


async def _update_mdi(  # noqa: PLR0913, PLR0917 # Baseline
    project_name: str,
    metadata_import_name: str,
    description: Optional[str],  # noqa: UP045 # Baseline
    scope: Optional[Union[List[str], str]],  # noqa: UP006, UP007, UP045 # Baseline
    tags: Optional[List[str]],  # noqa: UP006, UP045 # Baseline
    import_type: Optional[str],  # noqa: UP045 # Baseline
    reimport_options: Optional[EditReimportOptions],  # noqa: UP045 # Baseline
    import_options: Optional[EditImportOptions],  # noqa: UP045 # Baseline
) -> EditMetadataImportResponse:
    """Execute the PATCH (update) path."""
    LOGGER.info(
        "create_or_update_metadata_import → UPDATE mode: project=%s mdi=%s",
        project_name,
        metadata_import_name,
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
        updated_fields.append("scope to %d path(s)" % len(parsed_scope))  # noqa: UP031 # Baseline
    if tags is not None:
        patch_payload["tags"] = tags
        updated_fields.append("tags to %d tag(s)" % len(tags))  # noqa: UP031 # Baseline
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
        "CREATE mode supports three import types: "
        "'metadata' (discovery only, default), 'lineage' (lineage only), 'lineage_and_discovery' (both). "
        "PREREQUISITE for create mode: call list_connection_paths FIRST if schemas are not explicitly provided. "
        "connection_name is required in create mode unless is_openlineage=True; ignored in update mode. "
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
    tags={
        "metadata-import",
        "create-metadata-import",
        "update-metadata-import",
        "metadata_management_and_governance",
    },
    meta={"version": "2.0", "service": "metadata-import"},
    annotations={
        "title": "Create or Update Metadata Import in a Project",
        "destructiveHint": True,
    },
)
@auto_context
async def create_or_update_metadata_import(  # noqa: PLR0913, PLR0917 # Baseline
    project_name: Annotated[str, Field(description="Name of the project.")], # NOSONAR
    metadata_import_name: Annotated[Optional[str], Field(description="Name of an existing metadata import to update. Omit to create a new one.")] = None,  # noqa: UP045 # Baseline
    connection_name: Annotated[Optional[str], Field(description="Connection to use. Required in create mode (unless is_openlineage=True); ignored in update mode.")] = None,  # noqa: UP045 # Baseline
    is_openlineage: Annotated[bool, Field(description="Set to True when creating an OpenLineage import. When True, connection_name is not required.")] = False,
    import_type: Annotated[str, Field(description="Type of import: 'metadata' (discovery only, default), 'lineage' (lineage only), or 'lineage_and_discovery' (both). Create mode only.")] = "metadata",
    scope: Annotated[Optional[Union[List[str], str]], Field(description="Schema/table paths for discovery. Use ['/'] for all schemas. Required for 'metadata' and 'lineage_and_discovery' create modes.")] = None,  # noqa: UP006, UP007, UP045 # Baseline
    scope_lineage_include_list: Annotated[Optional[List[str]], Field(description="Include-list for lineage scope. Required for 'lineage' and 'lineage_and_discovery'. Use ['/'] for entire datasource.")] = None,  # noqa: UP006, UP045 # Baseline
    scope_lineage_exclude_list: Annotated[Optional[List[str]], Field(description="Exclude-list for lineage scope. Assets matching these patterns are excluded.")] = None,  # noqa: UP006, UP045 # Baseline
    name: Annotated[Optional[str], Field(description="Custom name for the new metadata import (create mode only). Auto-generated if not provided.")] = None,  # noqa: UP045 # Baseline
    catalog_name: Annotated[Optional[str], Field(description="Target catalog name. Required when Unified Lineage Discovery is used for discovery (create mode only).")] = None,  # noqa: UP045 # Baseline
    description: Annotated[Optional[str], Field(description="Description to set or update on the metadata import.")] = None,  # noqa: UP045 # Baseline
    tags: Annotated[Optional[List[str]], Field(description="Tags to assign to the metadata import.")] = None,  # noqa: UP006, UP045 # Baseline
    migrate_tags: Annotated[Optional[bool], Field(description="Whether to migrate tags from source during import (create mode only). Defaults to False.")] = False,  # noqa: UP045 # Baseline
    file_list: Annotated[Optional[List[str]], Field(description="Optional list of file asset names for lineage imports (create mode only).")] = None,  # noqa: UP006, UP045 # Baseline
    imported_asset_types: Annotated[Optional[List[str]], Field(description="Optional list of asset types to import (create mode only).")] = None,  # noqa: UP006, UP045 # Baseline
    scan_phases: Annotated[Optional[List[str]], Field(description="Optional lineage scan phases. Overrides the technology default (create mode only).")] = None,  # noqa: UP006, UP045 # Baseline
    reimport_options: Annotated[Optional[ReimportOptions], Field(description="Re-import behaviour options. In create mode partial keys are merged with defaults; in update mode all keys must be supplied.")] = None,  # noqa: UP045 # Baseline
    import_options: Annotated[Optional[ImportOptions], Field(description="Import options. In create mode partial keys are merged with defaults; in update mode all keys must be supplied.")] = None,  # noqa: UP045 # Baseline
) -> Union[CreateMetadataImportResponse, EditMetadataImportResponse]:  # noqa: UP007 # Baseline
    """Auto-dispatch to create (POST) or update (PATCH) based on whether metadata_import_name is supplied."""
    if metadata_import_name:
        # UPDATE mode — import_type always has a default value ("metadata"), so it only
        # counts as provided when it differs from that default.
        if import_type == "metadata" and all(
            f is None for f in (description, scope, tags, reimport_options, import_options)
        ):
            raise ValueError(
                "At least one field (description, scope, tags, import_type, "
                "reimport_options, import_options) must be provided to update a metadata import."
            )

        # EditReimportOptions/EditImportOptions require all fields (no defaults).
        # ReimportOptions/ImportOptions have Optional fields — a partially populated
        # instance may contain None values. Merge non-None values onto the known
        # defaults so EditReimportOptions/EditImportOptions can always be constructed.
        _REIMPORT_DEFAULTS = {  # noqa: N806 # Baseline
            "update_name": True,
            "update_description": True,
            "update_column_descriptions": True,
            "delete_when_deleted_at_source": True,
            "delete_when_removed_from_scope": False,
        }
        _IMPORT_DEFAULTS = {  # noqa: N806 # Baseline
            "exclude_tables": False,
            "exclude_views": False,
            "import_incremental_changes_only": False,
            "include_foreign_key": False,
            "include_primary_key": False,
            "include_asset_lifecycle_timestamps": False,
            "metadata_from_catalog_table_only": False,
        }

        edit_reimport: Optional[EditReimportOptions] = None  # noqa: UP045 # Baseline
        if reimport_options is not None:
            merged = {
                **_REIMPORT_DEFAULTS,
                **reimport_options.model_dump(exclude_none=True),
            }
            edit_reimport = EditReimportOptions(**merged)

        edit_import: Optional[EditImportOptions] = None  # noqa: UP045 # Baseline
        if import_options is not None:
            merged = {
                **_IMPORT_DEFAULTS,
                **import_options.model_dump(exclude_none=True),
            }
            edit_import = EditImportOptions(**merged)

        return await _update_mdi(
            project_name=project_name,
            metadata_import_name=metadata_import_name,
            description=description,
            scope=scope,
            tags=tags,
            import_type=import_type if import_type != "metadata" else None,
            reimport_options=edit_reimport,
            import_options=edit_import,
        )

    # CREATE mode
    if not is_openlineage and not connection_name:
        raise ValueError("connection_name is required when creating a new metadata import.")
    if not is_openlineage and import_type in ("metadata", "lineage_and_discovery") and not scope:
        raise ValueError("scope is required for 'metadata' and 'lineage_and_discovery' import types.")

    return await _create_mdi(CreateMetadataImportRequest(
        project_name=project_name,
        connection_name=connection_name,
        is_openlineage=is_openlineage,
        catalog_name=catalog_name,
        scope=scope,
        scope_lineage_include_list=scope_lineage_include_list,
        scope_lineage_exclude_list=scope_lineage_exclude_list,
        import_type=ImportType(import_type),
        file_list=file_list,
        name=name,
        imported_asset_types=imported_asset_types,
        scan_phases=scan_phases,
        tags=tags,
        migrate_tags=migrate_tags,
        reimport_options=reimport_options,
        import_options=import_options,
    ))
