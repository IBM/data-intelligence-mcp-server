# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Utility functions for extracting source data from search results."""

from typing import Any, List, Optional


def _should_skip_field(field_path: str) -> bool:
    """
    Check if a field should be skipped during source data extraction.
    
    Args:
        field_path: The field path to check
        
    Returns:
        True if the field should be skipped, False otherwise
    """
    if field_path == "artifact_id":
        return True
    if field_path in ["metadata", "entity", "entity.assets"]:
        return True
    return False


def _get_nested_value(row: dict, field_path: str) -> Optional[Any]:
    """
    Navigate through nested structure to get a value.
    
    Args:
        row: The data dictionary to navigate
        field_path: Dot-separated path (e.g., "metadata.modified_by")
        
    Returns:
        The value at the path, or None if not found
    """
    parts = field_path.split(".")
    value = row
    
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    
    return value


def _set_nested_value(target: dict, field_path: str, value: Any) -> None:
    """
    Set a value in a nested dictionary structure, creating intermediate dicts as needed.
    
    Args:
        target: The target dictionary to modify
        field_path: Dot-separated path (e.g., "metadata.modified_by")
        value: The value to set
    """
    parts = field_path.split(".")
    current = target
    
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    
    current[parts[-1]] = value


def extract_source_data(row: dict, source_fields: List[str]) -> Optional[dict]:
    """
    Extract only the fields that were requested in the _source section of the query.
    Excludes full 'metadata' and 'entity' objects but includes their nested fields if requested.
    
    Args:
        row: The search result row
        source_fields: List of field paths requested in _source (e.g., ['metadata.modified_by', 'custom_attributes'])
        
    Returns:
        Dictionary containing only the requested fields
    """
    if not source_fields:
        return {}
    
    source_data = {}
    
    for field_path in source_fields:
        if _should_skip_field(field_path):
            continue
        
        # Handle nested field paths (e.g., "metadata.modified_by")
        if "." in field_path:
            value = _get_nested_value(row, field_path)
            if value is not None:
                _set_nested_value(source_data, field_path, value)
        else:
            # Handle top-level fields (not metadata or entity)
            if field_path in row:
                source_data[field_path] = row[field_path]
    
    return source_data if source_data else None

# Made with Bob
