# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Optional


class UserSearchResult(BaseModel):
    """Model for individual user search result."""
    
    user_id: str = Field(
        description="Unique identifier for the user (iam_id in SaaS, uid in CP4D)"
    )
    username: str = Field(
        description="Username or user ID"
    )
    display_name: Optional[str] = Field(
        default=None,
        description="User's display name or full name"
    )
    email: Optional[str] = Field(
        default=None,
        description="User's email address"
    )
    state: str = Field(
        default="ACTIVE",
        description="User account state (e.g., ACTIVE, INACTIVE)"
    )

# Made with Bob
