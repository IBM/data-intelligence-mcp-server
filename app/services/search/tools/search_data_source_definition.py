from app.core.registry import service_registry
from app.services.search.models.search_data_source_definition import SearchDataSourceDefinitionRequest, SearchDataSourceDefinitionResponse

from typing import List, Optional

from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.tool_utils import (
    get_platform_assets_catalog_id, 
    find_datasource_type_asset_id, 
    get_datasource_type_name
)
from app.shared.utils.helpers import is_uuid
from app.shared.logging import LOGGER, auto_context
from app.services.constants import ASSET_TYPE_BASE_ENDPOINT

@service_registry.tool(
    name="search_data_source_definition",
    description="""Understand user's request about searching data source definitions aka DSD
                    and return a list of retrieved DSDs. Users can choose to filter the 
                    results based on the optional input parameters: data source type, 
                    hostname, port, or physical collection. If no filters are provided, then 
                    all available DSDs are retrieved.
                    Example: Find all dsds.
                    In this case, all input parameters will be None.
                    Example: Find DSDs with datasource type postgresql.
                    In this case, datasource_type parameter will be 'postgresql', and hostname, port, physical_collection will be None.
                    Example: Find dsds with endpoint localhost:0000 and database db1.
                    In this case, hostname parameter will be 'localhost', port parameter will be '0000', physical_collection parameter will be 'db1' and datasource_type parameter will be None.
                    Example: Find data source definitons with hostname someendpoint and bucket testbucket.
                    In this case, hostname parameter will be 'someendpoint', physical_collection parameter will be 'testbucket', and port and datasource_type parameters will be None.
                    
                    IMPORTANT CONSTRAINTS:
                    - All possible combinations of input parameters include:
                        - Only data source type
                        - Only hostname
                        - Only physical collection (database name, bucket name, or project id)
                        - Hostname + port
                        - Hostname + port + physical collection
                    - Invalid values will result in errors""",
    tags={"search", "data_source_definition"},
    meta={"version": "1.0", "service": "search"}
)
@auto_context
async def search_data_source_definition(
    request: SearchDataSourceDefinitionRequest
) -> List[SearchDataSourceDefinitionResponse]:
    # Validate the request 
    if request.port and not request.hostname:
        error_msg = "Port cannot be provided as a solo filter. Please provide the hostname with it."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)

    if request.datasource_type and (request.hostname or request.port or request.physical_collection):
        error_msg = "Datasource type filter cannot be provided with endpoint or physical collection filter."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)

    LOGGER.info(
        "Starting Data source definition search with datasource_type: '%s', hostname: '%s', port: '%s' and physical_collection: '%s'",
        request.datasource_type,
        request.hostname,
        request.port,
        request.physical_collection
    )

    params = {
        "catalog_id": await get_platform_assets_catalog_id(),
        "hide_deprecated_response_fields": False
    }

    payload = {"limit": 100, "sort": "asset.name<string>", "include": "entity"}

    if request.datasource_type:
        try:
            is_uuid(request.datasource_type)
            datasource_asset_id = request.datasource_type
        except ServiceError:
            datasource_asset_id = await find_datasource_type_asset_id(request.datasource_type)
        payload["query"] = f"ibm_data_source.data_source_type_id:{datasource_asset_id}"
    elif request.hostname or request.port or request.physical_collection:
        payload["query"] = retrieve_asset_endpoint_query(request.hostname, request.port, request.physical_collection)
    else:
        payload["query"] = "*:*"
    
    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + ASSET_TYPE_BASE_ENDPOINT + "/ibm_data_source/search",
        params=params,
        json=payload,
        tool_name="search_data_source_definition"
    )

    output = []
    for result in response.get('results', []):
        datasource_type_id = result["entity"]["ibm_data_source"]["data_source_type_id"]
        datasource_type_name = await get_datasource_type_name(datasource_type_id)
        dsd = SearchDataSourceDefinitionResponse(
            id=result["metadata"]["asset_id"],
            name=result["metadata"]["name"],
            create_time=result["metadata"]["created_at"],
            creator_id=result["metadata"]["creator_id"],
            datasource_type_id=datasource_type_id,
            datasource_type_name=datasource_type_name
        )
        output.append(dsd)

    if not output:
        raise ServiceError(
            "Could not find data source definition(s)."
        )

    return output

@service_registry.tool(
    name="search_data_source_definition",
    description="""Understand user's request about searching data source definitions aka DSD
                    and return a list of retrieved DSDs. Users can choose to filter the
                    results based on the optional input parameters: data source type,
                    hostname, port, or physical collection. If no filters are provided, then
                    all available DSDs are retrieved.
                    Example: Find all dsds.
                    In this case, all input parameters will be None.
                    Example: Find DSDs with datasource type postgresql.
                    In this case, datasource_type parameter will be 'postgresql', and hostname, port, physical_collection will be None.
                    Example: Find DSDs with endpoint localhost:0000 and database db1.
                    In this case, hostname parameter will be 'localhost', port parameter will be '0000', physical_collection parameter will be 'db1' and datasource_type parameter will be None.
                    Example: Find data source definitons with hostname someendpoint and bucket testbucket.
                    In this case, hostname parameter will be 'someendpoint', physical_collection parameter will be 'testbucket', and port and datasource_type parameters will be None.

                    IMPORTANT CONSTRAINTS:
                    - All possible combinations of input parameters include:
                        - Only data source type
                        - Only hostname
                        - Only physical collection (database name, bucket name, or project id)
                        - Hostname + port
                        - Hostname + port + physical collection
                        - Datasource type + hostname + port + physical collection
                    - Invalid values will result in errors""",
    tags={"search", "data_source_definition"},
    meta={"version": "1.0", "service": "search"}
)
@auto_context
async def wxo_search_data_source_definition(
    datasource_type: Optional[str], hostname: Optional[str], port: Optional[str], physical_collection: Optional[str]
) -> List[SearchDataSourceDefinitionResponse]:
    """Watsonx Orchestrator compatible version that expands SearchDataSourceDefinitionRequest object into individual parameters."""

    request = SearchDataSourceDefinitionRequest(
        datasource_type=datasource_type,
        hostname=hostname,
        port=port,
        physical_collection=physical_collection
    )

    # Call the original search_data_source_definition function
    return await search_data_source_definition(request)

def retrieve_asset_endpoint_query(hostname: str, port: str, physical_collection: str) -> str:
    """
    Format endpoint query parameters for data source definition search.
    
    Creates a properly formatted query string for the DSD search API based on the provided
    hostname, port, and physical collection parameters.
    
    Args:
        hostname (str): Hostname or IP address of the data source.
        port (str): Port number of the data source.
        physical_collection (str): Database name, bucket name, or project ID.
    
    Returns:
        str: Formatted query string for the DSD search API.
    """

    query_str = ""
    if physical_collection and not hostname:
        query_str = f"asset.endpoint:{physical_collection}"
    elif hostname:
        if port:
            query_str = f"asset.endpoint:{hostname}_{port}_"
        else:
            query_str = f"asset.endpoint:{hostname}*_"
        if physical_collection:
            query_str += f"{physical_collection}"
    return query_str
