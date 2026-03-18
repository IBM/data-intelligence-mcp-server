# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""CSV validation utilities for glossary import."""

import csv
import io
from typing import List, Dict, Any, Optional, Tuple
from pydantic import ValidationError

from app.services.glossary.constants import (
    ARTIFACT_TYPE_GLOSSARY_TERM,
    ARTIFACT_TYPE_CATEGORY,
)

# Column name constants
COLUMN_ARTIFACT_TYPE = "Artifact Type"
from app.services.glossary.models.csv_import import (
    CSVImportResult,
    CSVRowError,
    GlossaryTermCSVRow,
    CategoryCSVRow,
)
from app.shared.exceptions.base import ServiceError


def parse_csv_content(csv_content: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Parse CSV content into headers and rows.
    
    Args:
        csv_content: CSV content as string
        
    Returns:
        Tuple of (headers, rows) where rows is a list of dictionaries
        
    Raises:
        ServiceError: If CSV parsing fails
    """
    try:
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        if not reader.fieldnames:
            raise ServiceError("CSV file is empty or has no headers")
        
        headers = list(reader.fieldnames)
        rows = list(reader)
        
        return headers, rows
        
    except csv.Error as e:
        raise ServiceError(f"Failed to parse CSV: {str(e)}")
    except Exception as e:
        raise ServiceError(f"Unexpected error parsing CSV: {str(e)}")


def validate_required_columns(headers: List[str]) -> List[str]:
    """
    Validate that required columns are present.
    
    Args:
        headers: List of column headers from CSV
        
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    # Only Name and Artifact Type are truly required
    # Category is required for terms but optional for categories
    required = {"Name", COLUMN_ARTIFACT_TYPE}
    
    headers_lower = {h.lower() for h in headers}
    required_lower = {r.lower() for r in required}
    
    missing = required_lower - headers_lower
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
    
    return errors


def validate_row(
    row: Dict[str, str],
    row_number: int
) -> Tuple[Optional[Any], List[CSVRowError]]:
    """
    Validate a single CSV row and convert to appropriate model.
    
    Args:
        row: Dictionary representing a CSV row
        row_number: Row number (1-based, excluding header)
        
    Returns:
        Tuple of (validated_model, errors)
    """
    errors = []
    
    if not any(v.strip() for v in row.values() if v):
        return None, []
    
    # Get artifact type
    artifact_type = row.get(COLUMN_ARTIFACT_TYPE, "").strip().lower()
    
    if not artifact_type:
        errors.append(CSVRowError(
            row_number=row_number,
            column=COLUMN_ARTIFACT_TYPE,
            error_message="Artifact Type is required",
            value=""
        ))
        return None, errors
    
    # Validate based on artifact type
    try:
        if artifact_type == ARTIFACT_TYPE_GLOSSARY_TERM:
            model = GlossaryTermCSVRow(**row)
            return model, []
        elif artifact_type == ARTIFACT_TYPE_CATEGORY:
            model = CategoryCSVRow(**row)
            return model, []
        else:
            errors.append(CSVRowError(
                row_number=row_number,
                column=COLUMN_ARTIFACT_TYPE,
                error_message=f"Unsupported artifact type. Must be '{ARTIFACT_TYPE_GLOSSARY_TERM}' or '{ARTIFACT_TYPE_CATEGORY}'",
                value=artifact_type
            ))
            return None, errors
            
    except ValidationError as e:
        for error in e.errors():
            field = error.get("loc", ["unknown"])[0]
            message = error.get("msg", "Validation error")
            value = row.get(str(field), "")
            
            errors.append(CSVRowError(
                row_number=row_number,
                column=str(field),
                error_message=message,
                value=value
            ))
        return None, errors
    except Exception as e:
        errors.append(CSVRowError(
            row_number=row_number,
            column=None,
            error_message=f"Unexpected validation error: {str(e)}",
            value=None
        ))
        return None, errors


def validate_csv_content(csv_content: str) -> CSVImportResult:
    """
    Validate CSV content without importing.
    
    Args:
        csv_content: CSV content as string
        
    Returns:
        CSVImportResult with validation results
    """
    try:
        headers, rows = parse_csv_content(csv_content)
    except ServiceError as e:
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
                error_message=str(e),
                value=None
            )],
            process_id=None,
            import_status=None
        )
    
    # Validate headers
    header_errors = validate_required_columns(headers)
    if header_errors:
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
                error_message=error,
                value=None
            ) for error in header_errors],
            process_id=None,
            import_status=None
        )
    
    # Validate each row
    all_errors = []
    categories_count = 0
    terms_count = 0
    
    for idx, row in enumerate(rows, start=1):
        validated_model, row_errors = validate_row(row, idx)
        
        if row_errors:
            all_errors.extend(row_errors)
        elif validated_model:
            if isinstance(validated_model, CategoryCSVRow):
                categories_count += 1
            elif isinstance(validated_model, GlossaryTermCSVRow):
                terms_count += 1
    
    success = len(all_errors) == 0
    
    return CSVImportResult(
        success=success,
        total_rows=len(rows),
        categories_created=categories_count if success else 0,
        terms_created=terms_count if success else 0,
        categories_updated=0,
        terms_updated=0,
        errors=all_errors,
        process_id=None,
        import_status=None
    )