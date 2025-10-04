# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field, model_validator
from typing import Literal

class Entity(BaseModel):
    """A single RHS entity."""
    name: str = Field(..., description="Display name of the data class")
    global_id: str = Field(..., alias="globalid", description="Global ID of the data class")

class RuleRhsTermResponse(BaseModel):
    """Response model for RHS terms retrieval."""
    entities: list[Entity] = Field(default_factory=list, description="List of entities with name and global ID")
    total_count: int = Field(description="Total number of matching results after filtering")
    search_string: str = Field(description="The search string used in the query")

class TriggerCondition(BaseModel):
    """A single trigger condition.

    IMPORTANT OPERATOR RULES:
    - Asset.InferredClassification (data classes) → ONLY "CONTAINS" allowed
    - Asset.Tags → ONLY "CONTAINS" allowed
    - Asset.Name → "LIKE", "EQUALS", "IN" allowed
    - Asset.Owner → "EQUALS", "IN" allowed
    - Business.Term → "CONTAINS" allowed
    """
    field: Literal[
        "Asset.Name",
        "Asset.Owner",
        "Asset.Schema",
        "Business.Term",
        "Asset.UserClassification",
        "Asset.ColumnName",
        "Asset.InferredClassification",
        "Asset.Tags",
        "User.Group",
        "User.Name"
    ] = Field(
        ...,
        description="Field to evaluate",
        json_schema_extra={
            "oneOf": [
                {"const": "Asset.Name", "title": "Asset name",
                 "description": "Asset display name - for table/column names. Use CONTAINS, LIKE operators."},
                {"const": "Asset.Owner", "title": "Owner",
                 "description": "Asset owner username/email. MUST ONLY us CONTAINS operators."},
                {"const": "Asset.Schema", "title": "schema",
                 "description": "Schema of the connected asset.. MUST ONLY use CONTAINS operator."},
                {"const": "Business.Term", "title": "Business term",
                 "description": "Business glossary term. MUST ONLY us CONTAINS operator."},
                 {"const": "Asset.UserClassification", "title": "Classification",
                 "description": "The type of sensitive information in the asset. MUST ONLY use CONTAINS operator."},
                 {"const": "Asset.ColumnName", "title": "Column name",
                 "description": "The name of a column in an asset.. Use CONTAINS, LIKE operator."},
                 {"const": "Asset.InferredClassification", "title": "Data class",
                 "description": "The classification of a column. MUST ONLY us CONTAINS operator."},
                 {"const": "Asset.Tags", "title": "Tags",
                 "description": "The tag on an asset or column. MUST ONLY use CONTAINS operator."},
                 {"const": "User.Group", "title": "User Group",
                 "description": "Group(s) that the user requesting access to an asset belongs to. MUST ONLY use CONTAINS operator."},
                {"const": "User.Name", "title": "User Name",
                 "description": "The user requesting access to an asset. MUST ONLY use CONTAINS operator."}

            ]
        }
    )

    operator: Literal["CONTAINS", "LIKE"] = Field(
        ...,
        description="""Comparison operator. CRITICAL RULES:
        - For Asset.Name: use CONTAINS, LIKE
        - For Asset.Owner: ONLY use CONTAINS
        - For Asset.Schema: ONLY use CONTAINS
        - For Business.Term: ONLY use CONTAINS
        - For Asset.InferredClassification: ONLY use CONTAINS
        - For Asset.ColumnName: use CONTAINS, LIKE
        - For Asset.UserClassification: ONLY use CONTAINS
        - For Asset.Tags: ONLY use CONTAINS
        - For User.Group: ONLY use CONTAINS
        - For User.Name: ONLY use CONTAINS

        - For Business.Term: use CONTAINS""",
        json_schema_extra={
            "oneOf": [
                {"const": "CONTAINS", "title": "Contains",
                 "description": "Check if value exists - REQUIRED for Asset.InferredClassification and Asset.Tags"},
                {"const": "LIKE", "title": "Like",
                 "description": "Pattern with wildcards - valid for Asset.Name only"},
                {"const": "EQUALS", "title": "Equals",
                 "description": "Exact match - valid for Asset.Name and Asset.Owner only, NOT for data classes or tags"},
                {"const": "IN", "title": "In",
                 "description": "Match any in list - valid for Asset.Name and Asset.Owner only"}
            ]
        }
    )

    value: str = Field(..., description="Value to compare. For data classes, use globalid from search.")
    negate: bool = Field(default=False, description="Negate this condition (NOT)")

    @model_validator(mode='after')
    def validate_operator_field_combination(self):
        """Validate operator is compatible with field type."""
        field = self.field
        operator = self.operator

        # Data classes MUST use CONTAINS
        if field == "Asset.InferredClassification" and operator != "CONTAINS":
            raise ValueError(
                f"Asset.InferredClassification (data class) MUST use 'CONTAINS' operator. "
                f"You cannot use '{operator}' with data classes. Change operator to 'CONTAINS'."
            )

        # Tags MUST use CONTAINS
        if field == "Asset.Tags" and operator != "CONTAINS":
            raise ValueError(
                f"Asset.Tags MUST use 'CONTAINS' operator. "
                f"You cannot use '{operator}' with tags. Change operator to 'CONTAINS'."
            )

        # Business terms should use CONTAINS
        if field == "Business.Term" and operator != "CONTAINS":
            raise ValueError(
                f"Business.Term should use 'CONTAINS' operator. "
                f"You cannot use '{operator}' with business terms. Change operator to 'CONTAINS'."
            )

        # Owner should not use CONTAINS or LIKE
        if field == "Asset.Owner" and operator in ["CONTAINS", "LIKE"]:
            raise ValueError(
                f"Asset.Owner should use 'EQUALS' or 'IN' operator, not '{operator}'."
            )

        return self

class RuleAction(BaseModel):
    """Action to take when rule matches."""
    name: Literal["Allow", "Deny", "Transform"]

class Rule(BaseModel):
    """Internal rule representation."""
    name: str
    description: str
    trigger: list
    governance_type_id: str = "Access"
    action: RuleAction
    state: Literal["active", "draft"]

class PreviewMetadata(BaseModel):
    """Metadata for displaying human-readable previews.

    This class can be extended with additional fields as needed for preview display.
    All fields are optional with defaults to maintain backward compatibility.
    """
    data_class_names: dict[str, str] = Field(
        default_factory=dict,
        description="Map of global_id -> display name for data classes"
    )

    business_term_names: dict[str, str] = Field(
        default_factory=dict,
        description="Map of term_id -> display name for business terms"
    )

    @staticmethod
    def get_field_display_name(field: str) -> str:
        """Get human-readable field name."""
        field_map = {
            "Asset.Name": "Asset name",
            "Asset.InferredClassification": "Data class",
            "Asset.Owner": "Owner",
            "Business.Term": "Business term",
            "Asset.Tags": "Tags"
        }
        return field_map.get(field, field)

    def get_value_display(self, field: str, value: str) -> str:
        """Get human-readable value for display.

        Looks up display names from the appropriate mapping based on field type.
        Falls back to the original value if no mapping exists.
        """
        # Remove common prefixes for lookup
        clean_value = value.lstrip("#$")

        # Field-specific lookups
        if field == "Asset.InferredClassification":
            return self.data_class_names.get(clean_value, value)
        elif field == "Business.Term":
            return self.business_term_names.get(clean_value, value)

        # Default: return cleaned value
        return clean_value

class CreateRuleRequest(BaseModel):
    name: str
    description: str
    action: Literal["Allow", "Deny", "Transform"]
    conditions: list[TriggerCondition]
    combine_with: Literal["AND", "OR"] = Field(
        default="AND",
        description="How to combine conditions"
    )
    state: Literal["active", "draft"] = "active"
    preview_only: bool = True
    metadata: PreviewMetadata = Field(
        default_factory=PreviewMetadata,
        description="Metadata for human-readable preview display"
    )

class CreateRuleResponse(BaseModel):
    success: bool
    display_to_user: str
    preview_json: dict | None = None
    rule_id: str | None = None
    url: str | None = None
    error: str | None = None
