# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.connections.models.create_data_source_definition import CreateDataSourceDefinitionRequest, CreateDataSourceDefinitionResponse

from typing import Optional, Annotated, Dict, Any, cast
import re
from pydantic import Field
from urllib.parse import urlencode

from app.shared.logging import LOGGER, auto_context
from app.shared.exceptions.base import ServiceError, ValidationError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.services.tool_utils import (
    get_platform_assets_catalog_id,
    find_datasource_type_asset_id,
    get_datasource_type_name,
)

from app.shared.utils.helpers import append_context_to_url, is_uuid_bool

async def _create_data_source_definition(
    request: CreateDataSourceDefinitionRequest
) -> CreateDataSourceDefinitionResponse:
    # Validate the request
    _validate_create_dsd_request(request)

    LOGGER.info(
        "Creating data source definition with name: '%s', datasource_type: '%s', hostname: '%s', port: '%s', physical_collection: '%s', description: '%s', and tags: '%s'",
        request.name,
        request.datasource_type,
        request.hostname,
        request.port,
        request.physical_collection,
        request.description,
        request.tags
    )

    # Retrieve platform asset assets catalog ID
    pac_catalog_id = await get_platform_assets_catalog_id()
    params = {
        "catalog_id": pac_catalog_id,
        "hide_deprecated_response_fields": False
    }

    # Resolve datasource_type to UUID
    if is_uuid_bool(request.datasource_type):
        datasource_type_id: str = request.datasource_type
    else:
        datasource_type_id = await find_datasource_type_asset_id(request.datasource_type)

    # Find data source type name before executing POST request to avoid 
    # raising error after tool succeded, leaving orphaned asset.
    type_label = await get_datasource_type_name(datasource_type_id)

    # Build payload
    endpoint_entry = {
        "host": request.hostname,
        "port": request.port
    }
    if request.physical_collection is not None:
        endpoint_entry["physical_collection"] = request.physical_collection

    payload: dict = {
        "metadata": {
            "name": request.name,
            "asset_type": "ibm_data_source",
        },
        "entity": {
            "ibm_data_source": {
                "data_source_type_id": datasource_type_id,
                "data_source_flags": [],
                "data_source_state": "ACTIVE",
                "data_source_encoding": "UTF-8",
                "data_source_endpoints": {
                    "values": [endpoint_entry]
                },
                "data_source_protection_method": "default-enforcement",
            }
        },
    }
    if request.description is not None:
        payload["metadata"]["description"] = request.description
    if request.tags is not None:
        payload["metadata"]["tags"] = request.tags

    # Send Post request and get response
    url = str(tool_helper_service.base_url) + CAMS_ASSETS_BASE_ENDPOINT
    response = await tool_helper_service.execute_post_request(
        url=url,
        params=params,
        json=payload,
        tool_name="create_data_source_definition",
    )

    # Build response object
    # Non-2xx responses are raised as ExternalAPIError by execute_post_request
    response_dict = cast(Dict[str, Any], response)
    try:
        asset_id = response_dict["metadata"]["asset_id"]
        dsd_name = response_dict["metadata"]["name"]
    except (KeyError, TypeError) as e:
        raise ServiceError(
            f"Could not create data source definition with name {request.name}, data source type {request.datasource_type}, host {request.hostname}, port {request.port} and physical collection {request.physical_collection}.",
            service="connections",
            tool="create_data_source_definition",
            remediation_steps=(
                "Invoke the search_data_source_definition tool with the same hostname, port, and physical_collection "
                "to check whether a data source definition with this endpoint already exists. If one exists, return it "
                "to the user instead of creating a new one. Otherwise, confirm the parameter values with the user and "
                "retry this tool."
            ),
        ) from e

    return CreateDataSourceDefinitionResponse(
        dsd_id=asset_id,
        name=dsd_name,
        datasource_type_name=type_label,
        endpoint={
            "hostname": request.hostname,
            "port": request.port,
            "physical_collection": request.physical_collection
        },
        url=append_context_to_url(_create_dsd_url(asset_id, pac_catalog_id))
    )

@service_registry.tool(
    name="create_data_source_definition",
    annotations={
        "title": "Create a New Data Source Definition",
        "readOnlyHint": False,
    },
    description="""
                Use this tool to create a new data source definition (DSD) in the platform assets catalog.
                Example: Create a new DSD named postgresql_dev_db1 with datasource type postgresql with host c-01.private.us-south.link.satellite.cloud.ibm.com,  port number 33962 and database Bird.
                In this case, name parameter will be 'postgresql_dev_db1', datasource_type parameter will be 'postgresql', hostname parameter will be 'c-01.private.us-south.link.satellite.cloud.ibm.com', port parameter will be '33962', physical_collection parameter will be 'Bird', and all other parameters will be None.
                Example: Create a Apache Impala data source definition called test_dsd with endpoint localhost:0000 and database db1.
                In this case, name parameter will be 'test_dsd', datasource_type parameter will be 'Apache Impala', hostname parameter will be 'localhost', port parameter will be '0000', physical_collection parameter will be 'db1', and all other parameters will be None.
                Example: Create a new Amazon S3 dsd. Name it amazon_s3_dsd and set its IP 12.34.56.789, port 443 and bucket testbucket. Tag it with 'Amazon S3' and 'testing'.
                In this case, name parameter will be 'amazon_s3_dsd', datasource_type parameter will be 'Amazon S3', hostname parameter will be '12.34.56.789', port parameter will be '443', physical_collection parameter will be 'testbucket', tags parameter will be ['Amazon S3', 'testing'].
                IMPORTANT CONSTRAINT:
                - name must be provided
                - datasource_type must be provided
                - hostname must be provided
                - port must be provided
                Return: * dsd_id: Unique identifier of the newly created data source definition * name: Name of the newly created data source definition * datasource_type_name: Name of the data source type * endpoint: dictionary containing information of the data source definition's endpoints. * url: URL of the newly created data source definition.
                """,
    tags={"create", "data_source_definition", "metadata_management_and_governance"},
    meta={"version": "1.0", "service": "connections"},
)

@auto_context
async def create_data_source_definition(
    name: Annotated[str, Field(description="Name of the data source definition")],
    datasource_type: Annotated[str, Field(description="Datasource type name or UUID")],
    hostname: Annotated[str, Field(description="Hostname/IP address of the data source definition")],
    port: Annotated[str, Field(description="Connection port number of the data source definition")],
    physical_collection: Annotated[Optional[str], Field(description="Database/instance name, required for some datasource type")] = None,
    description: Annotated[Optional[str], Field(description="Purpose and owner information of the data source definition")] = None,
    tags: Annotated[Optional[list[str]], Field(description="Tags for categorization")] = None
) -> CreateDataSourceDefinitionResponse:
    """Wrapper that expands CreateDataSourceDefinitionRequest object into individual parameters."""

    request = CreateDataSourceDefinitionRequest(
        name=name,
        datasource_type=datasource_type,
        hostname=hostname,
        port=port,
        physical_collection=physical_collection,
        description=description,
        tags=tags
    )

    # Call the original _create_data_source_definition function
    return await _create_data_source_definition(request=request)


_VALID_NAME_RE = re.compile(r"^[A-Za-z0-9_\-. ]+$")

def _validate_create_dsd_request(request: CreateDataSourceDefinitionRequest) -> None:
    # Data source type must not be empty
    if not request.datasource_type or not request.datasource_type.strip():
        error_msg = "datasource_type must not be empty."
        LOGGER.error(error_msg)
        raise ValidationError(
            error_msg,
            service="connections",
            tool="create_data_source_definition",
            remediation_steps=(
                "Provide a non-empty datasource_type (a type name such as 'postgresql' or its UUID) if available "
                "from the conversation, otherwise ask the user for the data source type, then retry this tool."
            ),
        )

    # The name can only contain letters, numbers, underscore, dash, space, and period.
    # The name can't be only blank spaces.
    if not request.name or not request.name.strip():
        error_msg = "Data source definition name must not be blank."
        LOGGER.error(error_msg)
        raise ValidationError(
            error_msg,
            service="connections",
            tool="create_data_source_definition",
            remediation_steps=(
                "Provide a non-blank name if available from the conversation, otherwise ask the user for a name "
                "(recommended format: '[DataSourceType][Environment][DatabaseName]'), then retry this tool."
            ),
        )
    if not _VALID_NAME_RE.match(request.name):
        error_msg = (
            "Data source definition name contains invalid characters. "
            "Only letters, numbers, underscore (_), dash (-), space, and period (.) are allowed."
        )
        LOGGER.error(error_msg)
        raise ValidationError(
            error_msg,
            service="connections",
            tool="create_data_source_definition",
            remediation_steps=(
                "Remove or replace the invalid characters in name so it only contains letters, numbers, "
                "underscore (_), dash (-), space, and period (.). Confirm the corrected name with the user, "
                "then retry this tool."
            ),
        )

    if request.port and not request.hostname:
        error_msg = "Port cannot be provided without hostname. Please provide the hostname with it."
        LOGGER.error(error_msg)
        raise ValidationError(
            error_msg,
            service="connections",
            tool="create_data_source_definition",
            remediation_steps=(
                "Provide the hostname (hostname or IP address of the data source) if available from the "
                "conversation, otherwise ask the user for it, then retry this tool with both hostname and port."
            ),
        )

def _create_dsd_url(dsd_id: str, catalog_id: str) -> str:
    """
    Creates the URL for a data source definition.
    Args:
        dsd_id (str): The ID of the data source definition.
        catalog_id (str): The ID of the catalog.
    Returns:
        str: The URL for the data source definition.
    """
    dsd_url_prefix = str(tool_helper_service.ui_base_url) + "/data/catalogs/"
    url = dsd_url_prefix + catalog_id + "/asset/" + dsd_id
    query_params = {
        "ds_gov_summary": "true"
    }
    return f"{url}?{urlencode(query_params)}"
