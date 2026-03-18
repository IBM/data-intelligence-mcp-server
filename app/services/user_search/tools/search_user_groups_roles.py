# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Optional, Literal, Union, List
from app.core.registry import service_registry
from app.services.user_search.models.search_user_groups_roles import (
    UnifiedSearchRequest,
    UnifiedSearchResponse,
)
from app.services.user_search.models.search_users import UserSearchResult
from app.services.user_search.models.search_groups import GroupSearchResult
from app.services.user_search.models.search_roles import RoleSearchResult
from app.services.user_search.utils.search_utils import (
    search_users_by_query,
    search_groups_by_query,
    search_roles_by_query,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.core.settings import settings, ENV_MODE_SAAS
from app.shared.ui_message.ui_message_context import ui_message_context

TABLE_TITLE_SEARCH_USERS = "Search Users"
TABLE_TITLE_SEARCH_USER_GROUPS = "Search User Groups"
TABLE_TITLE_SEARCH_USER_ROLES = "Search User roles"

def format_artifacts_for_table(
    results: Union[List[UserSearchResult], List[GroupSearchResult], List[RoleSearchResult]]
) -> List[dict]:
    """
    Format search results by changing keys to Title Case for table display.
    
    Handles three types of results:
    - UserSearchResult: Formats user_id, username, display_name, email, state
    - GroupSearchResult: Formats group_id, group_name, description, state
    - RoleSearchResult: Formats role_key, role_name, description
    
    Args:
        results: List of search results (users, groups, or roles)
        
    Returns:
        List of dictionaries with Title Case keys for table display
    """
    if not results:
        return []
    
    # Determine result type by checking first item
    first_result = results[0]
    
    if isinstance(first_result, UserSearchResult):
        # Type narrowing for users
        user_results = [r for r in results if isinstance(r, UserSearchResult)]
        return [
            {
                "User ID": result.user_id,
                "Username": result.username,
                "Display Name": result.display_name or "",
                "Email": result.email or "",
                "State": result.state,
            }
            for result in user_results
        ]
    elif isinstance(first_result, GroupSearchResult):
        # Type narrowing for groups
        group_results = [r for r in results if isinstance(r, GroupSearchResult)]
        return [
            {
                "Group ID": result.group_id,
                "Group Name": result.group_name,
                "Description": result.description or "",
                "State": result.state,
            }
            for result in group_results
        ]
    elif isinstance(first_result, RoleSearchResult):
        # Type narrowing for roles
        role_results = [r for r in results if isinstance(r, RoleSearchResult)]
        return [
            {
                "Role Key": result.role_key,
                "Role Name": result.role_name,
                "Description": result.description or "",
            }
            for result in role_results
        ]
    else:
        # Fallback: return empty list if unknown type
        LOGGER.warning(f"Unknown result type: {type(first_result)}")
        return []


@service_registry.tool(
    name="search_user_groups_roles",
    description="""
    Unified tool to search and retrieve users, user groups, or user roles in watsonx.data intelligence.
    
    This tool enables AI agents to quickly find the right identity record by specifying the search type
    (user, group, or role) and an optional query. It uses intelligent fuzzy matching to find the best 
    matches and returns results with confidence scores and match metadata.
    
    Search Types:
    - "user": Search for individual users by name, email, username, or user ID
    - "group": Search for user groups by group name or group ID
    - "role": Search for user roles by role name (CP4D only)
    
    Features:
    - Intelligent fuzzy matching with confidence scores
    - List all items when no query is provided
    - Works in both SaaS and CP4D environments (roles search is CP4D only)
    - RBAC enforcement (only returns identities caller is permitted to see)
    
    Use Cases:
        Users:
        - "Find user jacob" → search_type="user", query="jacob"
        - "Search for user with email jacob@ibm.com" → search_type="user", query="jacob@ibm.com"
        - "List all users" → search_type="user", query=None
        
        Groups:
        - "Find group marketing" → search_type="group", query="marketing"
        - "Search for analysts group" → search_type="group", query="analysts"
        - "List all groups" → search_type="group", query=None
        
        Roles (CP4D only):
        - "Show me all user roles" → search_type="role", query=None
        - "Find administrator roles" → search_type="role", query="admin"
    
    Examples:
        - "Add Jacob to Project X" → search_type="user", query="jacob", then use user_id
        - "Give marketing analysts read access" → search_type="group", query="marketing", then use group_id
        - "Apply data protection rule to jacob@ibm.com" → search_type="user", query="jacob@ibm.com"
        - "What roles can I assign?" → search_type="role", query=None (CP4D only)
    """,
    tags={"search", "user_search", "identity", "access_management", "unified"},
    meta={"version": "1.0", "service": "user_search"},
)
@auto_context
async def _execute_search_by_type(request: UnifiedSearchRequest):
    """
    Execute search based on search_type and return results with metadata.
    
    Returns:
        Tuple of (results, total_count, entity_name, id_field)
    """
    if request.search_type == "user":
        results, total_count = await search_users_by_query(query=request.query)
        format_response = format_artifacts_for_table(results)
        ui_message_context.add_table_ui_message(tool_name="search_user_groups_roles",
                         formatted_data=format_response, title=TABLE_TITLE_SEARCH_USERS)
        return results, total_count, "user", "user_id"
    
    if request.search_type == "group":
        results, total_count = await search_groups_by_query(query=request.query)
        format_response = format_artifacts_for_table(results)
        ui_message_context.add_table_ui_message(tool_name="search_user_groups_roles",
                         formatted_data=format_response, title=TABLE_TITLE_SEARCH_USER_GROUPS)
        return results, total_count, "group", "group_id"
    
    if request.search_type == "role":
        # Check if CP4D mode for roles
        if settings.di_env_mode.upper() == ENV_MODE_SAAS:
            return None, 0, "role", "role_key"  # Signal SaaS mode
        results, total_count = await search_roles_by_query(query=request.query)
        format_response = format_artifacts_for_table(results)
        ui_message_context.add_table_ui_message(tool_name="search_user_groups_roles",
                         formatted_data=format_response, title=TABLE_TITLE_SEARCH_USER_ROLES)
        return results, total_count, "role", "role_key"
    
    raise ValueError(f"Invalid search_type: {request.search_type}. Must be 'user', 'group', or 'role'.")


def _build_empty_response(request: UnifiedSearchRequest, entity_name: str) -> UnifiedSearchResponse:
    """Build response for empty search results."""
    if request.query:
        LOGGER.info(f"No {entity_name}s found matching query '{request.query}'")
        message = f"No {entity_name}s found matching '{request.query}'. Please try a different search term or verify the {entity_name} exists in the system."
    else:
        LOGGER.info(f"No {entity_name}s found in the system")
        message = f"No {entity_name}s found in the system."
    
    return UnifiedSearchResponse(
        search_type=request.search_type,
        total_count=0,
        returned_count=0,
        results=[],
        message=message,
        query=request.query
    )


def _build_success_message(request: UnifiedSearchRequest, total_count: int, entity_name: str, id_field: str) -> str:
    """Build success message based on search mode."""
    if request.query:
        return (
            f"Found {total_count} {entity_name}(s) matching '{request.query}'. "
            f"Use the {id_field} field for downstream operations like access grants or governance controls."
        )
    return (
        f"Listed all {total_count} {entity_name}(s) in the system. "
        f"Use the {id_field} field for downstream operations like access grants or governance controls."
    )


async def search_user_groups_roles(
    request: UnifiedSearchRequest,
) -> UnifiedSearchResponse:
    """
    Unified search for users, groups, or roles by partial identifier with fuzzy matching.
    
    Args:
        request: UnifiedSearchRequest containing:
            - search_type: Type of identity to search ("user", "group", or "role")
            - query: Optional search term. If None, lists all items of the specified type.
    
    Returns:
        UnifiedSearchResponse containing:
            - search_type: Type of identity that was searched
            - total_count: Total number of matching items
            - returned_count: Number of items in this response
            - results: List of matching results (UserSearchResult, GroupSearchResult, or RoleSearchResult)
            - message: Human-readable status message
            - query: Original search query
    
    Raises:
        ExternalAPIError: When API call fails or permission is denied
        ServiceError: When unexpected error occurs during search
        ValueError: When search_type="role" is used in SaaS environment
    """
    query_display = f"query='{request.query}'" if request.query else f"list all {request.search_type}s"
    LOGGER.info(f"Unified search: search_type='{request.search_type}', {query_display}")
    
    try:
        # Execute search based on type
        results, total_count, entity_name, id_field = await _execute_search_by_type(request)
        
        # Handle SaaS mode for roles
        if results is None and request.search_type == "role":
            return UnifiedSearchResponse(
                search_type="role",
                total_count=0,
                returned_count=0,
                results=[],
                message="Search for user roles is only supported in CP4D mode.",
                query=request.query
            )
        
        # Handle empty results
        if not results:
            return _build_empty_response(request, entity_name)
        
        # Build success response
        returned_count = len(results)
        message = _build_success_message(request, total_count, entity_name, id_field)
        
        LOGGER.info(f"Successfully found {total_count} {entity_name}s, returning {returned_count} results")
        
        return UnifiedSearchResponse(
            search_type=request.search_type,
            total_count=total_count,
            returned_count=returned_count,
            results=results,
            message=message,
            query=request.query
        )
    
    except ValueError as e:
        LOGGER.error(f"Validation error during unified search: {str(e)}")
        raise ValueError(str(e))
    except ExternalAPIError as e:
        LOGGER.error(f"External API error during unified search: {str(e)}")
        raise ExternalAPIError(
            f"Failed to search {request.search_type}s due to API error: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(f"Unexpected error during unified search: {str(e)}")
        raise ServiceError(
            f"Failed to search {request.search_type}s due to unexpected error: {str(e)}"
        )


@service_registry.tool(
    name="search_user_groups_roles",
    description="""
    Unified tool to search and retrieve users, user groups, or user roles in watsonx.data intelligence.
    (Watsonx Orchestrator compatible version)
    
    This tool enables AI agents to quickly find the right identity record by specifying the search type
    (user, group, or role) and an optional query. It uses intelligent fuzzy matching to find the best 
    matches and returns results with confidence scores and match metadata.
    
    Search Types:
    - "user": Search for individual users by name, email, username, or user ID
    - "group": Search for user groups by group name or group ID
    - "role": Search for user roles by role name (CP4D only)
    """,
    tags={"search", "user_search", "identity", "access_management", "unified"},
    meta={"version": "1.0", "service": "user_search"},
)
@auto_context
async def wxo_search_user_groups_roles(
    search_type: Literal["user", "group", "role"],
    query: Optional[str] = None
) -> UnifiedSearchResponse:
    """
    Watsonx Orchestrator compatible version that expands UnifiedSearchRequest into individual parameters.
    
    Args:
        search_type: Type of identity to search ("user", "group", or "role")
        query: Optional search term. If None, lists all items of the specified type.
    
    Returns:
        UnifiedSearchResponse with matching results and metadata
    """
    request = UnifiedSearchRequest(
        search_type=search_type,
        query=query
    )
    
    return await search_user_groups_roles(request)


# Made with Bob