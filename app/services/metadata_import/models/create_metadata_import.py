# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field  # noqa: I001 # Baseline
from app.shared.models import BaseResponseModel, field_validator, model_validator
from enum import Enum
from typing import Any, List, Optional  # noqa: UP035 # Baseline


class ReimportOptions(BaseModel):
    """Optional overrides for re-import behaviour. Only supply the keys you want to change;
    unspecified fields retain their default values."""

    update_name: Optional[bool] = Field(  # noqa: UP045 # Baseline
        True,
        description="Whether to update the asset name during re-import. Defaults to True.",
    )
    update_description: Optional[bool] = Field(  # noqa: UP045 # Baseline
        True,
        description="Whether to update the asset description during re-import. Defaults to True.",
    )
    update_column_descriptions: Optional[bool] = Field(  # noqa: UP045 # Baseline
        True,
        description="Whether to update column descriptions during re-import. Defaults to True.",
    )
    delete_when_deleted_at_source: Optional[bool] = Field(  # noqa: UP045 # Baseline
        True,
        description="Whether to delete the asset when it is deleted at the source. Defaults to True.",
    )
    delete_when_removed_from_scope: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to delete the asset when it is removed from the import scope. Defaults to False.",
    )


class ImportOptions(BaseModel):
    """Optional overrides for import options. Only supply the keys you want to change;
    unspecified fields retain their default values."""

    exclude_tables: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to exclude tables from the import. Defaults to False.",
    )
    exclude_views: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to exclude views from the import. Defaults to False.",
    )
    import_incremental_changes_only: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to import only incremental changes since the last import. Defaults to False.",
    )
    include_foreign_key: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to include foreign key relationships in the import. Defaults to False.",
    )
    include_primary_key: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to include primary key information in the import. Defaults to False.",
    )
    include_asset_lifecycle_timestamps: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to include asset lifecycle timestamps in the import. Defaults to False.",
    )
    metadata_from_catalog_table_only: Optional[bool] = Field(  # noqa: UP045 # Baseline
        False,
        description="Whether to import metadata from catalog tables only. Defaults to False.",
    )


class CreateMetadataImportResponse(BaseResponseModel):
    message: str = Field(
        ..., description="An example output message from create_metadata_import."
    )
    metadata_import_asset_ui_url: str = Field(
        ..., description="The URL to view the created metadata import asset in the UI."
    )
    metadata_import_name: str = Field(
        ..., description="The name of the created metadata import asset."
    )
# Data source definition schema
class DatasourceDefinitionInfo(BaseModel):
    data_source_asset_id: Optional[str] = None  # noqa: UP045 # Baseline
    technology: str
    scanner: str


class ConnectionTypeForExtractionInfo(str, Enum):  # noqa: UP042 # Baseline
    DIRECT = "direct"
    AGENT = "agent"


class MetadataExtractionInfo(BaseModel):
    """
    The configuration of lineage extraction."""

    connection_type: ConnectionTypeForExtractionInfo = Field(..., description="")
    external_agent: str = Field(
        "",
        description="The agent group ID for the agent group for which the extraction of the asset must be assigned to (only applicable if `MetadataExtractionInfo.connection_type == 'agent').",
    )


class ImportType(str, Enum):  # noqa: UP042 # Baseline
    """The type of metadata import."""

    METADATA = "metadata"
    LINEAGE = "lineage"
    LINEAGE_AND_DISCOVERY = "lineage_and_discovery"


class MetadataImportScope(BaseModel):
    """Scope with paths only - for standard path-based import."""

    paths: List[str] = Field(  # noqa: UP006 # Baseline
        ...,
        description=(
            "List of schema/table paths to import. "
            "Each path must be a string representing a database schema or table. "
            "Use '/' to import all schemas. "
            "At least one path must be provided."
        ),
        examples=["/", "/demo/bank", "/demo/bank/employee"],
    )

    @field_validator("paths")
    def validate_paths(cls, v):  # noqa: ANN001, ANN201, N805 # Baseline
        if not v or len(v) == 0:
            raise ValueError("At least one path must be provided in scope.paths")
        return v


class MetadataImportScopeWithIncludeExclude(BaseModel):
    """Scope with include_list and optional exclude_list - for pattern-based filtering."""

    include_list: List[str] = Field(  # noqa: UP006 # Baseline
        ..., description="List of patterns to include in the import scope."
    )
    exclude_list: Optional[List[str]] = Field(  # noqa: UP006, UP045 # Baseline
        None, description="List of patterns to exclude from the import scope."
    )

    @field_validator("include_list")
    def validate_include_list(cls, v):  # noqa: ANN001, ANN201, N805 # Baseline
        if not v or len(v) == 0:
            raise ValueError("At least one pattern must be provided in include_list")
        return v


class MetadataImportScopeForTermGen(BaseModel):
    assets: List[str]  # noqa: UP006 # Baseline



class FileListItem(BaseModel):
    """Model for individual file list items containing asset ID and technology information."""

    asset_id: str = Field(
        ...,
        description="UUID of the asset"
    )
    technology: str = Field(
        ...,
        description="Technology name (e.g., 'Statistical Analysis System (SAS)')"
    )


class CreateMetadataImportRequest(BaseModel):
    """
    Unified request model for creating metadata imports.
    Supports three import types:
    - 'metadata': Discovery only (requires scope)
    - 'lineage': Lineage only (requires scope_lineage)
    - 'lineage_and_discovery': Both discovery and lineage (requires scope, scope_lineage, and dsd_name)
    """
    project_name: str = Field(..., description="Name of the project where the metadata import will be created.")
    connection_name: str | None = Field(None, description="Name of the connection to use for the metadata import. Not required when is_openlineage is True.")
    is_openlineage: bool = Field(False, description="Set to True when the import is for an OpenLineage technology. When True, connection_name is not required and no DSD mapping is needed.")
    import_type: ImportType = Field(
        default=ImportType.METADATA,
        description=(
            "Type of import to perform:\n"
            "- 'metadata': Discovery only (imports metadata/schema information)\n"
            "- 'lineage': Lineage only (imports data lineage information)\n"
            "- 'lineage_and_discovery': Both discovery and lineage"
        )
    )
    name: str | None = Field(None, description="Optional custom name for the metadata import. If not provided, a name will be auto-generated.")
    catalog_name: str | None = Field(
        default=None,
        description=(
            "Catalog name where discovered metadata will be stored. "
            "Required for technologies that use lineage for discovery when import_type includes discovery."
        )
    )

    scope: list[str] | str | None = Field(
        default=None,
        description=(
            "List of schema/table paths for metadata discovery. "
            "Required when import_type is 'metadata' or 'lineage_and_discovery'. "
            "Use ['/'] to import all schemas. Provide as a flat list of strings, e.g., ['schema1', 'schema2'] or ['/']."
        ),
        examples=[
            ["/"],
            ["schema1", "schema2"],
            ["/demo/bank", "/demo/bank/employee"]
        ]
    )

    scope_lineage_include_list: list[str] | None = Field(
        default=None,
        description=(
            "Optional include-list patterns for lineage scope. "
            "Required when import_type is 'lineage' or 'lineage_and_discovery'. "
            "Use ['/'] for the entire datasource, or specific paths/patterns such as ['schema1', 'schema2']."
        ),
        examples=[["/"], ["schema1", "schema2"], ["db.schema.*"]]
    )

    scope_lineage_exclude_list: list[str] | None = Field(
        default=None,
        description=(
            "Optional exclude-list patterns for lineage scope. "
            "When provided, assets matching these patterns are excluded from the lineage import."
        ),
        examples=[["db.schema.tmp.*"]]
    )

    file_list: list[str] | None = Field(
        default=None,
        description="Optional list of file asset names. Used for lineage imports."
    )

    scan_phases: list[str] | None = Field(
        default=None,
        description="Optional list of scan phases. Used for lineage imports."
    )

    imported_asset_types: list[str] | None = Field(
        None,
        description="Optional list of asset types that should be imported as part of lineage discovery."
    )

    tags: list[str] | None = Field(
        None,
        description="Optional list of tags to associate with the metadata import asset. If not provided, no tags are added."
    )
    migrate_tags: bool | None = Field(
        False,
        description="Whether to migrate tags from the metadata import asset to the imported data assets. Defaults to False."
    )
    reimport_options: ReimportOptions | None = Field(
        None,
        description="Optional overrides for re-import behaviour. Only supply the keys you want to change; all other keys retain their defaults."
    )
    import_options: ImportOptions | None = Field(
        None,
        description="Optional overrides for import options. Only supply the keys you want to change; all other keys retain their defaults."
    )

    @model_validator(mode='after')
    def validate_openlineage_connection(self) -> "CreateMetadataImportRequest":
        """Validate that connection_name is provided when is_openlineage is False."""
        if not self.is_openlineage and not self.connection_name:
            raise ValueError("'connection_name' is required when is_openlineage is False")
        return self

    @model_validator(mode='after')
    def validate_import_type_requirements(self) -> "CreateMetadataImportRequest":
        """Validate that required fields are present based on import_type."""
        # OpenLineage uses only manual inputs — scope is not applicable.
        if self.import_type == ImportType.METADATA:
            if not self.scope and not self.is_openlineage:
                raise ValueError("'scope' is required when import_type is 'metadata'")
        elif self.import_type == ImportType.LINEAGE:
            if not self.scope_lineage_include_list and not self.is_openlineage:
                raise ValueError("'scope_lineage_include_list' is required when import_type is 'lineage'")
        elif self.import_type == ImportType.LINEAGE_AND_DISCOVERY:
            if not self.scope and not self.is_openlineage:
                raise ValueError("'scope' is required when import_type is 'lineage_and_discovery'")
            if not self.scope_lineage_include_list and not self.is_openlineage:
                raise ValueError("'scope_lineage_include_list' is required when import_type is 'lineage_and_discovery'")
        return self


class MetadataEnrichmentInfo(BaseModel):
    added_date: str
    areaId: str  # noqa: N815 # Baseline


class MetadataFileConfigurationReplacements(BaseModel):
    replacement_scope: str
    replacement_value: str
    placeholder_value: str


class MetadataFileConfiguration(BaseModel):
    encoding: str
    enable_replacement: str
    placeholders_are_expressions: str
    replacements: List[MetadataFileConfigurationReplacements]  # noqa: UP006 # Baseline


class MetadataImportRequest(BaseModel):
    unified_lineage: bool = True
    use_lineage_for_discovery: bool = Field(
        False,
        description="Flag to determine whether MDI or Lineage should be used for discovery",
    )
    import_type: ImportType = Field(  # noqa: UP042 # Baseline
        ...,
        description="The type of metadata import to be performed.",
        examples=["metadata", "lineage", "lineage_and_discovery"],
    )

    description: str = Field(
        ..., description="The description of the metadata import asset to be created."
    )

    name: str = Field(
        ..., description="The name of the metadata import asset to be created."
    )

    connection_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description="The ID of the datasource connection from which asset metadata will be imported. Not required for OpenLineage imports.",
    )

    @field_validator("connection_id")
    def validate_connection_id(cls, v):  # noqa: ANN001, ANN201, N805 # Baseline
        if v == "":
            raise ValueError(
                "connection_id cannot be an empty string. Use null instead."
            )
        return v

    target_catalog_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description=(
            "Catalog ID where the imported metadata will be stored."
            "If not provided, metadata is stored in the project by default."
            "Provide the catalog ID to store assets in a catalog instead of the project."
            "Must be null or a non-empty string (empty string is not allowed)."
        ),
    )

    @field_validator("target_catalog_id")
    def validate_catalog_id(cls, v):  # noqa: ANN001, ANN201, N805 # Baseline
        if v == "":
            raise ValueError(
                "target_catalog_id cannot be an empty string. Use null instead."
            )
        return v

    @model_validator(mode="after")
    def validate_discovery_catalog_requirements(self):  # noqa: ANN201 # Baseline
        if (
            self.use_lineage_for_discovery
            and self.import_type in {
                ImportType.METADATA,
                ImportType.LINEAGE_AND_DISCOVERY,
            }
            and not self.target_catalog_id
        ):
            raise ValueError(
                "'target_catalog_id' is required when discovery uses lineage"
            )
        return self

    target_project_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        None,
        description=(
            "The ID of the project where the metadata import asset will be created. "
            "This project must be in the same location as the connection. "
        ),
    )

    @field_validator("target_project_id")
    def validate_project_id(cls, v):  # noqa: ANN001, ANN201, N805 # Baseline
        if v == "":
            raise ValueError(
                "target_project_id cannot be an empty string. Use null instead"
            )
        return v

    @model_validator(mode="after")
    def validate_target(self):  # noqa: ANN201 # Baseline
        if self.target_project_id and self.target_catalog_id:
            raise ValueError(
                "target_project_id and target_catalog_id are mutually exclusive. Provide exactly one."
            )
        if not self.target_project_id and not self.target_catalog_id:
            raise ValueError(
                "Exactly one of target_project_id or target_catalog_id must be provided."
            )
        return self

    datasource_definition_info: Optional[DatasourceDefinitionInfo] = Field(  # noqa: UP045 # Baseline
        None,
        description="A data source definition is a set of endpoints that identify a data source instance. A data source definition provides a list of connections from which a connection can be selected for metadata import. This field is required for `import_type=lineage and `import_type=lineage_and_discovery`.",
    )

    tags: List[str] = Field(  # noqa: UP006 # Baseline
        default_factory=list,
        description="A list of tags to be associated with the metadata import asset.",
    )

    migrate_tags: bool = Field(
        False,
        description="A check to disable or enable migrating MDI tags to data asset. If set to true, tags from the metadata import asset will be migrated to the corresponding data asset. If set to false, tags will not be migrated.",
    )

    reimport_options: dict[str, bool] = Field(
        default_factory=lambda: {
            "update_name": True,
            "update_description": True,
            "update_column_descriptions": True,
            "delete_when_deleted_at_source": True,
            "delete_when_removed_from_scope": False,
        },
        description="Options that control how re-import of an existing metadata import asset is handled. Specify if name, description, column descriptions to be udpated during re-import. This input is needed only when import_type is 'metadata' or 'termgeneration_and_metadata'.",
    )
    scope: MetadataImportScope = Field(
        ...,
        description=(
            "Defines which schemas/tables to import."
            "List of schema or table paths to import. Use '/' to import all assets in the connection."
            "Schemas and tables may be large in number, when fetching available options, use pagination and allow the user to filter or search to narrow the scope."
            "Always confirm the final list of paths with the user before proceeding."
        ),
    )

    import_options: dict[str, Any] = Field(
        default_factory=lambda: {
            "exclude_tables": False,
            "exclude_views": False,
            "import_incremental_changes_only": False,
            "include_foreign_key": False,
            "include_primary_key": False,
            "include_asset_lifecycle_timestamps": False,
            "metadata_from_catalog_table_only": False,
        },
        description="Advanced options that control how the asset metadata import is performed. This input is needed only if import_type is 'metadata'.",
    )


class AssetMetadataImportRequest(MetadataImportRequest):
    """This class is used when import_type is 'metadata' or 'termgeneration_and_metadata'."""

    import_type: ImportType = Field(
        ImportType.METADATA,
        description="The type of metadata import to be performed. For this class, should be 'metadata'.",
    )

    reimport_options: dict[str, bool] = Field(
        default_factory=lambda: {
            "update_name": True,
            "update_description": True,
            "update_column_descriptions": True,
            "delete_when_deleted_at_source": True,
            "delete_when_removed_from_scope": False,
        },
        description="Options that control how re-import of an existing metadata import asset is handled. Specify if name, description, column descriptions to be udpated during re-import. This input is needed only when import_type is 'metadata' or 'termgeneration_and_metadata'.",
        examples={
            "update_name": True,
            "update_description": True,
            "update_column_descriptions": False,
            "delete_when_deleted_at_source": True,
            "delete_when_removed_from_scope": False,
        },
    )
    scope: MetadataImportScope = Field(
        ...,
        description="The scope that defines what asset metadata needs to be imported. This input is needed only if import_type is 'metadata'.",
    )
    import_options: dict[str, Any] = Field(
        default_factory=lambda: {
            "exclude_tables": False,
            "exclude_views": False,
            "import_incremental_changes_only": False,
            "include_foreign_key": False,
            "include_primary_key": False,
            "include_asset_lifecycle_timestamps": False,
            "metadata_from_catalog_table_only": False,
        },
        description="Advanced options that control how the asset metadata import is performed. This input is needed only if import_type is 'metadata'.",
        examples={
            "exclude_tables": False,
            "exclude_views": False,
            "import_incremental_changes_only": False,
            "include_foreign_key": False,
            "include_primary_key": False,
        },
    )


class LineageMetadataImportRequest(MetadataImportRequest):
    import_type: ImportType = ImportType.LINEAGE
    datasource_definition_info: DatasourceDefinitionInfo = Field(
        ...,
        description="A data source definition is a set of endpoints that identify a data source instance. A data source definition provides a list of connections from which a connection can be selected for metadata import. This field is required for `import_type=lineage and `import_type=lineage_and_discovery`.",
    )
    lineage_scanning_phases: List[str] = Field(  # noqa: UP006 # Baseline
        default_factory=lambda: [
            "extraction_of_transformations",
            "processing_of_extracted_inputs",
            "processing_of_external_inputs",
            "processing_of_all_inputs",
            "dictionary_processing",
        ],
        description="This field is internal and always defaults to ['extraction_of_transformations', 'processing_of_extracted_inputs', 'processing_of_external_inputs', 'processing_of_all_inputs', 'dictionary_processing']. Do not supply a value.",
    )
    advanced_lineage_option: dict[str, Any] = Field(
        default_factory=lambda: {
            "analysis_timeout": 60,
            "analysis_edge_limit": 2500,
            "performance_profile": "Balanced",
        },
        description="Advanced options that control how the lineage metadata import is performed. This input is needed only if import_type is 'lineage' or 'lineage_and_discovery'.",
        examples={
            "analysis_timeout": 60,
            "analysis_edge_limit": 2500,
            "performance_profile": "Balanced",
        },
    )
    scope: Optional[MetadataImportScope] = Field(  # noqa: UP045 # Baseline
        None,
        description=(
            "Defines which schemas/tables to import."
            "List of schema or table paths to import. Use '/' to import all assets in the connection."
            "Schemas and tables may be large in number, when fetching available options, use pagination and allow the user to filter or search to narrow the scope."
            "Always confirm the final list of paths with the user before proceeding."
        ),
    )

    scope_lineage: MetadataImportScope | MetadataImportScopeWithIncludeExclude = Field(
        ...,
        description=(
            "The scope that defines what lineage metadata needs to be imported. "
            "Can use paths or include_list/exclude_list patterns. "
            "This input is needed only if import_type is 'lineage' or 'lineage_and_discovery'."
        ),
    )
    file_list: Optional[List[FileListItem]] = Field(  # noqa: UP006, UP045 # Baseline
        None, description="Optional list of file assets for lineage import."
    )


class LineageAndDiscoveryMetadataImportRequest(LineageMetadataImportRequest):
    import_type: ImportType = ImportType.LINEAGE_AND_DISCOVERY


class MetadataImportUsage(BaseModel):
    last_updated_at: str
    last_updater_id: str
    last_update_time: int
    last_accessed_at: str
    last_access_time: int
    last_accessor_id: str
    access_count: int


class MetadataImportMetadata(BaseModel):
    asset_id: str
    asset_type: str
    creator_id: str
    created_at: str
    project_id: str
    usage: MetadataImportUsage


class MetadataImportEntity(BaseModel):
    unified_lineage: bool
    description: str
    name: str
    import_type: ImportType
    connection_id: Optional[str] = None  # noqa: UP045 # Baseline
    target_project_id: Optional[str] = None  # noqa: UP045 # Baseline
    target_catalog_id: Optional[str] = None  # noqa: UP045 # Baseline
    job_id: str
    scope: MetadataImportScope | None = None
    scope_lineage: MetadataImportScope | MetadataImportScopeWithIncludeExclude | None = None
    datasource_type: Optional[str] = None  # noqa: UP045 # Baseline
    number_of_runs: int
    mde_enabled: bool
    migrate_tags: bool
    reimport_options: dict[str, bool]
    import_options: Optional[dict[str, Any]] = None  # noqa: UP045 # Baseline


class MetadataImport(BaseModel):
    metadata: MetadataImportMetadata
    entity: MetadataImportEntity


class MetadataImportDTO(BaseModel):
    metadata_import: MetadataImport
    url: str
