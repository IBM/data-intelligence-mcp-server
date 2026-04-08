# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Models for CSV import of glossary artifacts."""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

class CSVRowError(BaseModel):
    """Error information for a specific CSV row."""
    row_number: int = Field(..., description="Row number in the CSV (1-based, excluding header)")
    column: Optional[str] = Field(None, description="Column name where error occurred")
    error_message: str = Field(..., description="Description of the error")
    value: Optional[str] = Field(None, description="The problematic value")


class GlossaryTermCSVRow(BaseModel):
    """
    Schema for a glossary term row in CSV import.
    
    Based on IBM watsonx.data intelligence CSV import format:
    https://dataplatform.cloud.ibm.com/docs/content/wsj/governance/csv-import.html
    
    Required columns (marked with *):
    - Name*: The name of the term
    - Artifact Type*: Must be "glossary_term" for terms
    - Category*: Parent category path (defaults to "[uncategorized]" if not provided)
    
    Optional columns - Basic Information:
    - Description: Detailed description of the term
    - Tags: Tags associated with the term
    - Business Start: Business start date
    - Business End: Business end date
    
    Optional columns - Relationships:
    - Classifications: Classifications assigned to the term
    - Data Classes: Data classes associated with the term
    - Related Terms: Comma-separated list of related term names
    - Synonyms: Alternative names for the term
    - Abbreviations: Abbreviations for the term
    - Secondary Categories: Additional categories beyond the primary one
    
    Optional columns - Governance:
    - Stewards: User stewards responsible for the term
    - Steward Groups: Group stewards responsible for the term
    
    Optional columns - Advanced:
    - Rating: Rating value for the term
    - System Business Reference: System business reference information
    - Extended Attribute Groups (DQ Constraints): Data quality constraints
    - Custom Attributes: Any custom attribute columns (prefixed with custom_)
    
    Optional columns - Modification Details:
    - Creator: Who created the term
    - Created At: When the term was created
    - Modifier: Who last modified the term
    - Modified At: When the term was last modified
    """
    
    # Required fields
    name: str = Field(..., alias="Name", description="Name of the glossary term (required)")
    artifact_type: str = Field(..., alias="Artifact Type", description="Must be 'glossary_term' for terms")
    category: str = Field("[uncategorized]", alias="Category", description="Parent category path (defaults to [uncategorized])")
    
    # Optional fields - Basic Information
    description: Optional[str] = Field(None, alias="Description", description="Detailed description")
    tags: Optional[str] = Field(None, alias="Tags", description="Tags associated with the term")
    business_start: Optional[str] = Field(None, alias="Business Start", description="Business start date")
    business_end: Optional[str] = Field(None, alias="Business End", description="Business end date")
    
    # Optional fields - Relationships
    classifications: Optional[str] = Field(None, alias="Classifications", description="Classifications assigned to the term")
    data_classes: Optional[str] = Field(None, alias="Data Classes", description="Data classes associated with the term")
    related_terms: Optional[str] = Field(None, alias="Related Terms", description="Comma-separated related terms")
    synonyms: Optional[str] = Field(None, alias="Synonyms", description="Alternative names")
    abbreviations: Optional[str] = Field(None, alias="Abbreviations", description="Abbreviations for the term")
    secondary_categories: Optional[str] = Field(None, alias="Secondary Categories", description="Additional categories")
    
    # Optional fields - Governance
    stewards: Optional[str] = Field(None, alias="Stewards", description="User stewards responsible for the term")
    steward_groups: Optional[str] = Field(None, alias="Steward Groups", description="Group stewards responsible for the term")
    
    # Optional fields - Advanced
    rating: Optional[str] = Field(None, alias="Rating", description="Rating value for the term")
    system_business_reference: Optional[str] = Field(None, alias="System Business Reference", description="System business reference")
    extended_attribute_groups: Optional[str] = Field(None, alias="Extended Attribute Groups (DQ Constraints)", description="Data quality constraints")
    
    # Optional fields - Modification Details
    creator: Optional[str] = Field(None, alias="Creator", description="Who created the term")
    created_at: Optional[str] = Field(None, alias="Created At", description="When the term was created")
    modifier: Optional[str] = Field(None, alias="Modifier", description="Who last modified the term")
    modified_at: Optional[str] = Field(None, alias="Modified At", description="When the term was last modified")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v: Optional[str]) -> str:
        """Validate category and set default if empty."""
        if not v or not v.strip():
            return "[uncategorized]"
        return v.strip()
    
    @field_validator('artifact_type')
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        """Validate that artifact type is correct for terms."""
        if v.lower() != "glossary_term":
            raise ValueError(f"Artifact Type must be 'glossary_term' for terms, got '{v}'")
        return v.lower()
    
    model_config = ConfigDict(populate_by_name=True)


class CategoryCSVRow(BaseModel):
    """
    Schema for a category row in CSV import.
    
    Required columns (marked with *):
    - Name*: The name of the category
    - Artifact Type*: Must be "category" for categories
    
    Optional columns:
    - Category: Parent category path (empty for top-level, or "Parent >> Child" for nested)
    
    Optional columns - Basic Information:
    - Description: Detailed description of the category
    - Tags: Tags associated with the category
    - Business Start: Business start date
    - Business End: Business end date
    
    Optional columns - Governance:
    - Classifications: Classifications assigned to the category
    - Stewards: User stewards responsible for the category
    - Steward Groups: Group stewards responsible for the category
    
    Optional columns - Advanced:
    - Reporting Authorized: Whether reporting is authorized for this category
    - Custom Attributes: Any custom attribute columns (prefixed with custom_)
    
    Optional columns - Modification Details:
    - Creator: Who created the category
    - Created At: When the category was created
    - Modifier: Who last modified the category
    - Modified At: When the category was last modified
    """
    
    # Required fields
    name: str = Field(..., alias="Name", description="Name of the category (required)")
    artifact_type: str = Field(..., alias="Artifact Type", description="Must be 'category' for categories")
    
    # Optional fields - Category can be empty for top-level categories
    category: Optional[str] = Field(None, alias="Category", description="Parent category path (empty for top-level)")
    
    # Optional fields - Basic Information
    description: Optional[str] = Field(None, alias="Description", description="Detailed description")
    tags: Optional[str] = Field(None, alias="Tags", description="Tags associated with the category")
    business_start: Optional[str] = Field(None, alias="Business Start", description="Business start date")
    business_end: Optional[str] = Field(None, alias="Business End", description="Business end date")
    
    # Optional fields - Governance
    classifications: Optional[str] = Field(None, alias="Classifications", description="Classifications assigned to the category")
    stewards: Optional[str] = Field(None, alias="Stewards", description="User stewards responsible for the category")
    steward_groups: Optional[str] = Field(None, alias="Steward Groups", description="Group stewards responsible for the category")
    
    # Optional fields - Advanced
    reporting_authorized: Optional[str] = Field(None, alias="Reporting Authorized", description="Whether reporting is authorized")
    
    # Optional fields - Modification Details
    creator: Optional[str] = Field(None, alias="Creator", description="Who created the category")
    created_at: Optional[str] = Field(None, alias="Created At", description="When the category was created")
    modifier: Optional[str] = Field(None, alias="Modifier", description="Who last modified the category")
    modified_at: Optional[str] = Field(None, alias="Modified At", description="When the category was last modified")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty."""
        if not v or not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()
    
    
    @field_validator('artifact_type')
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        """Validate that artifact type is correct for categories."""
        if v.lower() != "category":
            raise ValueError(f"Artifact Type must be 'category' for categories, got '{v}'")
        return v.lower()
    
    model_config = ConfigDict(populate_by_name=True)


class CSVImportRequest(BaseModel):
    """Request model for CSV import."""
    
    csv_content: str = Field(
        ...,
        description="""CSV content as a string. Must follow IBM watsonx.data intelligence format (https://dataplatform.cloud.ibm.com/docs/content/wsj/governance/csv-import.html).

Required columns (marked with *):
- Name*: Name of the artifact
- Artifact Type*: Type of artifact ('glossary_term' or 'category')

Optional columns for Terms:
- Category: Parent category path (defaults to "[uncategorized]" if not provided)

Optional columns for Terms - Basic Information:
- Description: Detailed description
- Tags: Tags associated with the term
- Business Start: Business start date
- Business End: Business end date

Optional columns for Terms - Relationships:
- Classifications: Classifications assigned to the term
- Data Classes: Data classes associated with the term
- Related Terms: Comma-separated related term names
- Synonyms: Alternative names
- Abbreviations: Abbreviations for the term
- Secondary Categories: Additional categories beyond the primary one

Optional columns for Terms - Governance:
- Stewards: User stewards responsible for the term
- Steward Groups: Group stewards responsible for the term

Optional columns for Terms - Advanced:
- Rating: Rating value for the term
- System Business Reference: System business reference information
- Extended Attribute Groups (DQ Constraints): Data quality constraints
- Custom Attributes: Any custom attribute columns (prefixed with custom_)

Optional columns for Terms - Modification Details:
- Creator: Who created the term
- Created At: When the term was created
- Modifier: Who last modified the term
- Modified At: When the term was last modified

Optional columns for Categories:
- Category: Parent category path (empty for top-level, or "Parent >> Child" for nested)

Optional columns for Categories - Basic Information:
- Description: Detailed description
- Tags: Tags associated with the category
- Business Start: Business start date
- Business End: Business end date

Optional columns for Categories - Governance:
- Classifications: Classifications assigned to the category
- Stewards: User stewards responsible for the category
- Steward Groups: Group stewards responsible for the category

Optional columns for Categories - Advanced:
- Reporting Authorized: Whether reporting is authorized
- Custom Attributes: Any custom attribute columns (prefixed with custom_)

Optional columns for Categories - Modification Details:
- Creator: Who created the category
- Created At: When the category was created
- Modifier: Who last modified the category
- Modified At: When the category was last modified

Example CSV for Terms:
```
Name,Artifact Type,Category,Description,Related Terms,Synonyms
Credit Risk,glossary_term,Risk Management,The potential for financial loss due to borrower default,"Probability of Default,Loss Given Default",Default Risk
```

Example CSV for Categories:
```
Name,Artifact Type,Category,Description
Risk Management,category,,Category for risk-related terms
```
"""
    )
    
    validate_only: bool = Field(
        False,
        description="If true, only validate the CSV without importing. Returns validation errors if any."
    )
    
    merge_option: str = Field(
        "all",
        description="""Import merge option for handling existing artifacts:
- 'all': Imported values will replace all existing values in catalog (default)
- 'specified': Only non-empty imported values replace existing values
- 'empty': Imported values replace only empty values in catalog"""
    )
    
    @field_validator('merge_option')
    @classmethod
    def validate_merge_option(cls, v: str) -> str:
        """Validate merge_option is one of the allowed values."""
        allowed = ['all', 'specified', 'empty']
        if v.lower() not in allowed:
            raise ValueError(f"merge_option must be one of: {', '.join(allowed)}. Got '{v}'")
        return v.lower()


class CSVImportResult(BaseModel):
    """Result of CSV import operation."""
    
    success: bool = Field(..., description="Whether the import was successful")
    total_rows: int = Field(..., description="Total number of data rows processed (excluding header)")
    categories_created: int = Field(0, description="Number of categories created")
    terms_created: int = Field(0, description="Number of terms created")
    categories_updated: int = Field(0, description="Number of categories updated")
    terms_updated: int = Field(0, description="Number of terms updated")
    errors: List[CSVRowError] = Field(default_factory=list, description="List of validation or import errors")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
    imported_artifacts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of successfully imported artifacts with their IDs and URLs"
    )
    process_id: Optional[str] = Field(None, description="Process ID for async import tracking", exclude=True)
    import_status: Optional[str] = Field(None, description="Current status of the import process")
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0
    
    @property
    def summary(self) -> str:
        """Generate a human-readable summary."""
        if not self.success:
            return f"Import failed with {len(self.errors)} error(s)"
        
        parts = []
        if self.categories_created > 0:
            parts.append(f"{self.categories_created} categories created")
        if self.terms_created > 0:
            parts.append(f"{self.terms_created} terms created")
        if self.categories_updated > 0:
            parts.append(f"{self.categories_updated} categories updated")
        if self.terms_updated > 0:
            parts.append(f"{self.terms_updated} terms updated")
        
        if not parts:
            return "No artifacts were imported"
        
        return "Successfully imported: " + ", ".join(parts)

    def _format_errors_table(self) -> List[str]:
        """Format errors as a markdown table."""
        lines = [
            "**Errors:**", "",
            "| Row | Column | Message |",
            "|-----|--------|---------|",
        ]
        for err in self.errors:
            col = err.column or "—"
            lines.append(f"| {err.row_number} | {col} | {err.error_message} |")
        return lines

    def _format_artifact_section(self, label: str, created: int, updated: int, names: List[str]) -> List[str]:
        """Format a section for one artifact type (categories or terms)."""
        if not created and not updated:
            return []
        label_parts = []
        if created:
            label_parts.append(f"{created} created")
        if updated:
            label_parts.append(f"{updated} updated")
        lines = [f"**{label} ({', '.join(label_parts)}):**", ""]
        if names:
            lines += ["| Name |", "|------|"]
            lines += [f"| `{name}` |" for name in names]
        lines.append("")
        return lines

    @property
    def _is_total_failure(self) -> bool:
        """True when import failed with no artifacts created or updated."""
        total_imported = (
            self.categories_created + self.terms_created +
            self.categories_updated + self.terms_updated
        )
        return not self.success and not total_imported

    @property
    def _is_partial_success(self) -> bool:
        """True when some artifacts were imported but there were also errors."""
        total_imported = (
            self.categories_created + self.terms_created +
            self.categories_updated + self.terms_updated
        )
        return total_imported > 0 and len(self.errors) > 0

    @property
    def message(self) -> str:
        """Generate a formatted markdown message for display to the user."""
        if self.import_status == 'TIMEOUT':
            return "\n".join([
                "**Import timed out.**", "",
                "The import process exceeded the maximum wait time. "
                "Consider splitting your CSV into smaller batches (e.g. 50 rows at a time) "
                "and importing each batch separately.",
            ])

        if self._is_total_failure:
            lines = ["**Import failed.**"]
            if self.errors:
                lines += [""] + self._format_errors_table()
            return "\n".join(lines)

        categories_names = [a["name"] for a in self.imported_artifacts if a.get("type") == "category"]
        terms_names = [a["name"] for a in self.imported_artifacts if a.get("type") == "glossary_term"]

        # Distinguish between complete and partial success
        if self._is_partial_success:
            lines = ["**Import partially succeeded.**", ""]
        else:
            lines = ["**Import succeeded.**", ""]
        lines += self._format_artifact_section("Categories", self.categories_created, self.categories_updated, categories_names)
        lines += self._format_artifact_section("Terms", self.terms_created, self.terms_updated, terms_names)

        if self.errors:
            lines += self._format_errors_table() + [""]

        return "\n".join(lines)


class CSVSchemaInfo(BaseModel):
    """Information about the CSV schema for LLM consumption."""
    
    description: str = Field(
        ...,
        description="Description of the CSV format"
    )
    required_columns: List[str] = Field(
        ...,
        description="List of required column names"
    )
    optional_columns: Dict[str, str] = Field(
        ...,
        description="Dictionary of optional column names and their descriptions"
    )
    allowed_artifact_types: List[str] = Field(
        ...,
        description="List of allowed artifact types"
    )
    allowed_status_values: List[str] = Field(
        ...,
        description="List of allowed status values"
    )
    example_csv: str = Field(
        ...,
        description="Example CSV content"
    )
    constraints: List[str] = Field(
        ...,
        description="List of constraints and validation rules"
    )