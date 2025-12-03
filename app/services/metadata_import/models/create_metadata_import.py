# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Any, List, Literal, Optional, Union


class CreateMetadataImportRequest(BaseModel):
    project_name: str = Field(..., description="Name of the project where the metadata import will be created.")
    connection_name: str = Field(..., description="Name of the connection to use for the metadata import.")
    scope: Union[List[str], str] = Field(
        ...,
        description="List of schema/table paths to import. Use ['/'] to import all schemas. Provide as a flat list of strings, e.g., ['schema1', 'schema2'] or ['/'].",
        examples=[
            ["/"],
            ["schema1", "schema2"],
            ["/demo/bank", "/demo/bank/employee"]
        ]
    )
    name: Optional[str] = Field(None, description="Optional custom name for the metadata import. If not provided, a name will be auto-generated.")

class CreateMetadataImportResponse(BaseModel):
    message: str = Field(..., description="An example output message from create_metadata_import.")
    
    # Data source definition schema
class DatasourceDefinitionInfo(BaseModel):
    dataSourceAssetId: str
    technology: str
    scanner: str


class ConnectionTypeForExtractionInfo(str, Enum):
    DIRECT = "direct"
    AGENT = "agent"


class MetadataExtractionInfo(BaseModel):
    """
    The configuration of lineage extraction."""
    connection_type: ConnectionTypeForExtractionInfo = Field(..., description="")
    external_agent: str = Field("", description="The agent group ID for the agent group for which the extraction of the asset must be assigned to (only applicable if `MetadataExtractionInfo.connection_type == 'agent').")


class ImportType(str, Enum):
    """The type of metadata import."""
    METADATA = "metadata"
    

class MetadataImportScope(BaseModel):
    paths: List[str] = Field(..., description=(
        "List of schema/table paths to import. "
        "Each path must be a string representing a database schema or table. "
        "Use '/' to import all schemas. "
        "At least one path must be provided."
    ), examples=["/", "/demo/bank", "/demo/bank/employee"])
    @field_validator("paths")
    def validate_paths(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one path must be provided in scope.paths")
        return v

class MetadataImportScopeForTermGen(BaseModel):
    assets: List[str]

class MetadataEnrichmentInfo(BaseModel):
    added_date: str
    areaId: str

class MetadataFileConfigurationReplacements(BaseModel):
    replacement_scope: str
    replacement_value: str
    placeholder_value: str

class MetadataFileConfiguration(BaseModel):
    encoding: str
    enable_replacement: str
    placeholders_are_expressions: str
    replacements: List[MetadataFileConfigurationReplacements]

class MetadataImportRequest(BaseModel):
    unified_lineage: bool = True
    
    import_type : ImportType = Field(..., 
                                     description="The type of metadata import to be performed.",
                                     examples=["metadata"])
  
    description: str = Field(..., description="The description of the metadata import asset to be created.")
    
    name: str = Field(..., description="The name of the metadata import asset to be created.")
    
    connection_id: str = Field(..., description="The ID of the datasource connection from which asset metadata will be imported.")
    @field_validator("target_project_id")
    def validate_connection_id(cls, v):
        if v == "":
            raise ValueError("connection_id cannot be an empty string or null.")
        return v
    
    target_catalog_id: Optional[str] = Field(None, description=(
        "Catalog ID where the imported metadata will be stored."
        "If not provided, metadata is stored in the project by default."
        "Provide the catalog ID to store assets in a catalog instead of the project."
        "Must be null or a non-empty string (empty string is not allowed)."
    ))
    
    @field_validator("target_catalog_id")
    def validate_catalog_id(cls, v):
        if v == "":
            raise ValueError("target_catalog_id cannot be an empty string. Use null instead.")
        return v
    
    target_project_id: str = Field(..., description="The ID of the project where the metadata import asset will be created. This project must be in the same location as the connection.")
    
    @field_validator("target_project_id")
    def validate_project_id(cls, v):
        if v == "":
            raise ValueError("target_project_id cannot be an empty string or null. Use project_id instead")
        return v
    
    tags: List[str] = Field(default_factory=list, description="A list of tags to be associated with the metadata import asset.")
    
    migrate_tags: bool = Field(False, description="A check to disable or enable migrating MDI tags to data asset. If set to true, tags from the metadata import asset will be migrated to the corresponding data asset. If set to false, tags will not be migrated.")

    reimport_options: dict[str, bool] = Field(default_factory=lambda: {
        "update_name": True,
        "update_description": True,
        "update_column_descriptions": True,
        "delete_when_deleted_at_source": True,
        "delete_when_removed_from_scope": False
    }, description="Options that control how re-import of an existing metadata import asset is handled. Specify if name, description, column descriptions to be udpated during re-import. This input is needed only when import_type is 'metadata' or 'termgeneration_and_metadata'.")
    scope: MetadataImportScope = Field(..., description=
                                       "Defines which schemas/tables to import."
                                       "List of schema or table paths to import. Use '/' to import all assets in the connection."
                                       "Schemas and tables may be large in number, when fetching available options, use pagination and allow the user to filter or search to narrow the scope."
                                       "Always confirm the final list of paths with the user before proceeding.")
    
    import_options: dict[str, bool] = Field(default_factory=lambda: {
        "exclude_tables": False,
        "exclude_views": True,
        "import_incremental_changes_only": True,
        "include_foreign_key": True,
        "include_primary_key": True,
        "include_asset_lifecycle_timestamps": True,
        "metadata_from_catalog_table_only": True
    }, description="Advanced options that control how the asset metadata import is performed. This input is needed only if import_type is 'metadata'.")


class AssetMetadataImportRequest(MetadataImportRequest):
    """This class is used when import_type is 'metadata' or 'termgeneration_and_metadata'."""
    import_type : Literal["metadata"] = Field(..., description="The type of metadata import to be performed. Supported values are 'metadata', 'lineage', 'lineage_and_discovery', 'termgeneration', and 'termgeneration_and_metadata'.")
   
    reimport_options: dict[str, bool] = Field(default_factory=lambda: {
        "update_name": True,
        "update_description": True,
        "update_column_descriptions": True,
        "delete_when_deleted_at_source": True,
        "delete_when_removed_from_scope": False
    }, description="Options that control how re-import of an existing metadata import asset is handled. Specify if name, description, column descriptions to be udpated during re-import. This input is needed only when import_type is 'metadata' or 'termgeneration_and_metadata'.",
                                              examples=dict(update_name=True, update_description=True, update_column_descriptions=False, delete_when_deleted_at_source=True, delete_when_removed_from_scope=False))
    scope: MetadataImportScope = Field(..., description="The scope that defines what asset metadata needs to be imported. This input is needed only if import_type is 'metadata'.")
    import_options: dict[str, bool] = Field(default_factory=lambda: {
        "exclude_tables": False,
        "exclude_views": True,
        "import_incremental_changes_only": True,
        "include_foreign_key": True,
        "include_primary_key": True,
        "include_asset_lifecycle_timestamps": True,
        "metadata_from_catalog_table_only": True
    }, description="Advanced options that control how the asset metadata import is performed. This input is needed only if import_type is 'metadata'.",
                                            examples=dict(exclude_tables=False, exclude_views=False, import_incremental_changes_only=False, include_foreign_key=False, include_primary_key=False))


class LineageMetadataImportRequest(MetadataImportRequest):
    import_type: ImportType = Literal["lineage"]
    datasource_definition_info: DatasourceDefinitionInfo = Field(..., description="A data source definition is a set of endpoints that identify a data source instance. A data source definition provides a list of connections from which a connection can be selected for metadata import. This field is required for `import_type=lineage and `import_type=lineage_and_discovery`.")
    lineage_scanning_phases: List[str] = Field(default_factory=lambda: ["extraction_of_transformations", "processing_of_extracted_inputs", "processing_of_external_inputs", "processing_of_all_inputs", "dictionary_processing"],
        description="This field is internal and always defaults to ['extraction_of_transformations', 'processing_of_extracted_inputs', 'processing_of_external_inputs', 'processing_of_all_inputs', 'dictionary_processing']. Do not supply a value.")
    advanced_lineage_option: dict[str, Any] = Field(default_factory=lambda:{
        "enable_extended_attributes": True,
        "input_reader": "scenarioReader",
        "enable_transformation_logic": True
    }, description="Advanced options that control how the lineage metadata import is performed. This input is needed only if import_type is 'lineage' or 'lineage_and_discovery'."),
    scope_lineage: MetadataImportScope = Field(..., description="The scope that defines what lineage metadata needs to be imported. This input is needed only if import_type is 'lineage' or 'lineage_and_discovery'.")

class LineageAndDiscoveryMetadataImportRequest(AssetMetadataImportRequest, LineageMetadataImportRequest):
    import_type: ImportType = Literal["lineage_and_discovery"]
    scope: MetadataImportScope
    scope_lineage: MetadataImportScope

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
    connection_id: str
    target_project_id: str
    job_id: str
    scope: MetadataImportScope
    datasource_type: str
    number_of_runs: int
    mde_enabled: bool
    migrate_tags: bool
    reimport_options: dict[str, bool]
    import_options: Optional[dict[str, bool]]
    
class MetadataImport(BaseModel):
    metadata: MetadataImportMetadata
    entity: MetadataImportEntity

class MetadataImportDTO(BaseModel):
    metadata_import: MetadataImport
    url: str