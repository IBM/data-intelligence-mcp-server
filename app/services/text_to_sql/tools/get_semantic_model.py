# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Tool for retrieving schema assets for text-to-SQL operations.
This tool accesses the semantic_automation API to get schema assets.
"""

from typing import Any, List, Literal, Optional
from app.core.registry import service_registry
from app.services.constants import GET_SEMANTIC_MODEL, CONNECTIONS_BASE_ENDPOINT, CAMS_ASSETS_BASE_ENDPOINT
from app.services.text_to_sql.models.get_semantic_model import (
    GetSemanticModelRequest,
    GetSemanticModelResponse,
    SemanticModel,
    PropertyMetadata,
)
from app.services.tool_utils import (
    find_project_id, 
    find_catalog_id, 
    find_connection_id,
    find_data_source_definition_asset_id,
    get_platform_assets_catalog_id
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


async def _resolve_container_id(container_id_or_name: str, container_type: str) -> str:
    """Resolve container ID from name if needed, based on container_type."""
    if container_type == "project":
        return await confirm_uuid(container_id_or_name, find_project_id)
    return await confirm_uuid(container_id_or_name, find_catalog_id)


async def _resolve_connection_ids(
    connection_ids_or_names: Optional[list[str]], container_info: list[dict]
) -> Optional[list[str]]:
    """Resolve connection IDs from names or validate UUID."""
    if not connection_ids_or_names:
        return None

    connection_ids = []

    for connection_id_or_name in connection_ids_or_names:
        connection_id = await _check_or_find_connection_id_in_containers(connection_id_or_name, container_info)
        connection_ids.append(connection_id)

    return connection_ids


async def _check_or_find_connection_id_in_containers(
    connection_id_or_name: str, container_info: list[dict]
) -> str:
    """Check if connection_id_or_name is a UUID, if not, find the connection ID by name in given containers."""
    from app.shared.utils.helpers import is_uuid_bool
    connection_id = ""
    if is_uuid_bool(connection_id_or_name):
        for container in container_info:
            try:
                connection_id = await _validate_connection_uuid(
                    connection_uuid=connection_id_or_name, container_id=container['container_id'], container_type=container['container_type']
                )
                return connection_id
            except ServiceError:
                LOGGER.warning(f"Connection with ID '{connection_id_or_name}' not found in {container['container_type']} '{container['container_id']}'")
    else:
        for container in container_info:
            try:
                connection_id = await find_connection_id(
                    connection_name=connection_id_or_name, container_id=container['container_id'], container_type=container['container_type']
                )
                return connection_id
            except ServiceError:
                LOGGER.warning(f"Connection with name '{connection_id_or_name}' not found in {container['container_type']} '{container['container_id']}'")
    if not connection_id:
        raise ServiceError(f"Connection with name or ID '{connection_id_or_name}' not found in any container.")
    return connection_id


async def _validate_connection_uuid(
    connection_uuid: str, container_id: str, container_type: str
) -> str:
    """Validate that a connection UUID exists in the container."""
    params = {f"{container_type}_id": container_id}
    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + CONNECTIONS_BASE_ENDPOINT,
        params=params,
    )
    connection_ids = [
        conn["metadata"]["asset_id"] for conn in response.get("resources", [])
    ]

    if connection_uuid not in connection_ids:
        raise ServiceError(
            f"Connection with ID '{connection_uuid}' not found in {container_type} '{container_id}'"
        )

    return connection_uuid


async def _resolve_data_source_definition_id(
    data_source_definition_id_or_name: Optional[str],
) -> Optional[str]:
    """Resolve DSD ID from name or validate UUID."""

    if not data_source_definition_id_or_name:
        return None
    
    from app.shared.utils.helpers import is_uuid_bool
    
    dsd_id = ""
    if is_uuid_bool(data_source_definition_id_or_name):
        dsd_id = await _validate_data_source_definition_uuid(data_source_definition_id_or_name)
    else:
        dsd_id = await find_data_source_definition_asset_id(data_source_definition_id_or_name)

    if not dsd_id:
        raise ServiceError(f"DSD with name or ID '{data_source_definition_id_or_name}' not found.")

    return dsd_id


async def _validate_data_source_definition_uuid(
    data_source_definition_id: str,
) -> str:
    """Validate that a data source definition UUID exists."""
    params = {
        "catalog_id": await get_platform_assets_catalog_id(),
        "hide_deprecated_response_fields": False,
        "evaluate_data_policies": True
    }
    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url)
        + CAMS_ASSETS_BASE_ENDPOINT
        + f"/{data_source_definition_id}",
        params=params,
    )
    if  not isinstance(response, dict) or "metadata" not in response:
        raise ServiceError(
            f"Data source definition with ID '{data_source_definition_id}' not found"
        )
    return data_source_definition_id


def _build_request_context(
    request: GetSemanticModelRequest,
    connection_ids: Optional[list[str]],
    container_ids: Optional[list],
    dsd_id: Optional[str],
) -> dict:
    """Build the context dictionary for the API request."""
    context = {}
    if request.asset_ids:
        context["asset_ids"] = request.asset_ids
    if connection_ids:
        context["connection_ids"] = connection_ids
    if container_ids:
        context["containers"] = container_ids
    if dsd_id:
        context["data_source_definition_asset_id"] = dsd_id
    if request.document_library_ids:
        context["document_library_ids"] = request.document_library_ids
    return context


def _parse_property_metadata(prop_data: dict) -> PropertyMetadata:
    """Parse property metadata from API response."""
    return PropertyMetadata(
        name=prop_data.get("name", ""),
        type=prop_data.get("type", ""),
        expanded_name=prop_data.get("expanded_name"),
        description=prop_data.get("description"),
        primary_key=prop_data.get("primary_key", False),
        foreign_key=prop_data.get("foreign_key", []),
        enabled=prop_data.get("enabled", False),
        profiling=prop_data.get("profiling"),
        value_samples=prop_data.get("value_samples"),
    )


def _parse_schema_asset(asset_data: dict) -> SemanticModel:
    """Parse schema asset from API response."""
    properties = [
        _parse_property_metadata(prop) for prop in asset_data.get("properties", [])
    ]

    return SemanticModel(
        asset_id=asset_data.get("asset_id", ""),
        name=asset_data.get("name", ""),
        description=asset_data.get("description"),
        expanded_name=asset_data.get("expanded_name"),
        schema_name=asset_data.get("schema_name"),
        properties=properties,
    )

def _check_container_info_format(container_info: List[dict[str, str | Literal["catalog", "project"]]]) -> None:
    """
    Validate the format of the container_info parameter
    """
    for item in container_info:
        if not isinstance(item, dict):
            raise ValueError("Each item in container_info must be a dictionary")
        if len(item) > 2:
            raise ValueError("container_info items can have at most have 'container_type' and 'container_id_or_name' keys")
        elif len(item) == 2:
            if "container_type" not in item or "container_id_or_name" not in item:
                raise ValueError(
                    "Container_info can only have 'container_type' and 'container_id_or_name' keys"
                )
            if item["container_type"].lower() not in ["catalog", "project"]:
                raise ValueError(
                    f"Invalid value for container_type: {item['container_type']}. Container type must be either 'catalog' or 'project'"
                )
        elif "container_id_or_name" not in item:
                raise ValueError(
                    "Container_info is required to have 'container_id_or_name' key"
                )

def _validate_request(request: GetSemanticModelRequest) -> None:
    """
    Validate the format of the container_info parameter
    Validate that parameters follow the rule:
    - containers alone, OR
    - one other field alone (without containers), OR
    - containers with exactly one other field

    The 'other fields' are: connection_ids_or_names, asset_ids,
    data_source_definition_id_or_name, document_library_ids
    """
    # Check the format of container_info
    if request.container_info:
        _check_container_info_format(request.container_info)

    # Define the optional fields (excluding container_info and query)
    other_fields = [
        'connection_ids_or_names',
        'asset_ids',
        'data_source_definition_id_or_name',
        'document_library_ids'
    ]

    # Count how many other fields are not None
    non_none_other_fields = [
        field for field in other_fields
        if getattr(request, field) is not None
    ]

    has_containers = request.container_info is not None
    other_fields_count = len(non_none_other_fields)

    # Valid scenarios:
    # 1. containers alone (other_fields_count == 0, has_containers == True)
    # 2. one other field alone (other_fields_count == 1, has_containers == False)
    # 3. containers with exactly one other field (other_fields_count == 1, has_containers == True)

    # Invalid combinations
    if not has_containers and other_fields_count > 1:
        raise ValueError(
            f"Without container_info, only one other field can be provided."
            f"Found {other_fields_count} fields: {', '.join(non_none_other_fields)}"
        )

    if has_containers and other_fields_count > 1:
        raise ValueError(
            f"With container_info, only one additional field can be provided."
            f"Found {other_fields_count} fields: {', '.join(non_none_other_fields)}"
        )

async def _get_semantic_model(
    request: GetSemanticModelRequest,
) -> GetSemanticModelResponse:
    # Validate request
    _validate_request(request)

    # Resolve containers and their ids
    container_ids = []
    if request.container_info:
        for container in request.container_info:
            if 'container_type' not in container:
                container_type = "project"
            else:
                container_type = str(container["container_type"]).lower()
            container_id = await _resolve_container_id(container["container_id_or_name"], container_type)
            container_ids.append({"container_id": container_id, "container_type": container_type})

    # Resolve connections and their ids
    if container_ids:
        connection_ids = await _resolve_connection_ids(
            request.connection_ids_or_names, container_ids
        )
    else:
        pac_catalog_id = await get_platform_assets_catalog_id()
        connection_ids = await _resolve_connection_ids(
            request.connection_ids_or_names, [{"container_id": pac_catalog_id, "container_type": "catalog"}]
        )

    # Resolve DSD and its id
    dsd_id = await _resolve_data_source_definition_id(request.data_source_definition_id_or_name)

    LOGGER.info(
        "Calling get_semantic_model for containers: %s, connection ids: %s, asset IDs: %s, data source definition ID: %s, document library IDs: %s",
        container_ids,
        connection_ids,
        request.asset_ids,
        dsd_id,
        request.document_library_ids,
    )

    # Build query parameters and request body
    params = {
        "limit": 10,
        "offset": 0,
    }

    context = _build_request_context(request, connection_ids, container_ids, dsd_id)
    request_body: dict[str, Any] = {"input_question": request.query}

    if context:
        request_body["context"] = context
    
    LOGGER.info(f"Request body: {request_body}")

    # Make API request to get schema assets (POST request with JSON body)
    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GET_SEMANTIC_MODEL,
        params=params,
        json=request_body,
    )

    # Parse the response and build schema assets list
    schema_assets = [
        _parse_schema_asset(asset_data) for asset_data in response.get("resources", [])
    ]

    total_count = response.get("total_count", len(schema_assets))

    LOGGER.info(
        "Successfully retrieved %d schema assets for containers: %s",
        total_count,
        container_ids,
    )

    return GetSemanticModelResponse(
        container_ids=[container['container_id'] for container in container_ids],
        schema_assets=schema_assets,
        total_count=total_count,
    )


@service_registry.tool(
    name="get_semantic_model",
    annotations={
        "readOnlyHint": True,
        "title": "Get Relevant Semantic Model Assets for a User Question"
    },
    description="""Understand user's request about finding schema and assets to answer a question and return list of retrieved assets.
                       This function takes in a user's search prompt (query) as required parameter.
                       Optionally the user can also provide container info: container and container type, connection id or name, asset ids,
                       data source definition asset ids, document library ids.
                       The tool then returns a list of assets that have been found.
                       Example: How many customers are using euros as their currency in Accounts catalog?
                       In this case, query is "How many customers are using euros as their currency in Accounts catalog?" and container_info is [{"container_id_or_name": "Accounts", "container_type": "catalog"}], and connection_ids_or_names is None and asset_ids is None and data_source_definition_id_or_name is None and document_library_ids is None.
                       Example: In TestProject and Commercials with CustDB and Birdb connections, are customers who report late orders through support more likely to churn?
                       In this case, query is "are customers who report late orders through support more likely to churn?", container_info is [{"container_id_or_name": "TestProject"},{"container_id_or_name": "Commercials"}] and connection_ids_or_names is ["CustDB", "Birdb"] and asset_ids is None and data_source_definition_id_or_name is None and document_library_ids is None.
                       
                       IMPORTANT CONSTRAINTS:
                       - query cannot be empty
                       - ONLY ONE parameter out of connection_ids_or_names, asset_ids, data_source_definition_id_or_name, document_library_ids can be non-None
                       - container_info should be in the format: [{"container_id_or_name": "string", "container_type": "string"}, {"container_id_or_name": "string", "container_type": "string"}, ...] where container_id_or_name is the name or id
                         of the container and container_type is either "project" or "catalog". "container_type" is an optional key with default value "project".
                         Example: [{'container_id_or_name': 'testCatalog', 'container_type': 'catalog'}, {'container_id_or_name': 'testProject'}]
                       - optional parameters should be set to None if not provided
                       - Invalid values will result in errors""",
)
@auto_context
async def get_semantic_model(
    query: str,
    container_info: Optional[List[dict[str, str | Literal["project", "catalog"]]]] = None,
    connection_ids_or_names: Optional[List[str]] = None,
    asset_ids: Optional[List[str]] = None,
    data_source_definition_id_or_name: Optional[str] = None,
    document_library_ids: Optional[str] = None,
) -> GetSemanticModelResponse:
    """Wrapper version of get_semantic_model."""
    
    LOGGER.info(
        "get_semantic_model called with: container_info=%s, query=%s, "
        "connection_ids_or_names=%s, asset_ids=%s (type=%s), data_source_definition_id_or_name=%s, document_library_ids=%s",
        container_info, query, connection_ids_or_names,
        asset_ids, type(asset_ids).__name__ if asset_ids is not None else "NoneType",
        data_source_definition_id_or_name, document_library_ids
    )

    request = GetSemanticModelRequest(
        container_info=container_info,
        connection_ids_or_names=connection_ids_or_names,
        asset_ids=asset_ids,
        data_source_definition_id_or_name=data_source_definition_id_or_name,
        document_library_ids=document_library_ids,
        query=query,
    )
    return await _get_semantic_model(request)
