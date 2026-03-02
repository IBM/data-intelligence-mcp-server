# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
User Search Service

This service provides tools for searching and retrieving users, user groups,
and user roles by partial identifiers in watsonx.data intelligence. It enables
AI agents to quickly find the right identity records for downstream operations.

Features:
- Unified search tool with search_type parameter (user, group, or role)
- Search users by name, email, username, or user ID
- Search groups by name, description, or group ID
- Search roles by name (CP4D only)
- Intelligent fuzzy matching with confidence scores
- Pagination support
- Works in both SaaS and CP4D environments
"""

from app.services.user_search.tools.search_user_groups_roles import search_user_groups_roles, wxo_search_user_groups_roles

__all__ = [
    "search_user_groups_roles",
    "wxo_search_user_groups_roles",
]

# Made with Bob
