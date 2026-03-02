# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Optional


class RoleSearchResult(BaseModel):
    """Model for individual role search result."""
    
    role_key: str = Field(
        description="Unique identifier/key for the role"
    )
    role_name: str = Field(
        description="Name of the role"
    )
    description: Optional[str] = Field(
        default=None,
        description="Description of the role"
    )

# Made with Bob
