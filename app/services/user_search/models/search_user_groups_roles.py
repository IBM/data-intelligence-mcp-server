# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import List, Optional, Literal, Union
from app.services.user_search.models.search_users import UserSearchResult
from app.services.user_search.models.search_groups import GroupSearchResult
from app.services.user_search.models.search_roles import RoleSearchResult


class UnifiedSearchRequest(BaseModel):
    """Unified request model for searching users, groups, or roles."""
    
    search_type: Literal["user", "group", "role"] = Field(
        description="Type of identity to search for: 'user' for users, 'group' for user groups, or 'role' for user roles (CP4D only)"
    )
    query: Optional[str] = Field(
        default=None,
        description="Optional search term to filter results. If not provided or empty, returns all items of the specified type. For users: searches name, email, username, or user ID. For groups: searches group name or group ID. For roles: searches role name."
    )


class UnifiedSearchResponse(BaseResponseModel):
    """Unified response model for search results."""
    
    search_type: str = Field(
        description="Type of identity that was searched: 'user', 'group', or 'role'"
    )
    total_count: int = Field(
        description="Total number of items matching the query"
    )
    returned_count: int = Field(
        description="Number of items returned in this response"
    )
    results: Union[List[UserSearchResult], List[GroupSearchResult], List[RoleSearchResult]] = Field(
        description="List of matching results with identity information"
    )
    message: str = Field(
        description="Human-readable status message about the search results"
    )
    query: Optional[str] = Field(
        description="The original search query"
    )


# Made with Bob