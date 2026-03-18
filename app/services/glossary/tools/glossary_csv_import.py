# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Tool for importing glossary artifacts from CSV files."""

from typing import Optional
from fastmcp import Context

from app.core.registry import service_registry
from app.services.glossary.models.csv_import import (
    CSVImportRequest,
    CSVImportResult,
    CSVRowError,
    CSVSchemaInfo,
)
from app.services.glossary.utils.csv_validation import validate_csv_content
from app.services.glossary.utils.csv_import import import_csv_content
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="glossary_csv_import",
    description="""Import business glossary terms and categories from CSV files.

This tool accepts CSV content following IBM watsonx.governance format and either validates or imports glossary artifacts.

**Supported Artifact Types:**
- glossary_term: Business terms with definitions, examples, and relationships
- category: Organizational categories for grouping terms

**CSV Format Requirements:**

Required columns (marked with *):
- Name*: Name of the artifact
- Artifact Type*: Type ('glossary_term' or 'category')
- Category*: Parent category path for terms (defaults to "[uncategorized]" if not provided). Optional for categories (empty for top-level)

Optional columns for Terms - Basic Information:
- Description: Detailed description
- Tags: Tags associated with the term
- Business Start: Business start date
- Business End: Business end date

Optional columns for Terms - Relationships:
- Classifications: Classifications assigned to the term
- Data Classes: Data classes associated with the term
- Related Terms: Comma-separated related term names
- Part Of Terms: Terms that this term is part of
- Type Of Terms: Terms that this term is a type of
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

Optional columns for Categories - Basic Information:
- Category: Parent category path (empty for top-level, or "Parent >> Child" for nested)
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

**Example CSV:**
```
Name,Artifact Type,Category,Description,Related Terms,Synonyms
Credit Risk,glossary_term,Risk Management,The potential for financial loss,"Probability of Default,Loss Given Default",Default Risk
Risk Management,category,,Category for risk-related terms,,
```

**Validation Mode:**
Set validate_only=true to check CSV format without importing. Returns detailed error messages with row numbers.

**Import Mode:**
Set validate_only=false to import artifacts. Creates categories first, then terms, establishing all relationships.

**Error Handling:**
Returns structured errors with:
- Row number (1-based, excluding header)
- Column name where error occurred
- Error message
- Problematic value

This enables LLMs to generate properly formatted CSVs and validate user-provided CSVs before import.""",
)
@auto_context
async def glossary_csv_import(
    request: CSVImportRequest,
    ctx: Optional[Context] = None,
) -> CSVImportResult:
    """
    Import glossary artifacts from CSV content.
    
    Args:
        request: CSV import request with content and options
        ctx: Optional MCP context
        
    Returns:
        CSVImportResult with import/validation results
        
    Raises:
        ServiceError: If import fails unexpectedly
    """
    LOGGER.info(
        f"glossary_csv_import called with validate_only={request.validate_only}, "
        f"csv_length={len(request.csv_content)}"
    )
    
    try:
        if request.validate_only:
            LOGGER.info("Performing validation only")
            result = validate_csv_content(request.csv_content)
        else:
            LOGGER.info(f"Performing import with merge_option={request.merge_option}")
            result = await import_csv_content(request.csv_content, merge_option=request.merge_option)
        
        LOGGER.info(
            f"Import completed: success={result.success}, "
            f"total_rows={result.total_rows}, "
            f"errors={len(result.errors)}"
        )
        
        return result
        
    except Exception as e:
        LOGGER.error(f"Unexpected error during CSV import: {str(e)}", exc_info=True)
        return CSVImportResult(
            success=False,
            total_rows=0,
            categories_created=0,
            terms_created=0,
            categories_updated=0,
            terms_updated=0,
            errors=[CSVRowError(
                row_number=0,
                column=None,
                error_message=f"Unexpected error: {str(e)}",
                value=None
            )],
            process_id=None,
            import_status=None
        )



@service_registry.tool(
    name="glossary_csv_import",
    description="""Import business glossary terms and categories from CSV files.

This is the Watsonx Orchestrator compatible version that accepts parameters directly.

Accepts CSV content following IBM watsonx.governance format and either validates or imports glossary artifacts.

See glossary_csv_import for detailed documentation.""",
)
@auto_context
async def wxo_glossary_csv_import(
    csv_content: str,
    validate_only: bool = False,
    merge_option: str = "all",
    ctx: Optional[Context] = None,
) -> CSVImportResult:
    """
    Watsonx Orchestrator compatible version of glossary_csv_import.
    
    Args:
        csv_content: CSV content as string
        validate_only: If true, only validate without importing
        merge_option: Import merge option (all, specified, empty)
        ctx: Optional MCP context
        
    Returns:
        CSVImportResult with import/validation results
    """
    request = CSVImportRequest(
        csv_content=csv_content,
        validate_only=validate_only,
        merge_option=merge_option
    )
    return await glossary_csv_import(request, ctx=ctx)