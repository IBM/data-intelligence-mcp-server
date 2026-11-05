# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from enum import StrEnum

from pydantic import BaseModel, Field

from app.services.search.models.search_data_source_definition import (
    SearchDataSourceDefinitionResponse,
)
from app.shared.models import BaseResponseModel


class LineageScanningPhases(StrEnum):
    """Enum for lineage scanning phases."""
    DICTIONARY_PROCESSING = "dictionary_processing"
    EXTRACTION_OF_TRANSFORMATIONS = "extraction_of_transformations"
    PROCESSING_OF_EXTRACTED_INPUTS = "processing_of_extracted_inputs"
    INGEST_OF_EXTERNAL_INPUTS = "ingest_of_external_inputs"
    PROCESSING_OF_EXTERNAL_INPUTS = "processing_of_external_inputs"
    PROCESSING_OF_ALL_INPUTS = "processing_of_all_inputs"


class Technology(StrEnum):
    """Enum for supported technologies."""
    SNOWFLAKE = "Snowflake"
    MSSQL = "Microsoft SQL Server"
    MSSQL_AZURE = "Microsoft Azure SQL Database"
    POWER_BI_AZURE = "Microsoft Power BI (Azure)"
    IBM_DATA_STAGE = "IBM InfoSphere DataStage"
    IBM_DATA_STAGE_CPD = "IBM DataStage for Cloud Pak for Data"
    POSTGRESQL = "PostgreSQL"
    POSTGRESQL_AMAZON_RDS = "Amazon RDS for PostgreSQL"
    POSTGRESQL_IBM_CLOUD = "IBM Cloud Databases for PostgreSQL"
    REDSHIFT = "Amazon Redshift"
    TABLEAU = "Tableau"
    GREENPLUM = "Greenplum"
    OPEN_LINEAGE = "OpenLineage"
    DB2_IBM_CLOUD = "IBM Db2 on Cloud"
    DB2_ZOS = "IBM Db2 for z/OS"
    DB2 = "IBM Db2"
    BIG_QUERY = "Google BigQuery"
    ORACLE_AMAZON_RDS = "Amazon RDS for Oracle"
    ORACLE = "Oracle"
    MICRO_STRATEGY = "MicroStrategy"
    AZURE_DATABRICKS = "Microsoft Azure Databricks"
    COGNOS = "IBM Cognos Analytics"
    QLIK_SENSE = "Qlik Sense"
    APACHE_HIVE = "Apache Hive"
    SAP_ASE = "SAP ASE"
    TERADATA = "Teradata"
    SAP_HANA = "SAP HANA"
    SAS = "Statistical Analysis System (SAS)"
    IBM_DATA_VIRTUALIZATION = "IBM Data Virtualization"
    TALEND = "Talend Data"
    INFORMATICA_POWER_CENTER = "Informatica PowerCenter"
    SAP_BO = "SAP BusinessObjects"
    POWER_BI_LOCAL = "Microsoft Power BI Report Server"
    IBM_CLOUD = "IBM Cloud"
    IBM_SOFTWARE_HUB = "IBM Software Hub"
    NETEZZA = "IBM Netezza Performance Server"
    SYNAPSE = "Azure Synapse Analytics"

TECHNOLOGIES_WITH_UNIFIED_LINEAGE_DISCOVERY = {
    Technology.POWER_BI_AZURE.value,
    Technology.IBM_DATA_STAGE.value,
    Technology.IBM_DATA_STAGE_CPD.value,
    Technology.OPEN_LINEAGE.value,
    Technology.MICRO_STRATEGY.value,
    Technology.SAS.value,
    Technology.TALEND.value,
    Technology.QLIK_SENSE.value,
    Technology.INFORMATICA_POWER_CENTER.value,
}

TECHNOLOGIES_WITH_ONLY_MANUAL_INPUTS = {
    Technology.IBM_DATA_STAGE.value,
    Technology.SAS.value,
    Technology.TALEND.value,
    Technology.OPEN_LINEAGE.value,
}

class ScannersWithOverrides(StrEnum):
    """Enum for scanners with special override behavior."""
    SSIS = "Microsoft SQL Server Integration Services"
    SSAS = "Microsoft SQL Server Analytical Services"


class AssetImportExpansion(StrEnum):
    """Enum for asset import expansion types."""
    DATA = "data_asset"
    TRANSFORMATION_SCRIPT = "data_transformation"
    BUSINESS_INTELLIGENCE_REPORT = "ibm_bi_report"
    BUSINESS_INTELLIGENCE_REPORT_QUERY = "ibm_bi_report_query"
    BUSINESS_INTELLIGENCE_REPORT_QUERY_ITEM = "ibm_bi_report_query_item"
    DATA_INTEGRATION_JOB = "data_integration_job"
    DATA_INTEGRATION_COMPONENT = "data_integration_component"
    DATA_INTEGRATION_COLUMN = "data_integration_column"
    LOGICAL_MODEL = "ibm_logical_model"
    LOGICAL_MODEL_ENTITY = "ibm_logical_model_entity"
    LOGICAL_MODEL_ATTRIBUTE = "ibm_logical_model_attribute"
    LOGICAL_MODEL_RELATIONSHIP = "ibm_logical_model_relationship"
    PHYSICAL_MODEL = "ibm_physical_model"
    PHYSICAL_MODEL_SCHEMA = "ibm_physical_model_schema"
    PHYSICAL_MODEL_TABLE = "ibm_physical_model_table"
    PHYSICAL_MODEL_VIEW = "ibm_physical_model_view"
    PHYSICAL_MODEL_COLUMN = "ibm_physical_model_column"
    PHYSICAL_MODEL_CONSTRAINT = "ibm_physical_model_constraint"


class ImportedAssetTypes(BaseModel):
    default: list[str] | None = Field(None, description="Default imported asset types")
    optional: list[str] | None = Field(None, description="Optional imported asset types")

class GetConnectionTechnologyDetailsRequest(BaseModel):
    connection_name: str = Field(..., description="Name of the connection")
    project_name: str = Field(..., description="Name of the project where the connection is located")

class GetConnectionTechnologyDetailsResponse(BaseResponseModel):
    project_id: str = Field(..., description="ID of the project where the metadata import will be created.")
    connection_id: str | None = Field(None, description="ID of the connection to use for the metadata import. None for OpenLineage imports.")
    dsd: SearchDataSourceDefinitionResponse | None = Field(None, description="Definition of the DSD the connection is mapped to.")
    uses_unified_lineage_discovery: bool = Field(..., description="Whether the connection uses unified lineage for discovery")
    uses_only_manual_inputs: bool = Field(..., description="Whether the connection uses only manual inputs")
    technology: str = Field(..., description="Technology name")
    imported_asset_types: ImportedAssetTypes = Field(..., description="Information about options for imported asset type")
    scan_phases: list[str] = Field(..., description="Scan phases supported for this technology")
