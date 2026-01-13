# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json
import asyncio
from typing import Literal
from app.services.constants import (
    CONNECTIONS_BASE_ENDPOINT,
    PROJECTS_BASE_ENDPOINT,
    CATALOGS_BASE_ENDPOINT,
    SPACES_BASE_ENDPOINT,
    ASSET_TYPE_BASE_ENDPOINT,
    GS_BASE_ENDPOINT,
    DATASOURCE_TYPES_BASE_ENDPOINT,
    JSON_PLUS_UTF8_ACCEPT_TYPE,
    EN_LANGUAGE_ACCEPT_TYPE,
    USER_PROFILES_BASE_ENDPOINT,
    FIELD_PREFERENCES,
)
from app.shared.exceptions.base import ServiceError
from app.shared.utils.helpers import get_closest_match, get_project_or_space_type_based_on_context, append_context_to_url, is_uuid
from app.shared.utils.tool_helper_service import tool_helper_service
from app.core.auth import get_bss_account_id, get_user_identifier
from app.core.settings import settings

METADATA_ARTIFACT_TYPE = "metadata.artifact_type"
METADATA_NAME = "metadata.name"
ENTITY_ASSETS_PROJECT_ID = "entity.assets.project_id"
ENTITY_ASSETS_CATALOG_ID = "entity.assets.catalog_id"
ARTIFACT_TYPE_CATEGORY = "category"
ARTIFACT_TYPE_DATA_ASSET = "data_asset"
CATEGORY_UNCATEGORIZED = "uncategorized"


async def find_project_id(project_name: str) -> str:
    """
    Find id of project based on project name.

    Args:
        project_name (str): The name of the project which is used to find a project id.

    Returns:
        uuid.UUID: Unique identifier of the project.
    """

    params = {"limit": 100}

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + PROJECTS_BASE_ENDPOINT,
        params=params,
    )

    projects = [
        {"name": project["entity"]["name"], "id": project["metadata"]["guid"]}
        for project in response.get("resources", {})
    ]
    result_id = get_closest_match(projects, project_name)
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"find_project_id failed to find any projects with the name '{project_name}'"
        )


async def find_connection_id(connection_name: str, project_id: str) -> str:
    """
    Find id of connection based on connection name.

    Args:
        connection_name (str): The name of the connection which is used to find a connection id,
        project_id (uuid.UUID): The unique identifier of the project

    Returns:
        uuid.UUID: Unique identifier of the project.
    """

    params = {"project_id": project_id}

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + CONNECTIONS_BASE_ENDPOINT,
        params=params,
    )

    connections = [
        {
            "name": connection["entity"]["name"],
            "id": connection["metadata"]["asset_id"],
        }
        for connection in response.get("resources", {})
    ]
    result_id = get_closest_match(connections, connection_name)
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"find_connection_id failed to find any connections with the name '{connection_name}'"
        )
    
async def is_project_exist(project_identifier: str):
    """
    Check if a project exists by ID or name.
    
    This unified function handles both project ID and name lookups efficiently
    by fetching the project list once and checking both criteria.

    Args:
        project_identifier (str): The project ID (UUID) or name to check

    Returns:
        tuple: A tuple containing:
            - bool: True if project exists, False otherwise
            - str: Project type (e.g., 'df', 'cpdaas', 'wx') if found, empty string otherwise
            - str: Project ID if found, empty string otherwise
    
    Examples:
        >>> await is_project_exist("my-project-name")
        (True, "df", "abc-123-def-456")
        
        >>> await is_project_exist("abc-123-def-456")
        (True, "df", "abc-123-def-456")
        
        >>> await is_project_exist("non-existent")
        (False, "", "")
    """

    params = {"limit": 100}

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + PROJECTS_BASE_ENDPOINT,
        params=params
    )

    projects = [
        {
            "name": project["entity"]["name"],
            "type": project["entity"]["type"],
            "id": project["metadata"]["guid"]
        }
        for project in response.get("resources", [])
    ]

    # Check for exact match by ID or name
    for project in projects:
        if project["id"] == project_identifier or project["name"] == project_identifier:
            return True, project["type"], project["id"]
        
    return False, "", ""


# Backward compatibility wrappers
async def is_project_exist_by_name(project_name: str):
    """
    Check if a project exists by name (backward compatibility wrapper).
    
    This function maintains backward compatibility with existing code while
    delegating to the unified is_project_exist function.

    Args:
        project_name (str): The name of the project to check

    Returns:
        tuple: (bool, str, str) - (exists, project_type, project_id)
    """
    return await is_project_exist(project_name)


async def is_project_exist_by_id(project_id: str):
    """
    Check if a project exists by ID (backward compatibility wrapper).
    
    This function maintains backward compatibility with existing code while
    delegating to the unified is_project_exist function.

    Args:
        project_id (str): The ID of the project to check

    Returns:
        bool: True if project exists, False otherwise
    """
    exists, _, _ = await is_project_exist(project_id)
    return exists

async def find_catalog_id(catalog_name: str) -> str:
    """
    Find id of catalog based on catalog name.

    Args:
        catalog_name (str): The name of the catalog which is used to find a catalog id.

    Returns:
        uuid.UUID: Unique identifier of the catalog.
    """

    params = {"limit": 1, "name": catalog_name}

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + CATALOGS_BASE_ENDPOINT,
        params=params
    )

    result_id = None
    for catalog in response.get("catalogs", []):
        result_id = catalog["metadata"]["guid"]

    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"find_catalog_id failed to find any catalog with the name '{catalog_name}'"
        )

async def get_platform_assets_catalog_id() -> str:
    """
    Find id of the Platform Assets Catalog attached
    to current user's account.

    Returns:
        uuid.UUID: Unique identifier of the Platform Assets catalog.
    """

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + CATALOGS_BASE_ENDPOINT + "/ibm-global-catalog"
    )

    result_id = response.get("metadata", {}).get("guid", None)

    if result_id:
        return result_id
    else:
        raise ServiceError(
            "get_platform_assets_catalog_id failed to find the platform assets catalog"
        )


def _build_container_from_response(
    response: dict, container_type: str, id_field: str = "guid"
):
    """
    Build a Container object from API response.
    
    Args:
        response: API response dictionary
        container_type: Type of container ("project", "catalog", "space")
        id_field: Field name for ID in metadata ("guid" or "id")
        
    Returns:
        Container object
    """
    from app.services.search.models.container import Container, ContainerType
    
    container_id = response.get("metadata", {}).get(id_field, "")
    name = response.get("entity", {}).get("name", "")
    
    if container_type == "project":
        url = append_context_to_url(
            f"{tool_helper_service.ui_base_url}/projects/{container_id}/overview",
            settings.di_context
        )
        return Container(
            id=container_id,
            name=name,
            type=ContainerType.PROJECT,
            url=url
        )
    elif container_type == "space":
        url = append_context_to_url(
            f"{tool_helper_service.ui_base_url}/ml-runtime/spaces/{container_id}",
            settings.di_context
        )
        return Container(
            id=container_id,
            name=name,
            type=ContainerType.SPACE,
            url=url
        )
    else:  # catalog
        url = append_context_to_url(
            f"{tool_helper_service.ui_base_url}/data/catalogs/{container_id}",
            settings.di_context
        )
        return Container(
            id=container_id,
            name=name,
            type=ContainerType.CATALOG,
            url=url
        )


async def find_asset_container_by_id(
    container_id: str, container_type: str
):
    """
    Find container based on its id.
    
    Args:
        container_id: The ID of the container
        container_type: The type of the container - "project", "catalog", or "space"
        
    Returns:
        Container object with the given id
        
    Raises:
        ServiceError: If the container is not found
    """
    if container_type == "project":
        params = {"bss_account_id": await get_bss_account_id()}
        project_type = get_project_or_space_type_based_on_context()
        if project_type:
            params["type"] = project_type
            
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{PROJECTS_BASE_ENDPOINT}/{container_id}",
            params=params,
        )
        return _build_container_from_response(response, container_type, "guid")
        
    elif container_type == "space":
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{SPACES_BASE_ENDPOINT}/{container_id}",
        )
        return _build_container_from_response(response, container_type, "id")
        
    else:  # catalog or default
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{CATALOGS_BASE_ENDPOINT}/{container_id}",
        )
        return _build_container_from_response(response, container_type, "guid")


async def find_asset_container_by_name(
    container_name: str, container_type: str
):
    """
    Find container based on its name using fuzzy matching.
    
    Args:
        container_name: The name of the container
        container_type: The type of the container - "project", "catalog", or "space"
        
    Returns:
        Container object with the given name
        
    Raises:
        ServiceError: If the container is not found
    """
    # Import here to avoid circular dependency
    from app.services.search.tools.list_containers import _list_asset_containers
    from app.services.search.models.container import ContainerType
    
    # Convert string to ContainerType enum
    container_type_enum = ContainerType(container_type)
    containers = await _list_asset_containers(container_type_enum)
    
    if not containers:
        raise ServiceError(f"No {container_type}s found")
    
    # Create list of name-id pairs for fuzzy matching
    containers_names_ids = [
        {"name": container.name, "id": container.id} for container in containers
    ]
    
    # Find closest match
    result_id = get_closest_match(containers_names_ids, container_name)
    
    if result_id:
        # Return the matching container
        for container in containers:
            if container.id == result_id:
                return container
    
    raise ServiceError(
        f"Couldn't find any {container_type} with the name '{container_name}'"
    )


async def find_asset_id(
    asset_name: str, container_id: str, container_type: str
) -> str:
    """
    Find id of asset based on asset name.

    Args:
        asset_name (str): Name of the asset.
        catalog_id (str): ID of the to find the asset in.
        container_type (str): Type of container (project/catalog) to find the asset in.

    Returns:
        uuid.UUID: Unique identifier of the asset.
    """
    params = {
        container_type + "_id": container_id,
        "hide_deprecated_response_fields": True,
    }
    payload = {"query": "*:*"}

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + ASSET_TYPE_BASE_ENDPOINT + "/asset/search",
        params=params,
        json=payload,
    )

    result_id = None
    if response["total_rows"] > 0:
        asset_list = [
            {"name": asset["metadata"]["name"], "id": asset["metadata"]["asset_id"]}
            for asset in response["results"]
        ]
        result_id = get_closest_match(asset_list, asset_name)

    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"find_asset_id failed to find any asset with the name '{asset_name}'"
        )

async def find_datasource_type_asset_id(datasource_type: str) -> str:
    """
    Find the asset ID for a datasource type by its name.

    Searches for a datasource type matching the provided name or label and returns its ID.
    The search is case-insensitive and matches partial names.

    Args:
        datasource_type (str): The name or label of the datasource type (e.g., "db2", "postgresql").

    Returns:
        str: The asset ID (UUID) of the matching datasource type, or empty string if not found.
    """

    headers = {
        "accept": JSON_PLUS_UTF8_ACCEPT_TYPE,
        "Accept-Language": EN_LANGUAGE_ACCEPT_TYPE,
    }

    params = {
        "offset": 0,
        "limit": 100,
        "connection_properties": False,
        "interaction_properties": False,
        "discovery": False,
        "actions": False,
        "generate_transitive_conditions": False,
        "show_data_source_definitions_only": False,
        "show_data_source_definition_section": False
    }

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + DATASOURCE_TYPES_BASE_ENDPOINT,
        headers=headers,
        params=params
    )

    total_types = response.get("total_count")
    offset = params["offset"]
    datasource_type = datasource_type.lower()

    while offset <= total_types:
        for resource in response.get('resources', []):
            datasource_type_name = resource['entity']['name'].lower()
            datasource_type_label = resource['entity']['label'].lower()
            if datasource_type == datasource_type_name or datasource_type == datasource_type_label:
                return resource['metadata']['asset_id']
        offset += 100
        params["offset"] += offset
        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.base_url) + DATASOURCE_TYPES_BASE_ENDPOINT, 
            headers=headers,
            params=params
        )

    raise ServiceError(
        f"find_datasource_type_asset_id failed to find any datasource type with the name '{datasource_type}'"
    )

async def get_datasource_type_name(datasource_type_id: str) -> str:
    """
    Get the display name of a datasource type from its ID.

    Retrieves the human-readable label for a datasource type using its unique identifier.

    Args:
        datasource_type_id (str): The unique identifier (UUID) of the datasource type.

    Returns:
        str: The display name/label of the datasource type.
    """

    headers = {
        "accept": JSON_PLUS_UTF8_ACCEPT_TYPE,
        "Accept-Language": EN_LANGUAGE_ACCEPT_TYPE,
    }
    params = {
        "generate_transitive_conditions": False,
        "show_data_source_definition_section": False
    }
    response = await tool_helper_service.execute_get_request(
        url=f'{str(tool_helper_service.base_url)}{DATASOURCE_TYPES_BASE_ENDPOINT}/{datasource_type_id}',
        headers=headers,
        params=params,
    )

    result = response.get("entity", {}).get("label", "")

    if result:
        return result
    else:
        raise ServiceError(
            f"get_datasource_type_name failed to find any datasource type with id '{datasource_type_id}'"
        )


async def find_metadata_enrichment_id(
    metadata_enrichment_name: str, project_id: str
) -> str:
    """
    Find ID of metadata enrichment based on metadata enrichment name.

    Args:
        metadata_enrichment_name (str): The name of the metadata enrichment that you want to execute.
        project_id (uuid.UUID): The ID of the project in which you want to execute a metadata enrichment.

    Returns:
        str: The unique identifier of the metadata enrichment.

    Raises:
        ToolProcessFailedError: If the metadata enrichment asset is not found.
    """

    post_url = (
        tool_helper_service.base_url + "/v2/asset_types/metadata_enrichment_area/search"
    )
    query_params = {
        "project_id": project_id,
    }
    payload = {"query": f'metadata_enrichment_area.name:"{metadata_enrichment_name}"'}
    response = await tool_helper_service.execute_post_request(
        url=post_url,
        params=query_params,
        json=payload,
    )

    result_id = None
    list_of_results = response.get("results", [])
    for metadata_enrichment in list_of_results:
        result_id = metadata_enrichment.get("metadata", {}).get("asset_id", None)

    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"The metadata enrichment asset was not found with the name:'{metadata_enrichment_name}'"
        )


async def find_asset_id_exact_match(
    asset_name: str,
    container_id: str,
    container_type: Literal["catalog", "project"] = "project",
    artifact_type: str = "data_asset",
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> str:
    """
    Find id of asset in specified project based on asset name.
    Includes retry logic to handle indexing delays for newly created assets.

    Args:
        asset_name (str): The name of the asset.
        container_id (str): UUID of the project or catalog containing the asset.
        container_type (Literal["project", "catalog"]): Type of container - either "project" or "catalog".
        artifact_type (str): The artifact type of the asset
        max_retries (int): Maximum number of retries if asset not found (default: 3)
        retry_delay (float): Delay in seconds between retries (default: 2.0)

    Returns:
        str: Unique identifier of the asset
    """
    if container_type == "catalog":
        query_container = ENTITY_ASSETS_CATALOG_ID
    else:
        query_container = ENTITY_ASSETS_PROJECT_ID
    
    query_params = {
        "query": f"metadata.name:{asset_name} AND {query_container}:{container_id}"
    }
    
    # Retry logic to handle indexing delays
    for attempt in range(max_retries + 1):
        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
            params=query_params,
        )

        asset_id = None
        for row in response.get("rows", []):
            metadata = row["metadata"]
            if (
                metadata["artifact_type"] == artifact_type
                and metadata["name"] == asset_name
            ):
                asset_id = row["artifact_id"]
                break
        
        if asset_id:
            return asset_id
        
        # If not found and retries remaining, wait and try again
        if attempt < max_retries:
            from app.shared.logging.utils import LOGGER
            LOGGER.warning(
                f"Asset '{asset_name}' not found in {container_type} '{container_id}'. "
                f"Retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(retry_delay)
    
    # All retries exhausted
    raise ServiceError(
        f"Couldn't find any datasets with the name '{asset_name}' in {container_type} '{container_id}'"
    )


def confirm_list_str(list_or_str: list[str] | str) -> list[str]:
    """
    Convert a string or list input into a list of strings.

    This utility function normalizes input that can be either a string or a list of strings
    into a consistent list format. It handles multiple string formats including JSON arrays
    and single values.

    Processing logic:
    - If input is already a list: returns it unchanged
    - If input is a string:
        1. Attempts to parse as JSON (with single quotes converted to double quotes)
        2. If JSON parsing succeeds and result is a list: returns the parsed list
        3. If JSON parsing succeeds but result is not a list: wraps it in a list
        4. If JSON parsing fails: wraps the original string in a list

    Args:
        list_or_str (list[str] | str): The input which can be either:
            - A list of strings (returned as-is)
            - A JSON-formatted string representing a list (e.g., '["item1", "item2"]')
            - A single string value (wrapped in a list)

    Returns:
        list[str]: A list of strings. Always returns a list, even for single string inputs.

    Examples:
        >>> get_list_from_str(["a", "b", "c"])
        ["a", "b", "c"]

        >>> get_list_from_str('["item1", "item2"]')
        ["item1", "item2"]

        >>> get_list_from_str("single_value")
        ["single_value"]

        >>> get_list_from_str("['x', 'y', 'z']")
        ["x", "y", "z"]
    """
    if isinstance(list_or_str, str):
        try:
            parsed = json.loads(list_or_str.replace("'", '"'))
            if isinstance(parsed, list):
                list_or_str = parsed
            else:
                list_or_str = [parsed]
        except json.JSONDecodeError:
            list_or_str = [list_or_str]

    return list_or_str


async def find_category_id(category_name: str) -> str:
    """
    Find id of category based on category name

    Args:
        category_name (str): Name of the category

    Returns:
        str: Category id of the category.
    """

    must_match = [
        {"match": {METADATA_ARTIFACT_TYPE: ARTIFACT_TYPE_CATEGORY}},
        {"match": {METADATA_NAME: category_name}},
    ]
    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json={"query": {"bool": {"must": must_match}}},
    )

    result_id = None
    for row in response.get("rows", []):
        metadata = row["metadata"]
        if metadata["artifact_type"] == "category" and (
            metadata["name"] == category_name
            or (
                metadata["name"] == f"[{CATEGORY_UNCATEGORIZED}]"
                and category_name == CATEGORY_UNCATEGORIZED
            )
        ):
            entity = row["entity"]
            result_id = entity["artifacts"]["artifact_id"]
            break
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"Couldn't find any categories with the name '{category_name}'"
        )

async def retrieve_container_id(container_id: str, container_type: str) -> str:
    """
    Validate or convert a container name to its ID.

    This function checks if a container id was provided. If it is, then it
    checks if the provided container ID is in a valid UUID format. If not, it attempts to find
    a matching catalog or project by its name. If no container id is provided, it
    returns the platform assets catalog's ID.

    Args:
        container_id (str): Name or UUID of the project or catalog
        container_type (str): Type of container - "project" or "catalog"

    Returns:
        uuid.UUID: A valid container ID for the specified container.
    """
    if container_id:
        try:
            is_uuid(container_id)
        except ServiceError:
            if "catalog" in container_type:
                container_id = await find_catalog_id(container_id)
            else:
                container_id = await find_project_id(container_id)
    else:
        container_id = await get_platform_assets_catalog_id()

    return container_id

async def check_and_convert_creator_id(creator_id: str) -> str:
    """
    Validate or convert a creator identifier to a proper IAM ID.

    This function checks if the provided creator ID is valid. If not, it attempts to find
    a matching user by username, email, name, or display name. If no match is found,
    it returns the current user's IAM ID.

    Args:
        creator_id (str): User identifier - could be IAM ID, username, email, or display name.

    Returns:
        str: A valid IAM ID for the specified user or the current user.
    """

    # Check if the passed creator id is valid
    params = {
        "q":f'iam_id:{creator_id}',
        "limit":10,
        "skip":0,
        "include":FIELD_PREFERENCES
    }

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + USER_PROFILES_BASE_ENDPOINT,
        params=params
    )

    if response.get('total_results', []) > 0:
        return creator_id

    # Find closest user according to the user search
    params = {
        "q":f'user_name:{creator_id}*|email:{creator_id}*|name:{creator_id}*|display_name:{creator_id}*',
        "limit":10,
        "skip":0,
        "include":FIELD_PREFERENCES
    }

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + USER_PROFILES_BASE_ENDPOINT,
        params=params
    )

    if response.get('total_results', []) > 0:
        return response['resources'][0]['entity']['iam_id']

    # Assume the user wants to see use their identifier(uid, iam_id) and could have supplied natural language such as: me, mine
    return await get_user_identifier()

async def get_user_info_from_iam_id(iam_id: str, info_type: Literal["name", "email"]) -> str:
    """
    Retrieves information about user using their IAM ID.

    This function checks the type of information being looked for
    (name or email) and returns the corresponding user information.

    Args:
        iam_id (str): IAM ID of the user.

    Returns:
        str: Name or email of the user.
    """
    if iam_id:
        params = {
            "q":f'iam_id:{iam_id}',
            "limit":1,
            "skip":0,
            "include":FIELD_PREFERENCES
        }

        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.base_url) + USER_PROFILES_BASE_ENDPOINT,
            params=params
        )

        if response.get('total_results', []) > 0:
            if info_type == "name":
                return response['resources'][0]['entity']['display_name']
            else:
                return response['resources'][0]['entity']['email']
        else:
            raise ServiceError(
                f"Couldn't find any user with IAM ID '{iam_id}'"
            )
    else:
        raise ServiceError(
            "Empty IAM ID supplied to retrieve user information"
        )
