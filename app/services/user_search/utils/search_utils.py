# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Dict, Tuple, Optional
from app.core.auth import get_bss_account_id, get_cloud_iam_url_from_service_url
from app.shared.utils.helpers import get_exact_or_fuzzy_matches
from app.shared.exceptions.base import ExternalAPIError
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.core.settings import settings
from app.services.user_search.models.search_users import UserSearchResult
from app.services.user_search.models.search_groups import GroupSearchResult
from app.services.user_search.models.search_roles import RoleSearchResult

FUZZY_MATCH_THRESHOLD = 0.7
MAX_RESULTS = 10000
PAGE_LIMIT = 100

async def search_users_by_query(
    query: Optional[str] = None
) -> Tuple[List[UserSearchResult], int]:
    """
    Search for users by partial identifier with fuzzy matching, or list all users.
    
    Searches across user names, emails, and usernames using intelligent fuzzy matching.
    If no query provided, returns all users in the system.
    Supports both SaaS and CP4D environments with appropriate API endpoints.
    For SaaS, implements proper server-side pagination to fetch all users.
    
    Args:
        query: Optional search term (user name, email, username, or user ID). If None, returns all users.
        
    Returns:
        Tuple[List[UserSearchResult], int]: List of matching users and total count
        
    Raises:
        ExternalAPIError: When API call fails or permission is denied
    """
    query_str = f"query='{query}'" if query else "list all users"
    LOGGER.info(f"Searching for users with {query_str}")
    
    # Get account ID for SaaS or use CP4D endpoint
    is_cpd = settings.di_env_mode.upper() == "CPD"
    
    if is_cpd:
        raw_users = await _fetch_cpd_users()
        candidates = _normalize_user_data(raw_users, is_cpd)
    else:
        all_users = await _fetch_saas_users()
        candidates = _normalize_user_data(all_users, is_cpd)
    
    if not candidates:
        LOGGER.warning("No users available in the system")
        return [], 0
    
    # Apply query filtering
    paginated_users, total_count = _apply_user_query_filter(query, candidates)
    
    # Convert to UserSearchResult objects
    results = _convert_to_user_results(paginated_users)
    
    LOGGER.info(f"Found {total_count} matching users, returning {len(results)} results")
    return results, total_count


async def _fetch_cpd_users() -> List[Dict]:
    """Fetch all users from CP4D environment."""
    url = f"{settings.di_service_url}/usermgmt/v1/usermgmt/users"
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=url, tool_name="search_users"
        )
    except ExternalAPIError as e:
        LOGGER.error(f"API error while fetching users: {str(e)}")
        raise ExternalAPIError(
            "Unable to search for users. Please verify you have the necessary permissions to list users."
        )
    
    # CP4D returns list directly
    return response if isinstance(response, list) else []


async def _fetch_saas_users() -> List[Dict]:
    """Fetch all users from SaaS environment with pagination."""
    account_id = await get_bss_account_id()
    all_users = []
    next_url = f"{tool_helper_service.user_management_url}/v2/accounts/{account_id}/users?limit={PAGE_LIMIT}"
    
    while next_url:
        try:
            response = await tool_helper_service.execute_get_request(
                url=next_url, tool_name="search_users"
            )
        except ExternalAPIError as e:
            LOGGER.error(f"API error while fetching users: {str(e)}")
            raise ExternalAPIError(
                "Unable to search for users. Please verify you have the necessary permissions to list users."
            )
        
        users_page = response.get("resources", []) if isinstance(response, dict) else []
        if not users_page:
            break
        
        all_users.extend(users_page)
        
        # Get next_url from response for pagination
        next_url = response.get("next_url") if isinstance(response, dict) else None
        if next_url is not None:
            next_url = f"{tool_helper_service.user_management_url}{next_url}"
    
    return all_users


def _apply_user_query_filter(query: Optional[str], candidates: List[Dict]) -> Tuple[List[Dict], int]:
    """Apply query filter to user candidates."""
    if not query or query.strip() == "":
        return candidates, len(candidates)
    
    matched_users = get_exact_or_fuzzy_matches(
        search_word=query,
        candidates=candidates,
        search_fields=["username", "email", "display_name"],
        max_results=MAX_RESULTS,
        cutoff=FUZZY_MATCH_THRESHOLD
    )
    return matched_users, len(matched_users)


def _convert_to_user_results(users: List[Dict]) -> List[UserSearchResult]:
    """Convert user dictionaries to UserSearchResult objects."""
    return [
        UserSearchResult(
            user_id=user["id"],
            username=user["username"],
            display_name=user.get("display_name"),
            email=user.get("email"),
            state=user.get("state", "ACTIVE")
        )
        for user in users
    ]


async def search_groups_by_query(
    query: Optional[str] = None
) -> Tuple[List[GroupSearchResult], int]:
    """
    Search for user groups by partial identifier with fuzzy matching, or list all groups.
    
    Searches across group names using intelligent fuzzy matching.
    If no query provided, returns all groups in the system.
    Supports both SaaS and CP4D environments with appropriate API endpoints.
    For SaaS, implements proper server-side pagination to fetch all groups.
    
    Args:
        query: Optional search term (group name or group ID). If None, returns all groups.
        
    Returns:
        Tuple[List[GroupSearchResult], int]: List of matching groups and total count
        
    Raises:
        ExternalAPIError: When API call fails or permission is denied
    """
    query_str = f"query='{query}'" if query else "list all groups"
    LOGGER.info(f"Searching for groups with {query_str}")
    
    # Get configuration based on environment
    is_cpd = settings.di_env_mode.upper() == "CPD"
    
    if is_cpd:
        raw_groups = await _fetch_cpd_groups()
        candidates = _normalize_group_data(raw_groups, is_cpd)
    else:
        all_groups = await _fetch_saas_groups()
        candidates = _normalize_group_data(all_groups, is_cpd)
    
    if not candidates:
        LOGGER.warning("No groups available in the system")
        return [], 0
    
    # Apply query filtering
    paginated_groups, total_count = _apply_group_query_filter(query, candidates)
    
    # Convert to GroupSearchResult objects
    results = _convert_to_group_results(paginated_groups)
    
    LOGGER.info(f"Found {total_count} matching groups, returning {len(results)} results")
    return results, total_count


async def _fetch_cpd_groups() -> List[Dict]:
    """Fetch all groups from CP4D environment."""
    url = f"{settings.di_service_url}/usermgmt/v2/groups"
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=url, tool_name="search_groups"
        )
    except ExternalAPIError as e:
        LOGGER.error(f"API error while fetching groups: {str(e)}")
        raise ExternalAPIError(
            "Unable to search for groups. Please verify you have the necessary permissions to list groups."
        )
    
    return response.get("results", []) if isinstance(response, dict) else []


async def _fetch_saas_groups() -> List[Dict]:
    """Fetch all groups from SaaS environment with pagination."""
    account_id = await get_bss_account_id()
    all_groups = []
    current_offset = 0
    
    while True:
        url = f"{get_cloud_iam_url_from_service_url(str(settings.di_service_url))}/v2/groups?account_id={account_id}&limit={PAGE_LIMIT}&offset={current_offset}"
        
        try:
            response = await tool_helper_service.execute_get_request(
                url=url, tool_name="search_groups"
            )
        except ExternalAPIError as e:
            LOGGER.error(f"API error while fetching groups: {str(e)}")
            raise ExternalAPIError(
                "Unable to search for groups. Please verify you have the necessary permissions to list groups."
            )
        
        groups_page = response.get("groups", []) if isinstance(response, dict) else []
        if not groups_page:
            break
        
        all_groups.extend(groups_page)
        
        # Check if we have more pages
        if len(groups_page) < PAGE_LIMIT:
            break
        
        current_offset += PAGE_LIMIT
    
    return all_groups


def _apply_group_query_filter(query: Optional[str], candidates: List[Dict]) -> Tuple[List[Dict], int]:
    """Apply query filter to group candidates."""
    if not query or query.strip() == "":
        return candidates, len(candidates)
    
    matched_groups = get_exact_or_fuzzy_matches(
        search_word=query,
        candidates=candidates,
        search_fields=["group_name"],
        max_results=MAX_RESULTS,
        cutoff=FUZZY_MATCH_THRESHOLD
    )
    return matched_groups, len(matched_groups)


def _convert_to_group_results(groups: List[Dict]) -> List[GroupSearchResult]:
    """Convert group dictionaries to GroupSearchResult objects."""
    return [
        GroupSearchResult(
            group_id=group["id"],
            group_name=group["group_name"],
            description=group.get("description"),
            state=group.get("state", "ACTIVE")
        )
        for group in groups
    ]


def _normalize_user_data(raw_users: List[Dict], is_cpd: bool) -> List[Dict]:
    """
    Normalize user data from different environments into a consistent format.
    
    Args:
        raw_users: Raw user data from API
        is_cpd: Whether running in CP4D environment
        
    Returns:
        List of normalized user dictionaries
    """
    if is_cpd:
        # CP4D user structure: {uid, username, displayName, email, ...}
        return [
            {
                "id": user.get("uid", ""),
                "username": user.get("username", ""),
                "display_name": user.get("displayName", ""),
                "email": user.get("email", ""),
                "state": "ACTIVE",
            }
            for user in raw_users
            if isinstance(user, dict) and user.get("username") and user.get("uid")
        ]
    else:
        # SaaS user structure: {user_id, email, iam_id, state, ...}
        return [
            {
                "id": user.get("iam_id", user.get("user_id", "")),
                "username": user.get("user_id", user.get("email", "")),
                "display_name": user.get("firstname", "") + " " + user.get("lastname", "") if user.get("firstname") else None,
                "email": user.get("email", ""),
                "state": user.get("state", "ACTIVE"),
            }
            for user in raw_users
            if isinstance(user, dict) and (user.get("user_id") or user.get("email"))
        ]


def _normalize_group_data(raw_groups: List[Dict], is_cpd: bool) -> List[Dict]:
    """
    Normalize group data from different environments into a consistent format.
    
    Args:
        raw_groups: Raw group data from API
        is_cpd: Whether running in CP4D environment
        
    Returns:
        List of normalized group dictionaries
    """
    if is_cpd:
        # CP4D group structure: {name, group_id, description, ...}
        return [
            {
                "id": str(group.get("group_id", "")),
                "group_name": group.get("name", ""),
                "description": group.get("description", ""),
                "state": "ACTIVE",
            }
            for group in raw_groups
            if isinstance(group, dict) and group.get("name") and group.get("group_id")
        ]
    else:
        # SaaS group structure: {name, id, description, ...}
        return [
            {
                "id": group.get("id", ""),
                "group_name": group.get("name", ""),
                "description": group.get("description", ""),
                "state": "ACTIVE",
            }
            for group in raw_groups
            if isinstance(group, dict) and group.get("name") and group.get("id")
        ]

# Made with Bob


async def search_roles_by_query(
    query: Optional[str] = None
) -> Tuple[List[RoleSearchResult], int]:
    """
    Search for user roles by partial identifier with fuzzy matching (CP4D only).
    
    Searches across role names using intelligent fuzzy matching. If no query is provided,
    returns all available roles.
    
    Args:
        query: Optional search term (role name). If None, returns all roles.
        
    Returns:
        Tuple[List[RoleSearchResult], int]: List of matching roles and total count
        
    Raises:
        ExternalAPIError: When API call fails or permission is denied
        ValueError: When called in SaaS environment (CP4D only feature)
    """
    LOGGER.info(f"Searching for roles with query: '{query}'")
    
    # Check if running in CP4D environment
    is_cpd = settings.di_env_mode.upper() == "CPD"
    if not is_cpd:
        raise ValueError(
            "User role search is only available in CP4D environments. "
            "This feature is not supported in SaaS deployments."
        )
    
    # Fetch all roles from API
    url = f"{settings.di_service_url}/usermgmt/v1/roles"
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=url, tool_name="search_roles"
        )
    except ExternalAPIError as e:
        LOGGER.error(f"API error while fetching roles: {str(e)}")
        raise ExternalAPIError(
            "Unable to search for roles. Please verify you have the necessary permissions to list roles."
        )
    
    # Extract raw role data
    raw_roles = response.get("rows", []) if isinstance(response, dict) else []
    
    if not raw_roles:
        LOGGER.warning("No roles available in the system")
        return [], 0
    
    # Normalize role data
    candidates = []
    for role in raw_roles:
        try:
            doc = role.get("doc", {})
            role_name = doc.get("role_name", "")
            role_key = doc.get("_id", "")
            description = doc.get("description", "")
            
            if role_name and role_key:
                candidates.append({
                    "role_key": role_key,
                    "role_name": role_name,
                    "description": description
                })
        except (KeyError, AttributeError):
            continue
    
    if not candidates:
        LOGGER.warning("No valid roles found in response")
        return [], 0
    
    # If no query provided, return all roles
    if not query or query.strip() == "":
        total_count = len(candidates)
        
        results = [
            RoleSearchResult(
                role_key=role["role_key"],
                role_name=role["role_name"],
                description=role.get("description")
            )
            for role in candidates
        ]
        
        LOGGER.info(f"Returning all {len(results)} roles (total: {total_count})")
        return results, total_count
    
    # Perform fuzzy matching
    matched_roles = get_exact_or_fuzzy_matches(
        search_word=query,
        candidates=candidates,
        search_fields=["role_name"],
        max_results=MAX_RESULTS,
        cutoff=FUZZY_MATCH_THRESHOLD
    )
    
    total_count = len(matched_roles)
    
    # Convert to RoleSearchResult objects
    results = []
    for role in matched_roles:
        results.append(RoleSearchResult(
            role_key=role["role_key"],
            role_name=role["role_name"],
            description=role.get("description")
        ))
    
    LOGGER.info(f"Found {total_count} matching roles, returning {len(results)} results")
    return results, total_count
