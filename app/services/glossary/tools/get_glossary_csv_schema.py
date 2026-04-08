# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Tool for retrieving CSV schema information for glossary imports."""

from typing import Optional
from fastmcp import Context

from app.core.registry import service_registry
from app.services.glossary.models.csv_import import CSVSchemaInfo
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="get_glossary_csv_schema",
    description="""Get detailed information about the CSV schema for importing glossary artifacts.

This tool returns comprehensive schema information that helps LLMs understand how to:
1. Generate properly formatted CSV content from unstructured documents
2. Validate user-provided CSV files before import
3. Understand constraints and validation rules

The schema includes:
- Required and optional column names
- Column descriptions and purposes
- Allowed values for enumerated fields
- Validation constraints
- Example CSV content
- Best practices for CSV generation

Use this tool when you need to:
- Generate a CSV from a document (like a policy or specification)
- Validate CSV format before calling glossary_csv_import
- Understand what fields are available for glossary artifacts
- Learn the constraints for each field""",
)
@auto_context
async def get_glossary_csv_schema(
    ctx: Optional[Context] = None,
) -> CSVSchemaInfo:
    """
    Get CSV schema information for glossary import.
    
    Args:
        ctx: Optional MCP context
        
    Returns:
        CSVSchemaInfo with detailed schema information
    """
    LOGGER.info("get_glossary_csv_schema called")
    
    return CSVSchemaInfo(
        description=(
            "CSV format for importing glossary terms and categories."
            "The CSV must follow comma-separated values format with a header row. "
            "Each row represents either a glossary term or a category."
        ),
        required_columns=[
            "Name",
            "Artifact Type"
        ],
        optional_columns={
            # Category field
            "Category": "Parent category path - required for terms (defaults to '[uncategorized]'), optional for categories (empty for top-level)",
            # Basic Information
            "Description": "Detailed description of the artifact",
            "Tags": "Tags associated with the artifact",
            "Business Start": "Business start date",
            "Business End": "Business end date",
            # Relationships (terms only)
            "Classifications": "Classifications assigned (terms: yes, categories: yes)",
            "Data Classes": "Data classes associated (terms only)",
            "Related Terms": "Comma-separated list of related term names (terms only)",
            "Synonyms": "Alternative names, comma-separated (terms only)",
            "Abbreviations": "Abbreviations for the term (terms only)",
            "Secondary Categories": "Additional categories beyond the primary one (terms only)",
            # Governance
            "Stewards": "User stewards responsible",
            "Steward Groups": "Group stewards responsible",
            # Advanced
            "Rating": "Rating value (terms only)",
            "System Business Reference": "System business reference information (terms only)",
            "Extended Attribute Groups (DQ Constraints)": "Data quality constraints (terms only)",
            "Reporting Authorized": "Whether reporting is authorized (categories only)",
            # Modification Details
            "Creator": "Who created the artifact",
            "Created At": "When the artifact was created",
            "Modifier": "Who last modified the artifact",
            "Modified At": "When the artifact was last modified"
        },
        allowed_artifact_types=[
            "glossary_term",
            "category"
        ],
        allowed_status_values=[],
        example_csv="""Name,Artifact Type,Category,Description,Related Terms,Synonyms
Risk Management,category,[uncategorized],Category for risk-related terms,,
Credit Risk,glossary_term,Risk Management,The potential for financial loss due to borrower default,"Probability of Default,Loss Given Default",Default Risk
Probability of Default,glossary_term,Risk Management,The likelihood that a borrower will be unable to meet debt obligations,Credit Risk,PD
Loss Given Default,glossary_term,Risk Management,The percentage of exposure the bank expects to lose if a borrower defaults,"Credit Risk,Probability of Default",LGD""",
        constraints=[
            "Name is required and cannot be empty",
            "Artifact Type is required and must be 'glossary_term' or 'category'",
            "Category is required and defaults to '[uncategorized]' if not provided",
            "Related Terms should be comma-separated term names (applies to terms only)",
            "Category paths use forward slash (/) for hierarchy (e.g., 'Parent/Child')",
            "Empty rows are ignored",
            "Column names are case-sensitive",
            "CSV must use comma as delimiter",
            "Text containing commas should be quoted",
            "First row must be the header row"
        ]
    )


@service_registry.tool(
    name="get_glossary_csv_schema",
    description="""Get detailed information about the CSV schema for importing glossary artifacts.

This is the Watsonx Orchestrator compatible version.

Returns comprehensive schema information that helps understand how to:
1. Generate properly formatted CSV content from unstructured documents
2. Validate user-provided CSV files before import
3. Understand constraints and validation rules

See get_glossary_csv_schema for detailed documentation.""",
)
@auto_context
async def wxo_get_glossary_csv_schema(
    ctx: Optional[Context] = None,
) -> CSVSchemaInfo:
    """
    Watsonx Orchestrator compatible version of get_glossary_csv_schema.
    
    Args:
        ctx: Optional MCP context
        
    Returns:
        CSVSchemaInfo with detailed schema information
    """
    return await get_glossary_csv_schema(ctx=ctx)