# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated

from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import CONNECTIONS_BASE_ENDPOINT
from app.services.metadata_import.models.get_connection_technology_details import (
    TECHNOLOGIES_WITH_ONLY_MANUAL_INPUTS,
    TECHNOLOGIES_WITH_UNIFIED_LINEAGE_DISCOVERY,
    AssetImportExpansion,
    GetConnectionTechnologyDetailsRequest,
    GetConnectionTechnologyDetailsResponse,
    ImportedAssetTypes,
    LineageScanningPhases,
    ScannersWithOverrides,
    Technology,
)
from app.services.search.models.search_data_source_definition import (
    SearchDataSourceDefinitionRequest,
    SearchDataSourceDefinitionResponse,
)
from app.services.search.tools.search_data_source_definition import (
    _search_data_source_definition,
)
from app.services.tool_utils import (
    find_connection_id,
    find_project_id,
    get_datasource_type_name,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service


def get_phases_for_technology(technology: str | None, scanner: str | None = None) -> list[str]:  # noqa: PLR0911 # Baseline
    """
    Get the lineage scanning phases for a given technology and scanner.

    Args:
        technology: The technology name
        scanner: Optional scanner name that may override technology behavior

    Returns:
        List of lineage scanning phase values
    """
    extraction_and_processing_technologies = [
        Technology.MSSQL.value,
        Technology.MSSQL_AZURE.value,
        Technology.SNOWFLAKE.value,
        Technology.POSTGRESQL.value,
        Technology.POSTGRESQL_AMAZON_RDS.value,
        Technology.POSTGRESQL_IBM_CLOUD.value,
        Technology.REDSHIFT.value,
        Technology.GREENPLUM.value,
        Technology.DB2_IBM_CLOUD.value,
        Technology.DB2_ZOS.value,
        Technology.DB2.value,
        Technology.BIG_QUERY.value,
        Technology.ORACLE_AMAZON_RDS.value,
        Technology.ORACLE.value,
        Technology.AZURE_DATABRICKS.value,
        Technology.APACHE_HIVE.value,
        Technology.SAP_ASE.value,
        Technology.TERADATA.value,
        Technology.SAP_HANA.value,
        Technology.NETEZZA.value,
        Technology.SYNAPSE.value,
    ]

    extraction_and_processing_of_all_inputs_technologies = [
        Technology.POWER_BI_AZURE.value,
        Technology.IBM_DATA_STAGE_CPD.value,
        Technology.TABLEAU.value,
        Technology.MICRO_STRATEGY.value,
        Technology.COGNOS.value,
        Technology.QLIK_SENSE.value,
        Technology.INFORMATICA_POWER_CENTER.value,
        Technology.SAP_BO.value,
        Technology.POWER_BI_LOCAL.value,
    ]

    processing_of_external_inputs_and_dictionary_technologies = [
        Technology.SAS.value
    ]

    processing_of_all_inputs_only_technologies = [
        Technology.IBM_DATA_STAGE.value,
        Technology.OPEN_LINEAGE.value,
        Technology.TALEND.value,
    ]

    extraction_and_processing_of_extracted_inputs_and_dictionary_technologies = [
        Technology.IBM_DATA_VIRTUALIZATION.value,
    ]

    if not technology:
        return []

    if scanner == ScannersWithOverrides.SSAS.value:
        return [
            LineageScanningPhases.DICTIONARY_PROCESSING.value,
            LineageScanningPhases.PROCESSING_OF_ALL_INPUTS.value,
        ]

    if scanner == ScannersWithOverrides.SSIS.value:
        return [
            LineageScanningPhases.EXTRACTION_OF_TRANSFORMATIONS.value,
            LineageScanningPhases.PROCESSING_OF_ALL_INPUTS.value,
        ]

    if technology in extraction_and_processing_technologies:
        return [
            LineageScanningPhases.DICTIONARY_PROCESSING.value,
            LineageScanningPhases.EXTRACTION_OF_TRANSFORMATIONS.value,
            LineageScanningPhases.PROCESSING_OF_EXTRACTED_INPUTS.value,
            LineageScanningPhases.PROCESSING_OF_EXTERNAL_INPUTS.value,
        ]

    if technology in extraction_and_processing_of_all_inputs_technologies:
        return [
            LineageScanningPhases.EXTRACTION_OF_TRANSFORMATIONS.value,
            LineageScanningPhases.PROCESSING_OF_ALL_INPUTS.value,
        ]

    if technology in processing_of_all_inputs_only_technologies:
        return [LineageScanningPhases.PROCESSING_OF_ALL_INPUTS.value]

    if technology in processing_of_external_inputs_and_dictionary_technologies:
        return [
            LineageScanningPhases.DICTIONARY_PROCESSING.value,
            LineageScanningPhases.PROCESSING_OF_EXTERNAL_INPUTS.value,
        ]

    if technology in extraction_and_processing_of_extracted_inputs_and_dictionary_technologies:
        return [
            LineageScanningPhases.DICTIONARY_PROCESSING.value,
            LineageScanningPhases.EXTRACTION_OF_TRANSFORMATIONS.value,
            LineageScanningPhases.PROCESSING_OF_EXTRACTED_INPUTS.value,
        ]

    return []


def get_asset_expansion_set(technology: str | None, scanner: str | None = None) -> ImportedAssetTypes:  # noqa: PLR0911 # Baseline
    """
    Get the asset expansion set for a given technology and scanner.

    Args:
        technology: The technology name
        scanner: Optional scanner name that may override technology behavior

    Returns:
        ImportedAssetTypes with default and optional asset types
    """
    # Check scanner overrides first
    if scanner == ScannersWithOverrides.SSIS.value:
        return ImportedAssetTypes(
            default=[AssetImportExpansion.DATA_INTEGRATION_JOB.value],
            optional=[
                AssetImportExpansion.DATA_INTEGRATION_COMPONENT.value,
                AssetImportExpansion.DATA_INTEGRATION_COLUMN.value,
            ],
        )

    if scanner == ScannersWithOverrides.SSAS.value:
        return ImportedAssetTypes(
            default=[AssetImportExpansion.BUSINESS_INTELLIGENCE_REPORT.value],
            optional=[
                AssetImportExpansion.BUSINESS_INTELLIGENCE_REPORT_QUERY.value,
                AssetImportExpansion.BUSINESS_INTELLIGENCE_REPORT_QUERY_ITEM.value,
            ],
        )

    # Check technology-specific configurations
    if technology == Technology.OPEN_LINEAGE.value:
        return ImportedAssetTypes(
            default=[
                AssetImportExpansion.DATA.value,
                AssetImportExpansion.TRANSFORMATION_SCRIPT.value,
                AssetImportExpansion.BUSINESS_INTELLIGENCE_REPORT.value,
                AssetImportExpansion.DATA_INTEGRATION_JOB.value,
            ],
            optional=[],
        )

    if technology == Technology.SAS.value:
        return ImportedAssetTypes(
            default=[],
            optional=[
                AssetImportExpansion.DATA.value,
                AssetImportExpansion.TRANSFORMATION_SCRIPT.value,
            ],
        )

    if technology in [
        Technology.MICRO_STRATEGY.value,
        Technology.POWER_BI_AZURE.value,
        Technology.QLIK_SENSE.value,
        Technology.TABLEAU.value,
    ]:
        return ImportedAssetTypes(
            default=[AssetImportExpansion.BUSINESS_INTELLIGENCE_REPORT.value],
            optional=[
                AssetImportExpansion.BUSINESS_INTELLIGENCE_REPORT_QUERY.value,
                AssetImportExpansion.BUSINESS_INTELLIGENCE_REPORT_QUERY_ITEM.value,
            ],
        )

    if technology in [
        Technology.IBM_DATA_STAGE_CPD.value,
        Technology.IBM_DATA_STAGE.value,
        Technology.INFORMATICA_POWER_CENTER.value,
        Technology.TALEND.value,
    ]:
        return ImportedAssetTypes(
            default=[AssetImportExpansion.DATA_INTEGRATION_JOB.value],
            optional=[
                AssetImportExpansion.DATA_INTEGRATION_COMPONENT.value,
                AssetImportExpansion.DATA_INTEGRATION_COLUMN.value,
            ],
        )

    # Default: no expansion
    return ImportedAssetTypes(default=[], optional=[])


def uses_unified_lineage_discovery(scanner: str) -> bool:
    """Return True when the scanner technology uses lineage for discovery."""
    return scanner in TECHNOLOGIES_WITH_UNIFIED_LINEAGE_DISCOVERY


def uses_only_manual_inputs(scanner: str) -> bool:
    """Return True when the scanner technology uses only manual inputs."""
    return scanner in TECHNOLOGIES_WITH_ONLY_MANUAL_INPUTS


async def get_dsd_info(dsd_name: str) -> SearchDataSourceDefinitionResponse:
    """
    Get Data Source Definition information by name.

    Args:
        dsd_name: Name of the DSD to search for

    Returns:
        DatasourceDefinitionInfo object with DSD details

    Raises:
        ValueError: If DSD is not found
    """
    list_of_dsd = await _search_data_source_definition(
        SearchDataSourceDefinitionRequest(name=dsd_name)
    )
    dsd = None
    for dsd_res in list_of_dsd:
        if dsd_res.name == dsd_name:
            dsd = dsd_res
            break

    if dsd is None:
        raise ServiceError(
            f"Data source definition '{dsd_name}' not found",
            remediation_steps=(
                f"Verify that the data source definition name '{dsd_name}' is correct. "
                "Use search_data_source_definition to list available definitions and confirm the name."
            ),
        )

    return dsd


async def get_connection_technology(connection_id: str, container_id: str) -> tuple[str, str | None]:
    """Get the technology/scanner name for a connection."""
    params = {"project_id": container_id}

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + CONNECTIONS_BASE_ENDPOINT,
        params=params,
    )
    datasource_type = None
    dsd_name = None
    for conn in response.get("resources", []):  # type: ignore[union-attr]
        if conn["metadata"]["asset_id"] == connection_id:
            datasource_type = conn["entity"]["datasource_type"]
            dsd_name = conn["entity"]["data_source_definition_asset_name"]
            break

    if datasource_type is None:
        raise ServiceError(
            f"Data source type not found for connection {connection_id}",
            remediation_steps=(
                f"Verify that connection '{connection_id}' exists in the given project and is properly configured. "
                "Use search_connection to look up the connection and confirm its details."
            ),
        )

    datasource_type_name = await get_datasource_type_name(datasource_type_id=datasource_type)
    return datasource_type_name, dsd_name

async def _get_connection_technology_details(request: GetConnectionTechnologyDetailsRequest) -> GetConnectionTechnologyDetailsResponse:
    LOGGER.info(
        "Calling tool 'get_connection_technology_details' - projectName=%s, connectionName=%s",
        request.project_name,
        request.connection_name,
    )
    project_id = await find_project_id(request.project_name)
    connection_id = await find_connection_id(request.connection_name, project_id, "project")

    technology, dsd_name = await get_connection_technology(connection_id=connection_id, container_id=project_id)
    dsd: SearchDataSourceDefinitionResponse | None = None
    if dsd_name:
        try:
            dsd = await get_dsd_info(dsd_name)
        except Exception:
            LOGGER.warning("DSD '%s' referenced by connection '%s' was not found; continuing with dsd=None", dsd_name, request.connection_name)

    uses_unified_discovery = uses_unified_lineage_discovery(technology)
    only_manual_inputs = uses_only_manual_inputs(technology)

    dsd_message = "It is not mapped to any datasource definition. Please create one manually." if not dsd else f'It is mapped to {dsd_name} datasource definition.'
    uses_lineage_for_discovery_message = "" if not uses_unified_discovery else "This technology uses Unified lineage for discovery."

    message = (
        f'The {request.connection_name} connection in project {request.project_name} is of type \'{technology}\'. '
        f'{dsd_message} '
        f'{uses_lineage_for_discovery_message} '
    )

    LOGGER.info("Returning user-friendly message: %s", message)

    return GetConnectionTechnologyDetailsResponse(
        project_id=project_id,
        connection_id=connection_id,
        dsd=dsd,
        imported_asset_types=get_asset_expansion_set(technology=None if not dsd else dsd.datasource_type_name, scanner=technology),
        scan_phases=get_phases_for_technology(technology=None if not dsd else dsd.datasource_type_name, scanner=technology),
        uses_unified_lineage_discovery=uses_unified_discovery,
        uses_only_manual_inputs=only_manual_inputs,
        technology=technology)

@service_registry.tool(
    name="get_connection_technology_details",
    description="""Use this tool to inspect a connection in a project and determine its
    technology details for metadata import setup. It resolves the connection and
    project, identifies the underlying datasource technology and mapped data
    source definition, and returns import-relevant capabilities such as
    supported imported asset types, lineage scan phases, whether Unified Lineage
    Discovery is used, and whether only manual lineage inputs are supported.
    Call this before creating a metadata import when you need to understand how
    a connection should be configured for discovery or lineage.""",
    tags={"metadata_management_and_governance"},
    meta={"version": "1.0", "service": "metadata_import"},
    annotations={
        "title": "Get technology details for Metadata Import Setup from a connection in a Project",
        "readOnlyHint": True
    }
)
@auto_context
async def get_connection_technology_details(
    project_name: Annotated[str, Field(description="Name of the project where the metadata import will be created.")],
    connection_name: Annotated[str, Field(description="Name of the connection to use for the metadata import.")],
) -> GetConnectionTechnologyDetailsResponse:
    """
    Wrapper that expands GetConnectionTechnologyDetailsRequest object into individual parameters.

    Args:
        project_name: Name of the project
        connection_name: Name of the connection
    """
    request = GetConnectionTechnologyDetailsRequest(
        connection_name=connection_name,
        project_name=project_name
    )

    # Call the original get_connection_technology_details function
    return await _get_connection_technology_details(request)
