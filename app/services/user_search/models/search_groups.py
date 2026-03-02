# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Optional


class GroupSearchResult(BaseModel):
    """Model for individual group search result."""
    
    group_id: str = Field(
        description="Unique identifier for the group"
    )
    group_name: str = Field(
        description="Name of the group"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the group"
    )
    state: str = Field(
        default="ACTIVE",
        description="Group state (e.g., ACTIVE, INACTIVE)"
    )

# Made with Bob
