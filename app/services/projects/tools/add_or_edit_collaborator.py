# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.projects.models.add_or_edit_collaborator import (
    AddOrEditCollaboratorRequest,
    AddOrEditCollaboratorResponse,
    CollaboratorMember,
)
from app.core.auth import get_bss_account_id
from app.shared.utils.helpers import is_uuid_bool, get_exact_or_fuzzy_matches
from app.shared.exceptions.base import ServiceError, ValidationError
from app.services.tool_utils import (
    is_project_exist_by_name,
    is_project_exist_by_id,
    is_catalog_exist_by_name,
    is_catalog_exist_by_id,
    build_container_members_url
)
from app.services.constants import CATALOGS_BASE_ENDPOINT, PROJECTS_BASE_ENDPOINT
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service , create_default_headers
from typing import Annotated, List, Dict, Set, Sequence, Optional, Literal, cast
from pydantic import Field
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


async def _add_or_edit_collaborator(request: AddOrEditCollaboratorRequest) -> AddOrEditCollaboratorResponse:
    """
    Add or update collaborators in a project or catalog with intelligent user/group search and validation.
    
    This function performs comprehensive validation including container existence verification,
    member detection, and fuzzy matching for user/group identification. It automatically
    determines whether to add new members or update existing ones based on their current
    membership status.
    
    Args:
        request: AddOrEditCollaboratorRequest containing:
            - container_identifier: Project or catalog name or UUID
            - container_type: Type of container ('project' or 'catalog')
            - user_names: List of user/group names or emails to add or update
            - role: List of roles to assign (admin, editor, viewer)
            - type: List of member types ('user' or 'group'), one for each user_name. Optional, defaults to 'user' for all.
        
    Returns:
        AddOrEditCollaboratorResponse containing:
            - container_id: The validated container UUID
            - container_type: The type of container
            - added_members: List of successfully added/updated collaborators
            - message: Detailed success message with member summary
        
    Raises:
        ValidationError: When container doesn't exist or API operations fail
        ServiceError: When multiple matches are found requiring user clarification
    """
    # Validate and get container ID
    container_id = await validate_and_get_container_id(
        request.container_identifier,
        request.container_type
    )

    # Get account ID for user search
    account_id = await get_bss_account_id()

    # Get existing members to determine add vs update (use set for O(1) lookup)
    existing_members, existing_member_ids = await get_existing_members_data(
        container_id,
        request.container_type
    )

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
        raise ValidationError(
            "No valid users or groups found to add or update. "
            "Please verify the user list is correct.",
            remediation_steps="Call the search_user_groups_roles tool with search_type set to 'user' or 'group' to retrieve the list of users or groups. Then provide a user or group from the returned list.",
            tool="add_or_edit_collaborator"
        )

    # Validate that the container will have at least one admin after the operation
    validate_admin_requirement(existing_members, users_to_add, users_to_update)

    # Prepare members for API calls using helper function to avoid duplication
    members_to_add = create_collaborator_members(users_to_add)
    members_to_update = create_collaborator_members(users_to_update)

    # Add new members to container via POST API
    if members_to_add:
        await add_members_to_container(container_id, members_to_add, request.container_type)

    # Update existing members via PATCH API
    if members_to_update:
        await update_members_in_container(container_id, members_to_update, request.container_type)

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
    container_name = request.container_type
    
    message_parts = []
    if added_count > 0:
        added_summary = ", ".join([f"{m.user_name} ({m.role})" for m in members_to_add])
        added_word = "collaborator" if added_count == 1 else "collaborators"
        message_parts.append(f"Added {added_count} {added_word}: {added_summary}")
    
    if updated_count > 0:
        updated_summary = ", ".join([f"{m.user_name} ({m.role})" for m in members_to_update])
        updated_word = "collaborator" if updated_count == 1 else "collaborators"
        message_parts.append(f"Updated {updated_count} {updated_word}: {updated_summary}")
    
    message = f"✓ Successfully processed collaborators in {container_name}. {'. '.join(message_parts)}."

    LOGGER.info(message)

    return AddOrEditCollaboratorResponse(
        container_id=container_id,
        container_type=request.container_type,
        added_members=response_members,
        message=message,
    )


async def _validate_container_by_id(container_id: str, container_type: str) -> None:
    """
    Validate that a container exists by its UUID.
    
    Args:
        container_id: Container UUID to validate
        container_type: Type of container ('project' or 'catalog')
        
    Raises:
        ValidationError: When the container does not exist
    """
    if container_type == "project":
        if not await is_project_exist_by_id(container_id):
            raise ValidationError(
                f"Project with ID '{container_id}' does not exist. "
                f"Please verify the project ID is correct and you have access to it.",
                remediation_steps="Call the list_containers tool with container_type set to 'project' to retrieve the list of available projects. Then provide a project ID from the list.",
                tool="add_or_edit_collaborator"
            )
    else:  # catalog
        if not await is_catalog_exist_by_id(container_id):
            raise ValidationError(
                f"Catalog with ID '{container_id}' does not exist. "
                f"Please verify the catalog ID is correct and you have access to it.",
                remediation_steps="Call the list_containers tool with container_type set to 'catalog' to retrieve the list of available catalogs. Then provide a catalogs ID from the list.",
                tool="add_or_edit_collaborator"
            )


async def _find_container_by_name(container_identifier: str, container_type: str) -> str:
    """
    Find a container by its name and return its UUID.
    
    Args:
        container_identifier: Container name
        container_type: Type of container ('project' or 'catalog')
        
    Returns:
        str: The container UUID
        
    Raises:
        ValidationError: When the container cannot be found
    """
    if container_type == "project":
        is_exist, _, container_id = await is_project_exist_by_name(container_identifier)
        if is_exist:
            return container_id
        raise ValidationError(
            f"Project '{container_identifier}' could not be found. "
            f"Please verify the project name is spelled correctly and you have access to it.",
            remediation_steps="Call the list_containers tool with container_type set to 'project' to retrieve the list of available projects. Then provide a project name from the list.",
            tool="add_or_edit_collaborator"
        )
    else:  # catalog
        is_exist, _, container_id = await is_catalog_exist_by_name(container_identifier)
        if is_exist:
            return container_id
        raise ValidationError(
            f"Catalog '{container_identifier}' could not be found. "
            f"Please verify the catalog name is spelled correctly and you have access to it.",
            remediation_steps="Call the list_containers tool with container_type set to 'catalog' to retrieve the list of available catalogs. Then provide a catalog name from the list.",
            tool="add_or_edit_collaborator"
        )


async def validate_and_get_container_id(container_identifier: str, container_type: str) -> str:
    """
    Validate that the specified container (project or catalog) exists and retrieve its UUID.
    
    Accepts either a container UUID or container name. When a name is provided,
    performs a lookup to find the corresponding container ID.
    
    Args:
        container_identifier: Either a container UUID or container name
        container_type: Type of container ('project' or 'catalog')
        
    Returns:
        str: The validated container UUID
        
    Raises:
        ValidationError: When the container cannot be found by ID or name
    """
    # Check if it's a UUID
    if is_uuid_bool(container_identifier):
        await _validate_container_by_id(container_identifier, container_type)
        return container_identifier
    
    # Not a UUID, treat as container name
    return await _find_container_by_name(container_identifier, container_type)


async def get_existing_members_data(container_id: str, container_type: str) -> tuple[List[Dict], Set[str]]:
    """
    Retrieve all existing members from a container (project or catalog) with their roles and IDs.
    
    Returns both the full member list and a set of member IDs for efficient operations.
    The ID set uses O(1) lookup performance for duplicate detection.
    
    Args:
        container_id: The UUID of the container to query
        container_type: Type of container ('project' or 'catalog')
        
    Returns:
        tuple[List[Dict], Set[str]]: A tuple containing:
            - List of all existing members with their details
            - Set of all existing member IDs for O(1) lookup
        
    Raises:
        ValidationError: When unable to retrieve container members due to API failure or permission issues
    """
    # Build URL based on container type
    url = build_container_members_url(container_id, container_type)
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=url, tool_name="add_or_edit_collaborator"
        )
        members = response.get("members", [])
        
        # For catalogs, use user_iam_id and access_group_id; for projects, use id
        if container_type == "catalog":
            member_ids = {
                member.get("user_iam_id") or member.get("access_group_id")
                for member in members
                if member.get("user_iam_id") or member.get("access_group_id")
            }
        else:
            member_ids = {member["id"] for member in members}
        
        return members, member_ids
    except Exception as e:
        LOGGER.error(f"Unable to retrieve {container_type} members: {str(e)}")
        raise ValidationError(
            f"Could not retrieve the member list for {container_type} '{container_id}'. "
            f"Please ensure you have the necessary permissions to view {container_type} members.",
            tool="add_or_edit_collaborator"
        )


def get_member_id(member: Dict) -> str:
    """
    Get the member ID from a member dict, handling both project and catalog formats.
    
    Projects use 'id' field, catalogs use 'user_iam_id' or 'access_group_id'.
    
    Args:
        member: Member dictionary from API response
        
    Returns:
        The member's ID
    """
    return member.get("id") or member.get("user_iam_id") or member.get("access_group_id", "")


def validate_admin_requirement(
    existing_members: List[Dict],
    users_to_add: List[Dict],
    users_to_update: List[Dict]
) -> None:
    """
    Validate that the container will have at least one admin user after the operation.
    
    This function checks:
    1. Current admin users in the container
    2. Whether any existing admins are being changed to non-admin roles
    3. Whether any new admins are being added
    4. Ensures at least one admin remains after the operation
    
    Args:
        existing_members: List of current container members with their roles
        users_to_add: List of new users being added
        users_to_update: List of existing users being updated
        
    Raises:
        ValidationError: When the operation would result in a container with no admin users
    """
    
    # Get current admin member IDs (works for both projects and catalogs)
    current_admin_ids = {
        get_member_id(member) for member in existing_members
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
        raise ValidationError(
            "Cannot complete this operation: The project or catalog must have at least one admin user. "
            "This operation would result in a project or catalog with no admin users. "
            "Please ensure at least one user has the 'admin' role.",
            remediation_steps="Call the search_user_groups_roles tool with search_type set to 'role' and query set to 'admin', then verify the user's role.",
            tool="add_or_edit_collaborator"
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
                f"Please provide a more specific {entity_type} name or use the exact ID to avoid ambiguity.",
                tool="add_or_edit_collaborator"
            )
        
        if not search_results:
            raise ServiceError(
                f"No {entity_type} found matching '{user_name}'. "
                f"Please verify the {entity_type} name or email is correct and exists in this account.",
                remediation_steps="Call the search_user_groups_roles tool with search_type set to 'user' to retrieve the list of users. Then provide a username and email from the list.",
                tool="add_or_edit_collaborator"
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


async def add_members_to_container(
    container_id: str, members: List[CollaboratorMember], container_type: str
) -> dict:
    """
    Add validated members to a container (project or catalog) through the Data Intelligence API.
    
    Sends a batch request to add all specified members with their assigned roles.
    
    Args:
        container_id: The UUID of the container to add members to
        members: List of CollaboratorMember objects containing user details and roles
        container_type: Type of container ('project' or 'catalog')
        
    Returns:
        dict: The API response containing confirmation of added members
        
    Raises:
        ValidationError: When the API call fails due to permission issues or invalid data
    """
    # Build URL based on container type
    url = build_container_members_url(container_id, container_type)
    
    # Prepare payload - for catalogs, map id to user_iam_id or access_group_id
    if container_type == "catalog":
        payload_members = []
        for member in members:
            member_dict = {}
            # Map 'id' to appropriate catalog field based on member type
            if member.type == "group":
                member_dict["access_group_id"] = member.id
            else:
                member_dict["user_iam_id"] = member.id
            # Add role field
            member_dict["role"] = member.role
            payload_members.append(member_dict)
        payload = {"members": payload_members}
    else:
        payload = {"members": [member.model_dump() for member in members]}
    
    member_word = "member" if len(members) == 1 else "members"
    LOGGER.info(f"Adding {len(members)} {member_word} to {container_type} {container_id}")
    
    try:
        response = await tool_helper_service.execute_post_request(
            url=url, json=payload, tool_name="add_or_edit_collaborator"
        )
        return response
    except Exception as e:
        LOGGER.error(f"API error while adding members to {container_type}: {str(e)}")
        raise ValidationError(
            f"Unable to add collaborators to {container_type} '{container_id}'. "
            f"Please ensure you have admin or editor permissions for this {container_type}.",
            remediation_steps="Call the search_user_groups_roles tool with search_type set to 'role', then verify the user's role 'admin' or 'editor'.",
            tool="add_or_edit_collaborator"
        )


async def update_members_in_container(
    container_id: str, members: List[CollaboratorMember], container_type: str
) -> dict:
    """
    Update existing members' roles in a container (project or catalog) through the Data Intelligence API.
    
    For projects: Sends a single PATCH request to update all specified members with their new roles.
    For catalogs: Sends individual PATCH requests per member to /v2/catalogs/{catalog_id}/members/{member_id}
    Note: The 'type' field is excluded from the payload as it's not required for updates.
    
    Args:
        container_id: The UUID of the container to update members in
        members: List of CollaboratorMember objects containing user details and new roles
        container_type: Type of container ('project' or 'catalog')
        
    Returns:
        dict: The API response containing confirmation of updated members
        
    Raises:
        ValidationError: When the API call fails due to permission issues or invalid data
    """
    member_word = "member" if len(members) == 1 else "members"
    LOGGER.info(f"Updating {len(members)} {member_word} in {container_type} {container_id}")

    try:
        headers = create_default_headers(content_type=JSON_CONTENT_TYPE)
        
        if container_type == "catalog":
            # For catalogs, update each member individually with member_id in URL
            responses = []
            for member in members:
                # Build URL with member_id in path
                url = build_container_members_url(container_id, container_type, member.id)
                # Payload only contains the role field
                payload = {"role": member.role}
                
                response = await tool_helper_service.execute_patch_request(
                    url=url, headers=headers, json=payload, tool_name="add_or_edit_collaborator"
                )
                responses.append(response)
            
            # Return combined response
            return {"members": responses, "updated_count": len(responses)}
        else:
            # For projects, use batch update
            url = build_container_members_url(container_id, container_type)
            payload = {"members": [member.model_dump(exclude={"state", "type"}) for member in members]}
            
            response = await tool_helper_service.execute_patch_request(
                url=url, headers=headers, json=payload, tool_name="add_or_edit_collaborator"
            )
            return response
            
    except Exception as e:
        LOGGER.error(f"API error while updating members in {container_type}: {str(e)}")
        raise ValidationError(
            f"Unable to update collaborators in {container_type} '{container_id}' for {str(e)}. "
            f"Please ensure you have admin permissions for this {container_type}.",
            remediation_steps="Call the search_user_groups_roles tool with search_type set to 'role' and query set to 'admin', then verify the user's role.",
            tool="add_or_edit_collaborator"
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
    Uses centralized search utilities from search_utils.py for consistency.
    
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
        ValidationError: When API call fails, permission is denied, or invalid member_type is provided
    """
    if member_type not in ("user", "group"):
        raise ValidationError(
            f"Invalid member_type '{member_type}' specified. "
            f"Must be either 'user' or 'group'.",
            tool="add_or_edit_collaborator"
        )
    
    entity_type = "access group" if member_type == "group" else "user"
    LOGGER.info(f"Searching for {entity_type}: '{search_str}'")
    
    # Import search utilities
    from app.services.user_search.utils.search_utils import (
        _fetch_cpd_users,
        _fetch_cpd_groups,
        _fetch_saas_users,
        _fetch_saas_groups,
    )
    
    # Get configuration based on environment and member type
    is_cpd = settings.di_env_mode.upper() == "CPD"
    
    # Fetch data using centralized search utilities
    try:
        if is_cpd:
            if member_type == "group":
                raw_data = await _fetch_cpd_groups()
            else:
                raw_data = await _fetch_cpd_users()
        else:
            if member_type == "group":
                raw_data = await _fetch_saas_groups()
            else:
                raw_data = await _fetch_saas_users()
    except Exception as e:
        LOGGER.error(f"API error while fetching {entity_type}s from account: {str(e)}")
        raise ValidationError(
            f"Unable to search for {entity_type}s in this account. "
            f"Please verify you have the necessary permissions to list {entity_type}s.",
            tool="add_or_edit_collaborator"
        )
    
    if not raw_data:
        LOGGER.warning(f"No {entity_type}s available in account {account_id}")
        return []
    
    # Prepare data for fuzzy matching based on member type and environment
    candidates = extract_candidates(raw_data, member_type, is_cpd)
    
    # Define search fields based on member type
    search_fields = ["name"] if member_type == "group" else ["name", "id"]
    
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
    description="Use this tool when you need to add or update one or more collaborators (users or groups) in a project or catalog with specified roles. "
    "Intelligently searches for users or access groups using fuzzy matching on names and emails. "
    "For new members: Adds them to the container with the specified role. "
    "For existing members: Updates their role to the new specified role. "
    "Automatically detects whether members are new or existing and handles them appropriately. "
    "Supports role assignment (admin, editor, viewer) with 'viewer' as the default role. "
    "Supports mixed user and group types - specify type for each collaborator or omit to default to 'user' for all. "
    "Works with both projects and catalogs - specify container_type as 'project' or 'catalog' (defaults to 'project'). "
    "Return: The container ID and type, a list of successfully added/updated collaborator members with their roles, and a success message.",
    annotations={
        "title": "Add or Update Collaborators in a Project with Specified Roles",
        "destructiveHint": True
    }
)
@auto_context
async def add_or_edit_collaborator(
    container_identifier: Annotated[str, Field(description="The project or catalog name or UUID")],
    user_names: Annotated[List[str], Field(description="The usernames or group names to add as collaborators. Must match the length of the role list.")],
    role: Annotated[Optional[List[str]], Field(description="Roles to assign to the collaborators. Must match the length of user_names list. Defaults to 'editor' for each user if not specified.")] = None,
    type: Annotated[Optional[List[str]], Field(description="The member types: 'user' for individual users or 'group' for access groups. Must match the length of user_names list. Defaults to list of 'user' for each member if not specified.")] = None,
    container_type: Annotated[Optional[str], Field(description="The type of container: 'project' or 'catalog'. Defaults to 'project'.")] = None,
) -> AddOrEditCollaboratorResponse:
    """Wrapper that expands AddOrEditCollaboratorRequest object into individual parameters."""
    
    # Cast role to proper type, defaulting to ["viewer"] if None
    role_typed = cast(
        List[Literal["viewer", "editor", "admin"]],
        role if role is not None else ["viewer"]
    )
    
    # Cast type to proper type if provided
    type_typed = cast(
        Optional[List[Literal["user", "group"]]],
        type
    ) if type is not None else None
    
    # Cast container_type to proper type, defaulting to "project" if None
    container_type_typed = cast(
        Literal["project", "catalog"],
        container_type if container_type is not None else "project"
    )
    
    request = AddOrEditCollaboratorRequest(
        container_identifier=container_identifier,
        user_names=user_names,
        role=role_typed,
        type=type_typed,
        container_type=container_type_typed,
    )
    
    # Call the original add_or_edit_collaborator function
    return await _add_or_edit_collaborator(request)
