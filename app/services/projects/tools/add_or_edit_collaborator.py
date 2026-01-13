# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.projects.models.add_or_edit_collaborator import (
    AddOrEditCollaboratorRequest,
    AddOrEditCollaboratorResponse,
    CollaboratorMember,
)
from app.core.auth import get_bss_account_id, get_cloud_iam_url_from_service_url
from app.shared.utils.helpers import is_uuid, get_exact_or_fuzzy_matches
from app.shared.exceptions.base import ServiceError, ExternalAPIError
from app.services.tool_utils import is_project_exist_by_name, is_project_exist_by_id
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service , create_default_headers
from typing import List, Dict, Set, Sequence, Optional, Literal, cast
from app.core.settings import settings
from app.services.constants import JSON_CONTENT_TYPE

def create_collaborator_members(users: List[Dict]) -> List[CollaboratorMember]:
    """
    Helper function to create CollaboratorMember objects from user dictionaries.
    
    Args:
        users: List of user dictionaries containing user_info, role, and type
        
    Returns:
        List of CollaboratorMember objects
    """
    return [
        CollaboratorMember(
            user_name=(
                user["user_info"]["name"]
                if user["type"] == "user"
                else user["user_info"]["id"]
            ),
            id=user["user_info"]["id"],
            role=user["role"],
            state=user["user_info"]["state"],
            type=user["type"],
        )
        for user in users
    ]


@service_registry.tool(
    name="add_or_edit_collaborator",
    description="Add or update one or more collaborators (users or groups) in a project with specified roles. "
    "Intelligently searches for users or access groups using fuzzy matching on names and emails. "
    "For new members: Adds them to the project with the specified role. "
    "For existing members: Updates their role to the new specified role. "
    "Automatically detects whether members are new or existing and handles them appropriately. "
    "Supports role assignment (admin, editor, viewer) with 'viewer' as the default role. "
    "Supports mixed user and group types - specify type for each collaborator or omit to default to 'user' for all.",
)
@auto_context
async def add_or_edit_collaborator(request: AddOrEditCollaboratorRequest) -> AddOrEditCollaboratorResponse:
    """
    Add or update collaborators in a project with intelligent user/group search and validation.
    
    This function performs comprehensive validation including project existence verification,
    member detection, and fuzzy matching for user/group identification. It automatically
    determines whether to add new members or update existing ones based on their current
    membership status.
    
    Args:
        request: AddOrEditCollaboratorRequest containing:
            - project_identifier: Project name or UUID
            - user_names: List of user/group names or emails to add or update
            - role: List of roles to assign (admin, editor, viewer)
            - type: List of member types ('user' or 'group'), one for each user_name. Optional, defaults to 'user' for all.
        
    Returns:
        AddOrEditCollaboratorResponse containing:
            - project_id: The validated project UUID
            - added_members: List of successfully added/updated collaborators
            - message: Detailed success message with member summary
        
    Raises:
        ValueError: When project doesn't exist or API operations fail
        ServiceError: When multiple matches are found requiring user clarification
    """
    # Validate and get project ID
    project_id = await validate_and_get_project_id(request.project_identifier)

    # Get account ID for user search
    account_id = await get_bss_account_id()

    # Get existing members to determine add vs update (use set for O(1) lookup)
    existing_members, existing_member_ids = await get_existing_members_data(project_id)

    # Search and validate users/groups
    # Type should never be None at this point due to model validator, but we handle it for safety
    member_types = request.type if request.type is not None else ["user"] * len(request.user_names)
    users_to_add, users_to_update = await search_and_validate_members(
        request.user_names,
        request.role,
        member_types,
        account_id,
        existing_member_ids
    )

    if not users_to_add and not users_to_update:
        raise ValueError(
            "No valid users or groups found to add or update. "
            "Please verify the user list is correct."
        )

    # Validate that the project will have at least one admin after the operation
    await validate_admin_requirement(existing_members, users_to_add, users_to_update)

    # Prepare members for API calls using helper function to avoid duplication
    members_to_add = create_collaborator_members(users_to_add)
    members_to_update = create_collaborator_members(users_to_update)

    # Add new members to project via POST API
    if members_to_add:
        await add_members_to_project(project_id, members_to_add)

    # Update existing members via PATCH API
    if members_to_update:
        await update_members_in_project(project_id, members_to_update)

    # Combine all processed members for response
    all_members = members_to_add + members_to_update

    # Prepare response without sensitive ID information
    response_members = [
        CollaboratorMember(
            user_name=member.user_name,
            role=member.role,
            state=member.state,
            type=member.type,
        )
        for member in all_members
    ]

    # Create detailed success message
    added_count = len(members_to_add)
    updated_count = len(members_to_update)
    
    message_parts = []
    if added_count > 0:
        added_summary = ", ".join([f"{m.user_name} ({m.role})" for m in members_to_add])
        added_word = "collaborator" if added_count == 1 else "collaborators"
        message_parts.append(f"Added {added_count} {added_word}: {added_summary}")
    
    if updated_count > 0:
        updated_summary = ", ".join([f"{m.user_name} ({m.role})" for m in members_to_update])
        updated_word = "collaborator" if updated_count == 1 else "collaborators"
        message_parts.append(f"Updated {updated_count} {updated_word}: {updated_summary}")
    
    message = f"✓ Successfully processed collaborators. {'. '.join(message_parts)}."

    LOGGER.info(message)

    return AddOrEditCollaboratorResponse(
        project_id=project_id,
        added_members=response_members,
        message=message,
    )

async def validate_and_get_project_id(project_identifier: str) -> str:
    """
    Validate that the specified project exists and retrieve its UUID.
    
    Accepts either a project UUID or project name. When a name is provided,
    performs a lookup to find the corresponding project ID.
    
    Args:
        project_identifier: Either a project UUID or project name
        
    Returns:
        str: The validated project UUID
        
    Raises:
        ValueError: When the project cannot be found by ID or name
    """
    try:
        # Check if it's a UUID
        is_uuid(project_identifier)
        if not await is_project_exist_by_id(project_identifier):
            raise ValueError(
                f"Project with ID '{project_identifier}' does not exist. "
                f"Please verify the project ID is correct and you have access to it."
            )
        return project_identifier
    except ServiceError:
        # Not a UUID, try as project name
        is_exist, _ , project_id = await is_project_exist_by_name(project_identifier)
        if is_exist:
            return project_id
        else:
            raise ValueError(
                f"Project '{project_identifier}' could not be found. "
                f"Please verify the project name is spelled correctly and you have access to it."
            )

async def get_existing_members_data(project_id: str) -> tuple[List[Dict], Set[str]]:
    """
    Retrieve all existing members from a project with their roles and IDs.
    
    Returns both the full member list and a set of member IDs for efficient operations.
    The ID set uses O(1) lookup performance for duplicate detection.
    
    Args:
        project_id: The UUID of the project to query
        
    Returns:
        tuple[List[Dict], Set[str]]: A tuple containing:
            - List of all existing members with their details
            - Set of all existing member IDs for O(1) lookup
        
    Raises:
        ValueError: When unable to retrieve project members due to API failure or permission issues
    """
    url = f"{tool_helper_service.base_url}/v2/projects/{project_id}/members"
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=url, tool_name="add_or_edit_collaborator"
        )
        members = response.get("members", [])
        member_ids = {member["id"] for member in members}
        return members, member_ids
    except ExternalAPIError as e:
        LOGGER.error(f"Unable to retrieve project members: {str(e)}")
        raise ValueError(
            f"Could not retrieve the member list for project '{project_id}'. "
            f"Please ensure you have the necessary permissions to view project members."
        )


async def validate_admin_requirement(
    existing_members: List[Dict],
    users_to_add: List[Dict],
    users_to_update: List[Dict]
) -> None:
    """
    Validate that the project will have at least one admin user after the operation.
    
    This function checks:
    1. Current admin users in the project
    2. Whether any existing admins are being changed to non-admin roles
    3. Whether any new admins are being added
    4. Ensures at least one admin remains after the operation
    
    Args:
        existing_members: List of current project members with their roles
        users_to_add: List of new users being added
        users_to_update: List of existing users being updated
        
    Raises:
        ValueError: When the operation would result in a project with no admin users
    """
    
    # Get current admin member IDs
    current_admin_ids = {
        member["id"] for member in existing_members
        if member.get("role") == "admin"
    }
    
    # Check if any existing admins are being updated to non-admin roles
    admins_being_demoted = {
        user["user_info"]["id"] for user in users_to_update
        if user["user_info"]["id"] in current_admin_ids and user["role"] != "admin"
    }
    
    # Calculate remaining admins after updates
    remaining_admin_ids = current_admin_ids - admins_being_demoted
    
    # Check if any new admins are being added
    new_admin_ids = {
        user["user_info"]["id"] for user in users_to_add
        if user["role"] == "admin"
    }
    
    # Also check if any existing non-admins are being promoted to admin
    promoted_to_admin_ids = {
        user["user_info"]["id"] for user in users_to_update
        if user["user_info"]["id"] not in current_admin_ids and user["role"] == "admin"
    }
    
    # Calculate total admins after the operation
    total_admins_after = len(remaining_admin_ids) + len(new_admin_ids) + len(promoted_to_admin_ids)
    
    if total_admins_after == 0:
        raise ValueError(
            "Cannot complete this operation: The project must have at least one admin user. "
            "This operation would result in a project with no admin users. "
            "Please ensure at least one user has the 'admin' role."
        )
    
    LOGGER.info(f"Admin validation passed: Project will have {total_admins_after} admin(s) after operation")

async def search_and_validate_members(
    user_names: List[str],
    roles: Sequence[str],
    member_types: Sequence[str],
    account_id: str,
    existing_member_ids: Set[str]
) -> tuple[List[Dict], List[Dict]]:
    """
    Search for users or groups using fuzzy matching and categorize them for add or update.
    
    Performs intelligent search across the account, handles multiple match scenarios,
    and separates users into those to be added (new) and those to be updated (existing).
    
    Args:
        user_names: List of user or group names/emails to search for
        roles: List of roles to assign, corresponding to each user_name
        member_types: List of member types ('user' or 'group'), corresponding to each user_name
        account_id: The BSS account ID to search within
        existing_member_ids: Set of member IDs already in the project
        
    Returns:
        tuple[List[Dict], List[Dict]]: Two lists:
            - users_to_add: List of new members to add
            - users_to_update: List of existing members to update
            Each containing:
                - user_info: Dictionary with name, id, and state
                - role: The role to assign to this member
                - type: The member type ('user' or 'group')
        
    Raises:
        ServiceError: When multiple matches are found requiring user clarification, or when search fails
    """
    users_to_add = []
    users_to_update = []
    
    for index, user_name in enumerate(user_names):
        member_type = member_types[index]
        entity_type = "group" if member_type == "group" else "user"
        
        # Use unified search function
        search_results = await search_members(account_id, user_name, member_type)
        
        # Handle multiple matches
        if len(search_results) > 1:
            result_list = "\n".join(
                [f"- {result['name']}" for result in search_results]
            )
            raise ServiceError(
                f"Multiple {entity_type}s match the search term '{user_name}':\n{result_list}\n\n"
                f"Please provide a more specific {entity_type} name or use the exact ID to avoid ambiguity."
            )
        
        if not search_results:
            raise ServiceError(
                f"No {entity_type} found matching '{user_name}'. "
                f"Please verify the {entity_type} name or email is correct and exists in this account."
            )
        
        # Check if already a member - if yes, add to update list; if no, add to add list
        user_dict = {
            "user_info": search_results[0],
            "role": roles[index],
            "type": member_type
        }
        
        if search_results[0]["id"] in existing_member_ids:
            users_to_update.append(user_dict)
            LOGGER.info(f"'{user_name}' is an existing collaborator - will update role to '{roles[index]}'")
        else:
            users_to_add.append(user_dict)
            LOGGER.info(f"'{user_name}' is a new collaborator - will add with role '{roles[index]}'")
    
    return users_to_add, users_to_update


async def add_members_to_project(
    project_id: str, members: List[CollaboratorMember]
) -> dict:
    """
    Add validated members to a project through the Data Intelligence API.
    
    Sends a batch request to add all specified members with their assigned roles.
    
    Args:
        project_id: The UUID of the project to add members to
        members: List of CollaboratorMember objects containing user details and roles
        
    Returns:
        dict: The API response containing confirmation of added members
        
    Raises:
        ValueError: When the API call fails due to permission issues or invalid data
    """
    url = f"{tool_helper_service.base_url}/v2/projects/{project_id}/members"
    
    # Prepare payload
    payload = {"members": [member.model_dump() for member in members]}
    
    member_word = "member" if len(members) == 1 else "members"
    LOGGER.info(f"Adding {len(members)} {member_word} to project {project_id}")
    
    try:
        response = await tool_helper_service.execute_post_request(
            url=url, json=payload, tool_name="add_or_edit_collaborator"
        )
        return response
    except ExternalAPIError as e:
        LOGGER.error(f"API error while adding members to project: {str(e)}")
        raise ValueError(
            f"Unable to add collaborators to project '{project_id}'. "
            f"Please ensure you have admin or editor permissions for this project."
        )


async def update_members_in_project(
    project_id: str, members: List[CollaboratorMember]
) -> dict:
    """
    Update existing members' roles in a project through the Data Intelligence API.
    
    Sends a PATCH request to update all specified members with their new roles.
    Note: The 'type' field is excluded from the payload as it's not required for updates.
    
    Args:
        project_id: The UUID of the project to update members in
        members: List of CollaboratorMember objects containing user details and new roles
        
    Returns:
        dict: The API response containing confirmation of updated members
        
    Raises:
        ValueError: When the API call fails due to permission issues or invalid data
    """
    url = f"{tool_helper_service.base_url}/v2/projects/{project_id}/members"

    # Prepare payload - exclude 'type' field as it's not needed for updates
    payload = {"members": [member.model_dump(exclude={"state", "type"}) for member in members]}

    member_word = "member" if len(members) == 1 else "members"
    LOGGER.info(f"Updating {len(members)} {member_word} in project {project_id}")

    try:
        headers = create_default_headers(content_type=JSON_CONTENT_TYPE)
        response = await tool_helper_service.execute_patch_request(
            url=url, headers=headers, json=payload, tool_name="add_or_edit_collaborator"
        )
        return response
    except ExternalAPIError as e:
        LOGGER.error(f"API error while updating members in project: {str(e)}")
        raise ValueError(
            f"Unable to update collaborators in project '{project_id}'. "
            f"Please ensure you have admin permissions for this project."
        )


def extract_candidates(raw_data: List[Dict], member_type: str, is_cpd: bool) -> List[Dict]:
    """
    Extract and normalize candidate data based on environment and member type.
    
    Args:
        raw_data: Raw data from API response
        member_type: Type of member ('user' or 'group')
        is_cpd: Whether running in CP4D environment
        
    Returns:
        List of normalized candidate dictionaries with name, id, and state
    """
    if is_cpd:
        if member_type == "group":
            # CP4D group structure: {name, group_id, description, ...}
            return [
                {
                    "name": item.get("name", ""),
                    "id": str(item.get("group_id", "")),
                    "state": "ACTIVE",
                }
                for item in raw_data
                if isinstance(item, dict) and item.get("name") and item.get("group_id")
            ]
        else:
            # CP4D user structure: {uid, username, displayName, email, ...}
            return [
                {
                    "name": item.get("username", item.get("displayName", "")),
                    "id": item.get("uid", ""),
                    "state": "ACTIVE",
                }
                for item in raw_data
                if isinstance(item, dict) and item.get("username") and item.get("uid")
            ]
    else:
        # SaaS data structure
        if member_type == "group":
            return [
                {
                    "name": item.get("name", ""),
                    "id": item.get("id", ""),
                    "state": "ACTIVE",
                }
                for item in raw_data
                if isinstance(item, dict) and item.get("name") and item.get("id")
            ]
        else:
            return [
                {
                    "name": item.get("user_id", item.get("email", "")),
                    "id": item.get("iam_id", item.get("user_id", "")),
                    "state": item.get("state", "ACTIVE"),
                }
                for item in raw_data
                if isinstance(item, dict) and (item.get("user_id") or item.get("email")) and (item.get("id") or item.get("user_id"))
            ]

def get_search_config(member_type: str, is_cpd: bool, account_id: str) -> tuple[str, Optional[str], List[str]]:
    """
    Get API configuration for member search based on environment and member type.
    
    Args:
        member_type: Type of member ('user' or 'group')
        is_cpd: Whether running in CP4D environment
        account_id: The BSS account ID (for SaaS only)
        
    Returns:
        tuple[str, Optional[str], List[str]]: URL, response_key, and search_fields
        
    Raises:
        ValueError: When di_service_url is not configured
    """
    if is_cpd:
        if not settings.di_service_url:
            raise ValueError(
                "DI_SERVICE_URL is not configured. "
                "Please set the DI_SERVICE_URL environment variable to your CP4D instance URL."
            )
        if member_type == "group":
            return (
                f"{settings.di_service_url}/usermgmt/v2/groups",
                "results",
                ["name"]
            )
        return (
            f"{settings.di_service_url}/usermgmt/v1/usermgmt/users",
            None,
            ["name", "id"]
        )
    
    if member_type == "group":
        if not settings.di_service_url:
            raise ValueError(
                "DI_SERVICE_URL is not configured. "
                "Please set the DI_SERVICE_URL environment variable to your Data Intelligence service URL."
            )
        return (
            f"{get_cloud_iam_url_from_service_url(str(settings.di_service_url))}/v2/groups?account_id={account_id}",
            "groups",
            ["name"]
        )
    return (
        f"{tool_helper_service.user_management_url}/v2/accounts/{account_id}/users",
        "resources",
        ["name", "id"]
    )


async def search_members(
    account_id: str,
    search_str: str,
    member_type: str = "user"
) -> List[Dict]:
    """
    Unified intelligent search for users and access groups with fuzzy matching capabilities.
    
    Searches across the specified account using fuzzy matching algorithms to find
    users by name/email or groups by name. Returns up to 10 best matches.
    Supports both SaaS and CP4D environments with appropriate API endpoints.
    
    Args:
        account_id: The BSS account ID to search within (for SaaS) or ignored for CP4D
        search_str: Search term (user name, email, or group name)
        member_type: Type of member to search for ('user' or 'group')
        
    Returns:
        List[Dict]: List of matching members, each containing:
            - name: The user's email/ID or group name
            - id: The unique identifier
            - state: The member's state (e.g., 'ACTIVE')
        
    Raises:
        ValueError: When API call fails, permission is denied, or invalid member_type is provided
    """
    if member_type not in ("user", "group"):
        raise ValueError(
            f"Invalid member_type '{member_type}' specified. "
            f"Must be either 'user' or 'group'."
        )
    
    entity_type = "access group" if member_type == "group" else "user"
    LOGGER.info(f"Searching for {entity_type}: '{search_str}'")
    
    # Get configuration based on environment and member type
    is_cpd = settings.di_env_mode.upper() == "CPD"
    url, response_key, search_fields = get_search_config(member_type, is_cpd, account_id)
    
    # Fetch data from API
    try:
        response = await tool_helper_service.execute_get_request(
            url=url, tool_name="add_or_edit_collaborator"
        )
    except ExternalAPIError as e:
        LOGGER.error(f"API error while fetching {entity_type}s from account: {str(e)}")
        raise ValueError(
            f"Unable to search for {entity_type}s in this account. "
            f"Please verify you have the necessary permissions to list {entity_type}s."
        )
    
    # Extract raw data based on response structure
    if response_key:
        raw_data = response.get(response_key, [])
    elif isinstance(response, list):
        raw_data = response
    else:
        raw_data = []
    
    if not raw_data:
        LOGGER.warning(f"No {entity_type}s available in account {account_id}")
        return []
    
    # Prepare data for fuzzy matching based on member type and environment
    candidates = extract_candidates(raw_data, member_type, is_cpd)
    
    # Perform exact match first, then fuzzy match if needed
    matched_results = get_exact_or_fuzzy_matches(
        search_word=search_str,
        candidates=candidates,
        search_fields=search_fields,
        max_results=10,
        cutoff=0.6
    )
    
    entity_word = entity_type if len(matched_results) == 1 else f"{entity_type}s"
    LOGGER.info(f"Found {len(matched_results)} matching {entity_word} for search term '{search_str}'")
    return matched_results


# Backward compatibility wrappers
async def search_group(account_id: str, group_search_str: str) -> List[Dict]:
    """
    Search for access groups in the account (backward compatibility wrapper).
    
    This function maintains backward compatibility with existing code while
    delegating to the unified search_members function.
    
    Args:
        account_id: The BSS account ID to search within
        group_search_str: Search term for access group name
        
    Returns:
        List[Dict]: List of matching access groups with name, id, and state
    """
    return await search_members(account_id, group_search_str, member_type="group")


async def search_users(account_id: str, user_search_str: str) -> List[Dict]:
    """
    Search for users in the account (backward compatibility wrapper).
    
    This function maintains backward compatibility with existing code while
    delegating to the unified search_members function.
    
    Args:
        account_id: The BSS account ID to search within
        user_search_str: Search term for user name or email
        
    Returns:
        List[Dict]: List of matching users with name, id, and state
    """
    return await search_members(account_id, user_search_str, member_type="user")


@service_registry.tool(
    name="add_or_edit_collaborator",
    description="Add or update one or more collaborators (users or groups) in a project with specified roles. "
    "Intelligently searches for users or access groups using fuzzy matching on names and emails. "
    "For new members: Adds them to the project with the specified role. "
    "For existing members: Updates their role to the new specified role. "
    "Automatically detects whether members are new or existing and handles them appropriately. "
    "Supports role assignment (admin, editor, viewer) with 'viewer' as the default role. "
    "Supports mixed user and group types - specify type for each collaborator or omit to default to 'user' for all. "
    "(Watsonx Orchestrator compatible)",
)
@auto_context
async def wxo_add_or_edit_collaborator(
    project_identifier: str,
    user_names: List[str],
    role: Optional[List[str]] = None,
    type: Optional[List[str]] = None,
) -> AddOrEditCollaboratorResponse:
    """Watsonx Orchestrator compatible version that expands AddOrEditCollaboratorRequest object into individual parameters."""
    
    # Cast role to proper type, defaulting to ["editor"] if None
    role_typed = cast(
        List[Literal["viewer", "editor", "admin"]],
        role if role is not None else ["viewer"]
    )
    
    # Cast type to proper type if provided
    type_typed = cast(
        Optional[List[Literal["user", "group"]]],
        type
    ) if type is not None else None
    
    request = AddOrEditCollaboratorRequest(
        project_identifier=project_identifier,
        user_names=user_names,
        role=role_typed,
        type=type_typed,
    )
    
    # Call the original add_or_edit_collaborator function
    return await add_or_edit_collaborator(request)
