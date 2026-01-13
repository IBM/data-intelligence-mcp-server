"""
# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

Model for adding or editing collaborators to a project.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import cast, Literal as LiteralType

class AddOrEditCollaboratorRequest(BaseModel):
    """Model for adding or editing collaborators or update the role of the collaborator to a project."""
    
    project_identifier: str = Field(
        ...,
        description="The project name or id of the project"
    )
    
    user_names: List[str] = Field(
        ...,
        description="The usernames or group names to add as collaborators. Must match the length of the role list."
    )
    
    role: List[Literal["viewer", "editor", "admin"]] = Field(
        default_factory=lambda: ["viewer"],
        description="Roles to assign to the collaborators. Must match the length of user_names list. Defaults to 'editor' for each user if not specified."
    )
    
    type: Optional[List[Literal["user", "group"]]] = Field(
        default_factory=lambda: ["user"],
        description="The member types: 'user' for individual users or 'group' for access groups. Must match the length of user_names list. Defaults to list of 'user' for each member if not specified."
    )
    
    @model_validator(mode='after')
    def validate_lists_length(self):
        """Ensure user_names, role, and type lists have compatible lengths."""
        user_count = len(self.user_names)
        
        # Handle role list - expand single role or validate length
        self.role = self.expand_or_validate_list(
            self.role, user_count, "roles", "role"
        )
        
        # Handle type list - expand single type or validate length
        if self.type is None:
            self.type = cast(List[LiteralType["user", "group"]], ["user"] * user_count)
        else:
            self.type = self.expand_or_validate_list(
                self.type, user_count, "types", "type"
            )
        
        return self
    
    @staticmethod
    def expand_or_validate_list(
        input_list: List, target_length: int, list_name: str, singular_name: str
    ) -> List:
        """
        Expand a single-item list to target length or validate list length matches.
        
        Args:
            input_list: The list to expand or validate
            target_length: The required length
            list_name: Name of the list for error messages (plural)
            singular_name: Name of the item for error messages (singular)
            
        Returns:
            Expanded or validated list
            
        Raises:
            ValueError: If list length doesn't match and isn't 1
        """
        if len(input_list) == 1 and target_length > 1:
            # Expand single item to all users
            return input_list * target_length
        elif len(input_list) != target_length:
            raise ValueError(
                f"The number of {list_name} ({len(input_list)}) must match the number of user_names ({target_length}) "
                f"or provide a single {singular_name} to apply to all users."
            )
        return input_list
    
    @field_validator('user_names')
    @classmethod
    def validate_user_names(cls, v):
        """Ensure user_names list is not empty."""
        if not v:
            raise ValueError("user_names list cannot be empty")
        return v


class CollaboratorMember(BaseModel):
    """Model representing a collaborator member.
    
    Can be used both for internal operations (with id) and responses (without id).
    The id field is optional and should be excluded from responses for security.
    """
    
    user_name: str = Field(..., description="User's name or email address")
    id: Optional[str] = Field(default=None, description="User's IAM ID or group ID (internal use only)")
    role: str = Field(..., description="Role assigned to the user")
    state: str = Field(default="ACTIVE", description="User's state")
    type: str = Field(default="user", description="Member type: 'user' or 'group'")


class AddOrEditCollaboratorResponse(BaseModel):
    """Response model for adding or editing collaborators."""
    
    project_id: str = Field(..., description="The project ID where collaborators were added")
    added_members: List[CollaboratorMember] = Field(
        ...,
        description="List of members that were successfully added (without sensitive ID information)"
    )
    message: str = Field(..., description="Success message")
