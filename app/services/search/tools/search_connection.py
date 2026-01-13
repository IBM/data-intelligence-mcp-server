from app.core.registry import service_registry
from app.services.search.models.search_connection import SearchConnectionRequest, SearchConnectionResponse

from typing import List, Literal, Optional
from urllib.parse import urlencode

from app.shared.logging import LOGGER, auto_context
from app.shared.exceptions.base import ServiceError
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.helpers import append_context_to_url, is_uuid

from app.services.constants import (
    AUTH_SCOPE_ALL_STR, 
    SEARCH_PATH, 
    JSON_PLUS_UTF8_ACCEPT_TYPE, 
    CONNECTIONS_BASE_ENDPOINT,
)
from app.services.tool_utils import (
    get_datasource_type_name,
    retrieve_container_id,
    find_datasource_type_asset_id,
    check_and_convert_creator_id
)

PROJ_CONNECTION_URL_PREFIX = str(tool_helper_service.ui_base_url) + "/connections/"
CAT_CONNECTION_URL_PREFIX = str(tool_helper_service.ui_base_url) + "/data/catalogs/"


@service_registry.tool(
    name="search_connection",
    description="""Understand user's request about searching connections and return a list of 
                    retrieved connections. Users can choose to filter the results based on 
                    the optional input parameters: container, container type, connection name,
                    data source type, and creator. If no filters are provided, then all available 
                    connections are retrieved.
                    Example: Find all connections.
                    In this case, all input parameters will be None.
                    Example: Find connections in catalog test.
                    In this case, container parameter will be 'test' and container_type will be 'catalog'.
                    Example: Find bird connection in catalog test.
                    In this case, connection_name parameter will be 'bird', container parameter will be 'test' and container_type will be 'catalog'.
                    Example: Find connections with data source postgresql and created by user123 in catalog test.
                    In this case, datasource_type parameter will be 'postgresql', creator parameter will be 'user123', container parameter will be 'test' and container_type will be 'catalog'.

                    IMPORTANT CONSTRAINTS:
                    - container_type needs to be provided if container is provided
                    - container_type must be one of: "catalog", "project"
                    - container and container_type must be provided if one or more of connection_name, datasource_type, or creator is provided
                    - Invalid values will result in errors""",
    tags={"search", "connection"},
    meta={"version": "1.0", "service": "search"}
)
@auto_context
async def search_connection(
    request: SearchConnectionRequest
) -> List[SearchConnectionResponse]:
    # Validate the request
    _validate_connection_request(request)

    LOGGER.info(
        "Starting connection search with container: '%s', container type: '%s', connection name: '%s', data source type: '%s' and creator: '%s'",
        request.container,
        request.container_type,
        request.connection_name,
        request.datasource_type,
        request.creator
    )
    
    if not request.container_type:
        output = await search_connection_global_search()
        if not output:
            raise ServiceError(
            "Could not find any connections."
        )
        return output

    container_id = await retrieve_container_id(request.container, request.container_type)

    headers = {
        "accept": JSON_PLUS_UTF8_ACCEPT_TYPE,
        "Inject-Token" : "false"
    }
    params = {"limit":100, "decrypt_secrets":True, "include_properties":True, "userfs":False}

    if request.creator:
        params["metadata.creator"] = await check_and_convert_creator_id(request.creator)
    if request.connection_name:
        params["entity.name"] = request.connection_name
    if request.datasource_type:
        try:
            is_uuid(request.datasource_type)
            datasource_asset_id = request.datasource_type
        except ServiceError:
            datasource_asset_id = await find_datasource_type_asset_id(request.datasource_type)
        params["entity.datasource_type"] = datasource_asset_id
    params[request.container_type + "_id"] =  container_id

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + CONNECTIONS_BASE_ENDPOINT, 
        headers=headers, 
        params=params, 
        tool_name="search_connection"
    )

    output = []
    for resource in response.get('resources', []):
        if resource['metadata']['asset_category'] != "SYSTEM":
            datasource_type_id = resource['entity']['datasource_type']
            datasource_type_name = await get_datasource_type_name(datasource_type_id)
            connection = SearchConnectionResponse(
                id=resource['metadata']['asset_id'],
                name=resource['entity']['name'],
                url=append_context_to_url(_create_connection_url(resource['metadata']['asset_id'], container_id, request.container_type)),
                create_time=resource['metadata']['create_time'],
                creator_id=resource['metadata']['creator_id'],
                datasource_type_id=datasource_type_id,
                datasource_type_name=datasource_type_name,
                container_id=container_id,
                container_type=request.container_type
            )
            output.append(connection)
    
    if not output:
        raise ServiceError(
            "Could not find any connections."
        )

    return output

@service_registry.tool(
    name="search_connection",
    description="""Understand user's request about searching connections and return a list of
                    retrieved connections. Users can choose to filter the results based on
                    the optional input parameters: container, container type, connection name,
                    data source type, and creator. If no filters are provided, then all available
                    connections are retrieved.
                    Example: Find all connections.
                    In this case, all input parameters will be None.
                    Example: Find connections in catalog test.
                    In this case, container parameter will be 'test' and container_type will be 'catalog'.
                    Example: Find bird connection in catalog test.
                    In this case, connection_name parameter will be 'bird', container parameter will be 'test' and container_type will be 'catalog'.
                    Example: Find connections with data source postgresql and created by user123 in catalog test.
                    In this case, datasource_type parameter will be 'postgresql', creator parameter will be 'user123', container parameter will be 'test' and container_type will be 'catalog'.

                    IMPORTANT CONSTRAINTS:
                    - container_type needs to be provided if container is provided
                    - container_type must be one of: "catalog", "project"
                    - container and container_type must be provided if one or more of connection_name, datasource_type, or creator is provided
                    - Invalid values will result in errors""",
    tags={"search", "connection"},
    meta={"version": "1.0", "service": "search"}
)
@auto_context
async def wxo_search_connection(
    container: Optional[str], container_type: Optional[Literal["catalog", "project"]], connection_name: Optional[str], datasource_type: Optional[str], creator: Optional[str]
) -> List[SearchConnectionResponse]:
    """Watsonx Orchestrator compatible version that expands SearchConnectionRequest object into individual parameters."""

    request = SearchConnectionRequest(
        container=container,
        container_type=container_type,
        connection_name=connection_name,
        datasource_type=datasource_type,
        creator=creator
    )

    # Call the original search_data_source_definition function
    return await search_connection(request)

async def search_connection_global_search() -> List[SearchConnectionResponse]:
    """
    Executes a global search query to search for connections
    across all container types.

    Returns:
        list[SearchConnectionResponse]: A list of all connections found through GS.
    """
    params = {
        "auth_scope": AUTH_SCOPE_ALL_STR
    }

    payload = {
        "query": {
            "bool": {
                "must": [
                    {
                        "term": {
                            "metadata.artifact_type": "connection"
                        }
                    },
                    {
                        "gs_user_query": {
                            "search_string": "*"
                        }
                    }
                ]
            }
        }
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + SEARCH_PATH,
        params=params,
        json=payload,
        tool_name="search_connection"
    )

    output = []
    container_keys = ["project_id", "catalog_id"]
    for connection_info in response.get('rows', []):
        container_key = next((k for k in container_keys if k in connection_info['entity']['assets']), None)
        if not container_key:
            continue
        container_id = connection_info['entity']['assets'][container_key]
        container_type = container_key.replace("_id", "")
        datasource_type_id = ""
        datasource_type_name = ""
        for attribute in connection_info.get('custom_attributes', []):
            if attribute['attribute_name'] == 'connection.datasource_type':
                datasource_type_id = attribute['attribute_value']
                datasource_type_name = await get_datasource_type_name(datasource_type_id)
                break
        connection = SearchConnectionResponse(
            id=connection_info['artifact_id'],
            name=connection_info['metadata']['name'],
            url=append_context_to_url(_create_connection_url(connection_info['artifact_id'], container_id, container_type)),
            create_time=connection_info['metadata']['created_on'],
            creator_id=connection_info['entity']['assets']['rov']['owners'][0],
            datasource_type_id=datasource_type_id,
            datasource_type_name=datasource_type_name,
            container_id=container_id,
            container_type=container_type
        )
        output.append(connection)
    
    return output

def _validate_connection_request(request: SearchConnectionRequest) -> None:
    if request.container and not request.container_type:
        error_msg = "Container identifier cannot be provided without container type. Please provide the container type as well."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)

    if (request.connection_name or request.datasource_type or request.creator) and not (request.container and request.container_type):
        error_msg = "Cannot filter by name, data source type or creator without container information. Please provide container information."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)

def _create_connection_url(conn_id: str, container_id: str, container_type: str) -> str:
    if container_type == "project":
        query_params = {
            "project_id": container_id
        }
        url = PROJ_CONNECTION_URL_PREFIX + conn_id
    elif container_type == "catalog":
        url = CAT_CONNECTION_URL_PREFIX + container_id + "/asset/" + conn_id
        query_params = {
            "udi_edit": "true",
            "ds_gov_summary": "true"
        }
    else:
        return ""
    return f"{url}?{urlencode(query_params)}"
