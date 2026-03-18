# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""CSV import utilities for glossary import."""

import asyncio
import csv
import io
from typing import Dict, Any, List, Optional

from app.core.auth import get_access_token
from app.core.settings import settings
from app.services.glossary.constants import (
    ERROR_CODE_INVALID_HEADER,
    ERROR_CODE_INVALID_ARTIFACT_TYPE,
    ERROR_CODE_MISSING_CATEGORY,
    IMPORT_STATUS_SUCCEEDED,
    IMPORT_STATUS_COMPLETED,
    CSV_FILENAME,
    CSV_CONTENT_TYPE,
    MERGE_OPTION_ALL,
    OPERATION_IMPORT_CREATE,
    OPERATION_IMPORT_MODIFY,
    ARTIFACT_TYPE_GLOSSARY_TERM,
    ARTIFACT_TYPE_CATEGORY,
    CSV_COLUMN_ARTIFACT_TYPE,
)
from app.services.glossary.models.csv_import import (
    CSVImportResult,
    CSVRowError,
)
from app.services.glossary.utils.csv_validation import validate_csv_content
from app.services.glossary.utils.csv_polling import poll_import_status
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER
from app.shared.utils.http_client import get_async_http_client


def _determine_error_column(error_code: str, parameters: List[str]) -> Optional[str]:
    """
    Determine the column name based on error code.
    
    Args:
        error_code: Error code from API
        parameters: Error parameters from API
        
    Returns:
        Column name or None
    """
    if ERROR_CODE_INVALID_HEADER in error_code:
        return parameters[0] if parameters else None
    elif ERROR_CODE_INVALID_ARTIFACT_TYPE in error_code:
        return CSV_COLUMN_ARTIFACT_TYPE
    elif ERROR_CODE_MISSING_CATEGORY in error_code:
        return "Category"
    return None


def _create_csv_error_from_location(
    location: Dict[str, Any],
    error_code: str,
    error_message: str,
    parameters: List[str]
) -> CSVRowError:
    """
    Create a CSVRowError from a location entry.
    
    Args:
        location: Location dictionary from API
        error_code: Error code from API
        error_message: Error message from API
        parameters: Error parameters from API
        
    Returns:
        CSVRowError object
    """
    line_number = location.get('line_number', 0)
    record_number = location.get('record_number', 0)
    column = _determine_error_column(error_code, parameters)
    
    return CSVRowError(
        row_number=line_number if line_number > 0 else record_number,
        column=column,
        error_message=error_message,
        value=parameters[0] if parameters else None
    )


def parse_api_error_messages(response: Dict[str, Any]) -> List[CSVRowError]:
    """
    Parse error messages from the API response.
    
    The API returns errors in the 'messages' field with structure:
    {
        'messages': {
            'resources': [
                {
                    'code': 'GIM00013E',
                    'message': 'Error message',
                    'parameters': ['param1', 'param2'],
                    'locations': [{'line_number': 1, 'record_number': 0}]
                }
            ]
        }
    }
    
    Args:
        response: API response dictionary
        
    Returns:
        List of CSVRowError objects
    """
    messages = response.get('messages', {})
    if not messages:
        return []
    
    resources = messages.get('resources', [])
    errors = []
    
    for resource in resources:
        error_code = resource.get('code', '')
        error_message = resource.get('message', '')
        parameters = resource.get('parameters', [])
        locations = resource.get('locations', [])
        
        for location in locations:
            csv_error = _create_csv_error_from_location(
                location, error_code, error_message, parameters
            )
            errors.append(csv_error)
    
    return errors


def extract_artifact_names_from_csv(csv_content: str) -> List[Dict[str, str]]:
    """
    Extract artifact names and types from CSV content.

    Args:
        csv_content: CSV content as string

    Returns:
        List of dicts with 'name' and 'type' keys
    """
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)
    artifacts = []
    for row in reader:
        name = (row.get("Name") or "").strip()
        artifact_type = (row.get(CSV_COLUMN_ARTIFACT_TYPE) or "").strip().lower()
        if name and artifact_type:
            artifacts.append({"name": name, "type": artifact_type})
    return artifacts


def split_csv_by_artifact_type(csv_content: str) -> Dict[str, str]:
    """
    Split CSV content by artifact type into separate CSV strings.
    
    Args:
        csv_content: Original CSV content with mixed artifact types
        
    Returns:
        Dictionary mapping artifact_type -> CSV content for that type
    """
    csv_file = io.StringIO(csv_content)
    reader = csv.DictReader(csv_file)
    
    if not reader.fieldnames:
        return {}
    
    headers = list(reader.fieldnames)
    rows_by_type: Dict[str, List[Dict[str, str]]] = {}
    
    for row in reader:
        artifact_type = row.get(CSV_COLUMN_ARTIFACT_TYPE, "").strip().lower()
        if artifact_type:
            if artifact_type not in rows_by_type:
                rows_by_type[artifact_type] = []
            rows_by_type[artifact_type].append(row)
    
    # Convert back to CSV strings
    result = {}
    for artifact_type, rows in rows_by_type.items():
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        result[artifact_type] = output.getvalue()
    
    return result


def build_import_endpoint(artifact_type: str) -> str:
    """
    Build the import endpoint URL for a specific artifact type.
    
    Args:
        artifact_type: The artifact type (glossary_term or category)
        
    Returns:
        The endpoint URL path
    """
    return f"/v3/governance_artifact_types/{artifact_type}/import"


async def import_csv_content(csv_content: str, merge_option: str = MERGE_OPTION_ALL) -> CSVImportResult:
    """
    Import CSV content into glossary using the API endpoint.
    
    This function:
    1. Validates the CSV
    2. Splits CSV by artifact type
    3. Uploads each artifact type to its specific endpoint
    4. Polls the status endpoint until completion for each
    5. Aggregates and returns the import results
    
    Args:
        csv_content: CSV content as string
        merge_option: Import merge option (all, specified, empty)
        
    Returns:
        CSVImportResult with aggregated import results
    """
    validation_result = validate_csv_content(csv_content)
    
    if not validation_result.success:
        return validation_result
    
    # Split CSV by artifact type
    csv_by_type = split_csv_by_artifact_type(csv_content)
    
    if not csv_by_type:
        return CSVImportResult(
            success=False,
            total_rows=validation_result.total_rows,
            categories_created=0,
            terms_created=0,
            categories_updated=0,
            terms_updated=0,
            errors=[CSVRowError(
                row_number=0,
                column=None,
                error_message="No valid artifact types found in CSV",
                value=None
            )],
            warnings=[],
            process_id=None,
            import_status='ERROR'
        )
    
    # Import artifact types with proper ordering:
    # 1. Categories first (if present) - terms may reference them
    # 2. Then terms and other types concurrently
    all_results = []
    
    # Import categories first if present
    if ARTIFACT_TYPE_CATEGORY in csv_by_type:
        LOGGER.info(f"Importing {ARTIFACT_TYPE_CATEGORY} artifacts first")
        category_result = await import_single_artifact_type(
            csv_by_type[ARTIFACT_TYPE_CATEGORY],
            ARTIFACT_TYPE_CATEGORY,
            merge_option
        )
        all_results.append(category_result)
    
    # Import remaining types concurrently
    remaining_types = {k: v for k, v in csv_by_type.items() if k != ARTIFACT_TYPE_CATEGORY}
    
    if remaining_types:
        LOGGER.info(f"Importing {len(remaining_types)} remaining artifact types concurrently")
        tasks = [
            import_single_artifact_type(type_csv_content, artifact_type, merge_option)
            for artifact_type, type_csv_content in remaining_types.items()
        ]
        remaining_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions from concurrent imports
        for result in remaining_results:
            if isinstance(result, Exception):
                LOGGER.error(f"Concurrent import failed: {str(result)}")
                all_results.append(CSVImportResult(
                    success=False,
                    total_rows=0,
                    categories_created=0,
                    terms_created=0,
                    categories_updated=0,
                    terms_updated=0,
                    errors=[CSVRowError(
                        row_number=0,
                        column=None,
                        error_message=f"Import failed: {str(result)}",
                        value=None
                    )],
                    warnings=[],
                    process_id=None,
                    import_status='ERROR'
                ))
            else:
                all_results.append(result)
    
    # Collect artifact names from original CSV for display
    all_artifact_names = extract_artifact_names_from_csv(csv_content)

    # Aggregate results
    return aggregate_import_results(all_results, validation_result.total_rows, all_artifact_names)


def _handle_no_process_id(response: Dict[str, Any]) -> CSVImportResult:
    """Handle case when API doesn't return a process_id."""
    api_errors = parse_api_error_messages(response)
    if api_errors:
        return CSVImportResult(
            success=False,
            total_rows=0,
            categories_created=0,
            terms_created=0,
            categories_updated=0,
            terms_updated=0,
            errors=api_errors,
            warnings=[],
            imported_artifacts=[],
            process_id=None,
            import_status='FAILED'
        )
    raise ServiceError("Import API did not return a process_id")


def _handle_polling_error(e: ServiceError, process_id: str) -> CSVImportResult:
    """Handle polling error."""
    LOGGER.error(f"Import polling failed: {str(e)}")
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
        warnings=[],
        imported_artifacts=[],
        process_id=process_id,
        import_status='TIMEOUT'
    )


def _extract_operation_counts(final_response: Dict[str, Any]) -> tuple[int, int, int, int]:
    """Extract operation counts from final response."""
    categories_created = 0
    categories_updated = 0
    terms_created = 0
    terms_updated = 0
    
    ops_count = final_response.get('operations_count', {})
    
    if ARTIFACT_TYPE_GLOSSARY_TERM in ops_count:
        term_ops = ops_count[ARTIFACT_TYPE_GLOSSARY_TERM]
        terms_created = term_ops.get(OPERATION_IMPORT_CREATE, 0)
        terms_updated = term_ops.get(OPERATION_IMPORT_MODIFY, 0)
    
    if ARTIFACT_TYPE_CATEGORY in ops_count:
        cat_ops = ops_count[ARTIFACT_TYPE_CATEGORY]
        categories_created = cat_ops.get(OPERATION_IMPORT_CREATE, 0)
        categories_updated = cat_ops.get(OPERATION_IMPORT_MODIFY, 0)
    
    return categories_created, categories_updated, terms_created, terms_updated


def _build_import_result(
    status: str,
    api_errors: List[CSVRowError],
    categories_created: int,
    categories_updated: int,
    terms_created: int,
    terms_updated: int,
    warnings: List[str],
    process_id: str,
    import_succeeded: bool
) -> CSVImportResult:
    """Build import result based on status and errors."""
    if api_errors:
        LOGGER.warning(f"Import completed with {len(api_errors)} error(s)")
        partial_success = (categories_created + terms_created + categories_updated + terms_updated) > 0
        
        return CSVImportResult(
            success=partial_success and import_succeeded,
            total_rows=0,
            categories_created=categories_created,
            terms_created=terms_created,
            categories_updated=categories_updated,
            terms_updated=terms_updated,
            errors=api_errors,
            warnings=warnings,
            imported_artifacts=[],
            process_id=process_id,
            import_status=status
        )
    
    return CSVImportResult(
        success=import_succeeded,
        total_rows=0,
        categories_created=categories_created,
        terms_created=terms_created,
        categories_updated=categories_updated,
        terms_updated=terms_updated,
        errors=[],
        warnings=warnings,
        imported_artifacts=[],
        process_id=process_id,
        import_status=status
    )


async def import_single_artifact_type(
    csv_content: str,
    artifact_type: str,
    merge_option: str = MERGE_OPTION_ALL
) -> CSVImportResult:
    """
    Import CSV content for a single artifact type.
    
    Args:
        csv_content: CSV content containing only one artifact type
        artifact_type: The artifact type (glossary_term or category)
        merge_option: Import merge option (all, specified, empty)
        
    Returns:
        CSVImportResult with import results for this artifact type
    """
    try:
        http_client = await get_async_http_client()
        
        # Prepare the file for upload
        csv_bytes = csv_content.encode('utf-8')
        files = {'file': (CSV_FILENAME, csv_bytes, CSV_CONTENT_TYPE)}
        
        # Build the URL with artifact type
        endpoint = build_import_endpoint(artifact_type)
        url = f"{settings.di_service_url}{endpoint}"
        params = {'merge_option': merge_option}
        
        # Get authorization token
        auth_token = await get_access_token()
        if not auth_token:
            raise ServiceError("Failed to obtain authorization token")
        
        headers = {'Authorization': auth_token}
        
        LOGGER.info(f"Importing {artifact_type} CSV to {url} with merge_option={merge_option}")
        
        response = await http_client.post_multipart(
            url=url,
            files=files,
            params=params,
            headers=headers
        )
        
        LOGGER.info(f"Import API initial response: {response}")
        
        # Extract process_id from response
        process_id = response.get('process_id') or response.get('processId')
        
        if not process_id:
            return _handle_no_process_id(response)
        
        LOGGER.info(f"Import process started with process_id={process_id}")
        
        # Poll for completion
        try:
            final_response = await poll_import_status(process_id)
            LOGGER.info(f"Full unparsed final_response from poll_import_status: {final_response}")
        except ServiceError as e:
            return _handle_polling_error(e, process_id)
        
        # Check final import status
        status = final_response.get('status', 'UNKNOWN')
        api_errors = parse_api_error_messages(final_response)
        import_succeeded = status in [IMPORT_STATUS_SUCCEEDED, IMPORT_STATUS_COMPLETED] and len(api_errors) == 0
        
        # Extract operation counts
        categories_created, categories_updated, terms_created, terms_updated = _extract_operation_counts(final_response)
        
        # Extract warnings
        warnings = final_response.get('warnings', [])
        
        return _build_import_result(
            status, api_errors, categories_created, categories_updated,
            terms_created, terms_updated, warnings, process_id, import_succeeded
        )
        
    except Exception as e:
        LOGGER.error(f"Failed to import {artifact_type} CSV: {str(e)}", exc_info=True)
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
                error_message=f"Import failed for {artifact_type}: {str(e)}",
                value=None
            )],
            warnings=[],
            process_id=None,
            import_status='ERROR'
        )


def aggregate_import_results(
    results: List[CSVImportResult],
    total_rows: int,
    artifact_names: Optional[List[Dict[str, str]]] = None,
) -> CSVImportResult:
    """
    Aggregate multiple import results into a single result.
    
    Args:
        results: List of CSVImportResult objects from different artifact types
        total_rows: Total number of rows in the original CSV
        artifact_names: Optional list of dicts with 'name' and 'type' from the original CSV
        
    Returns:
        Aggregated CSVImportResult
    """
    # Aggregate counts
    categories_created = sum(r.categories_created for r in results)
    categories_updated = sum(r.categories_updated for r in results)
    terms_created = sum(r.terms_created for r in results)
    terms_updated = sum(r.terms_updated for r in results)
    
    # Aggregate errors and warnings
    all_errors = []
    all_warnings = []
    process_ids = []
    
    for result in results:
        all_errors.extend(result.errors)
        all_warnings.extend(result.warnings)
        if result.process_id:
            process_ids.append(result.process_id)
    
    # Determine overall success
    success = all(r.success for r in results) and len(all_errors) == 0
    
    # Determine overall status
    statuses = [r.import_status for r in results if r.import_status]
    if all(s == IMPORT_STATUS_SUCCEEDED for s in statuses):
        import_status = IMPORT_STATUS_SUCCEEDED
    elif any(s == 'TIMEOUT' for s in statuses):
        import_status = 'TIMEOUT'
    elif any(s == 'ERROR' for s in statuses):
        import_status = 'ERROR'
    else:
        import_status = IMPORT_STATUS_COMPLETED

    # Build imported_artifacts list from original CSV names when import succeeded
    imported_artifacts: List[Dict[str, str]] = []
    if success and artifact_names:
        imported_artifacts = list(artifact_names)
    
    return CSVImportResult(
        success=success,
        total_rows=total_rows,
        categories_created=categories_created,
        terms_created=terms_created,
        categories_updated=categories_updated,
        terms_updated=terms_updated,
        errors=all_errors,
        warnings=all_warnings,
        imported_artifacts=imported_artifacts,
        process_id=', '.join(process_ids) if process_ids else None,
        import_status=import_status
    )