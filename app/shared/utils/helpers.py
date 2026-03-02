# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

import json
import re

from difflib import get_close_matches
from typing import Callable, List, Optional, Union
from urllib.parse import urlparse, parse_qs
from uuid import UUID

from app.core.settings import settings
from app.shared.exceptions.base import ServiceError


def is_none(value: object) -> bool:
    """
    This function takes a single value and checks if it is None or should be treated as None

    Args:
        value (object): A value to be tested

    Returns:
        bool: Information if value is or should be treated as None
    """
    return value is None or value == "None"


def is_uuid(id: str):
    """
    This function takes a single string and checks if it is a valid UUID

    Args:
        id (str): A value to be tested

    Returns:
        None if valid UUID

    Raises:
        ServiceError: If the string is not a valid UUID
    """
    try:
        UUID(id, version=4)
    except ValueError:
        raise ServiceError(f"'{id}' is not valid UUID")


def is_uuid_bool(id: str) -> bool:
    """
    Check if a string is a valid UUID.
    
    Args:
        id: String to check
        
    Returns:
        bool: True if valid UUID, False otherwise
    """
    try:
        UUID(id, version=4)
        return True
    except (ValueError, AttributeError):
        return False


async def confirm_uuid(uuid_or_str: str, find_function: Callable) -> str:
    try:
        is_uuid(uuid_or_str)
        return uuid_or_str
    except ServiceError:
        return await find_function(uuid_or_str)


def _is_valid_lineage_id(lineage_id: str) -> bool:
    """
    Check if a string is a valid lineage ID (64-character hexadecimal string).

    Args:
        lineage_id (str): The string to validate

    Returns:
        bool: True if the string is a valid lineage ID, False otherwise
    """
    return isinstance(lineage_id, str) and bool(
        re.match(r"^[0-9a-f]{64}$", lineage_id.lower())
    )


def _try_parse_json(json_str: str) -> Optional[List[str]]:
    """
    Attempts to parse a string as JSON and validate it's a list.
    
    This function safely tries to convert a JSON string to a Python list.
    If parsing fails or the result is not a list, it returns None.
    
    Args:
        json_str (str): The JSON-formatted string to parse
        
    Returns:
        Optional[List[str]]: A list of strings if parsing succeeds and the result
                            is a list, None if parsing fails or result is not a list
                            
    Raises:
        No exceptions are raised as errors are caught internally
    """
    try:
        parsed_value = json.loads(json_str)
        if isinstance(parsed_value, list):
            return parsed_value
    except json.JSONDecodeError:
        pass
    return None


def _try_parse_with_normalization(json_str: str) -> Optional[List[str]]:
    """
    Try to parse a string as JSON after normalizing quotes.

    Args:
        json_str: The string to parse

    Returns:
        List[str] if parsing succeeds and result is a list, None otherwise
    """
    try:
        normalized_value = json_str.replace("'", '"')
        normalized_value = normalized_value.replace(r"\"", '"')
        return _try_parse_json(normalized_value)
    except json.JSONDecodeError:
        return None


def _get_values_to_check(value) -> List[str]:
    """
    Convert a value to a list of strings to check.

    Args:
        value: The value (string, list of strings, or JSON string representation of a list)

    Returns:
        List[str]: List of strings to check

    Raises:
        ServiceError: If the value is neither a string nor a list
    """
    if isinstance(value, str):
        if value.strip().startswith("[") and value.strip().endswith("]"):
            parsed_list = _try_parse_json(value)
            if parsed_list:
                return parsed_list

            parsed_list = _try_parse_with_normalization(value)
            if parsed_list:
                return parsed_list
        return [value]
    elif isinstance(value, list):
        return value
    else:
        raise ServiceError(
            f"Argument '{value}' must be a string or list of strings, got {type(value).__name__}"
        )


def are_lineage_ids(values: Union[str, List[str]]):
    """
    Check if all values are valid lineage IDs.

    Args:
        values: A list of values to check.

    Returns:
        bool: Information if all values are valid lineage IDs
    """
    values_to_check = _get_values_to_check(values)

    # Check each lineage ID
    for lineage_id in values_to_check:
        if not isinstance(lineage_id, str):
            raise ServiceError(
                f"Lineage ID must be a string, got {type(lineage_id).__name__}"
            )

        if not _is_valid_lineage_id(lineage_id):
            raise ServiceError(
                f"'{lineage_id}' is not a valid lineage ID. Expected a 64-character hexadecimal string."
            )


def get_closest_match(word_list_with_id: list, search_word: str) -> str | None:
    """
    This function takes a list of objects, where each objects contains a 'name' and 'id' key,
    and a search word as input. It returns the 'id' of the objects in the list whose 'name' is the closest match
    to the search word, based on a fuzzy matching algorithm.

    Args:
        word_list_with_id (list): A list of objects, each containing 'name' and 'id' keys.
        search_word (str): The word to search for in the list of names.

    Returns:
        str | None: The 'id' of the dictionary in the list whose 'name' is the closest match to the search word,
                   or None if no match is found.
    """
    closest_name = get_close_matches(
        word=search_word.lower(),
        possibilities=[name["name"].lower() for name in word_list_with_id],
        n=1,
        cutoff=0.6,
    )
    if closest_name:
        for words in word_list_with_id:
            if str(words.get("name")).lower() == closest_name[0].lower():
                return str(words.get("id"))
    return None


def find_exact_matches(candidates: List[dict], search_fields: List[str], search_lower: str) -> List[dict]:
    """Find candidates with exact field matches (case-insensitive)."""
    return [
        candidate for candidate in candidates
        if any(candidate.get(field) and str(candidate.get(field)).lower() == search_lower
               for field in search_fields)
    ]


def calculate_best_token_score(search_tokens: List[str], candidate_tokens: List[str], cutoff: float) -> float:
    """
    Calculate the best match score between search tokens and candidate tokens.
    
    Scoring hierarchy:
    - Exact match: 1.0
    - Starts with: 0.95
    - Contains: 0.85
    - Fuzzy match: 0.7
    """
    max_score = 0.0
    for search_token in search_tokens:
        for candidate_token in candidate_tokens:
            if candidate_token == search_token:
                max_score = max(max_score, 1.0)
            elif candidate_token.startswith(search_token):
                max_score = max(max_score, 0.95)
            elif search_token in candidate_token:
                max_score = max(max_score, 0.85)
            elif get_close_matches(search_token, [candidate_token], n=1, cutoff=cutoff):
                max_score = max(max_score, 0.7)
    return max_score


def perform_token_based_matching(
    candidates: List[dict],
    search_tokens: List[str],
    search_fields: List[str],
    cutoff: float,
    max_results: int
) -> List[dict]:
    """Score candidates based on token matching and return top matches."""
    candidate_scores = []
    
    for candidate in candidates:
        # Combine search fields into searchable text
        text_parts = [str(candidate.get(field)) for field in search_fields if candidate.get(field)]
        if not text_parts:
            continue
        
        search_text = " ".join(text_parts).lower()
        candidate_tokens = [t for t in re.split(r'[._+\-@\s]+', search_text) if t]
        
        # Calculate best match score using helper function
        max_score = calculate_best_token_score(search_tokens, candidate_tokens, cutoff)
        
        if max_score >= cutoff:
            candidate_scores.append((candidate, max_score))
    
    # Sort by score and return top matches
    candidate_scores.sort(key=lambda x: x[1], reverse=True)
    return [candidate for candidate, _ in candidate_scores[:max_results]]

def get_exact_or_fuzzy_matches(
    search_word: str,
    candidates: List[dict],
    search_fields: Optional[List[str]] = None,
    max_results: int = 10,
    cutoff: float = 0.6
) -> List[dict]:
    """
    Perform exact match first, then fall back to token-based fuzzy matching.
    Returns multiple matches to allow caller to handle ambiguity.
    
    This function extracts tokens from email addresses and names to perform
    intelligent matching
    
    Args:
        search_word: The word to search for
        candidates: List of candidate dictionaries to search through
        search_fields: List of field names to search in (defaults to ["name"])
        max_results: Maximum number of fuzzy matches to return (default 10)
        cutoff: Minimum similarity score for fuzzy matching (0.0-1.0, default 0.6)
        
    Returns:
        List[dict]: List of matching candidate dictionaries
    """
    if not search_word or not candidates:
        return []
    
    search_fields = search_fields or ["name"]
    search_lower = search_word.lower().strip()
    
    # Try exact match first
    exact_matches = find_exact_matches(candidates, search_fields, search_lower)
    if exact_matches:
        return exact_matches
    
    # Extract and validate search tokens
    search_tokens = [t for t in re.split(r'[._+\-@\s]+', search_lower) if t and len(t) > 1]
    if not search_tokens:
        return []
    
    # Perform token-based fuzzy matching
    return perform_token_based_matching(candidates, search_tokens, search_fields, cutoff, max_results)

def get_project_or_space_type_based_on_context() -> str | None:
    """
    Returns the project or space type based on the current context.
    
    Returns:
        str | None: The project/space type ('cpd' or 'wx') or None
    """
    context = settings.di_context
    if context in ["cpdaas", "cpd"]:
        return "cpd"
    elif context == "df":
        return "wx"
    return None

def append_context_to_url(url: str, context: str | None = None) -> str:
    """
    Appends the context parameter to a URL if it doesn't already have one.
    Validates that the context is appropriate for the current environment mode.

    Args:
        url (str): The URL to append the context parameter to.
        context (str | None, optional): The context value to append. 
            If None, uses settings.di_context. Defaults to None.

    Returns:
        str: The URL with the context parameter appended.

    Raises:
        ValueError: If the context is not valid for the environment mode.
    """
    # Use provided context or fall back to settings.di_context
    context_value = context if context is not None else settings.di_context
    
    # Validate that the context is valid for the environment mode
    if context_value not in settings.valid_contexts:
        valid_contexts = ", ".join(settings.valid_contexts)
        raise ValueError(
            f"Invalid context '{context_value}' for environment mode '{settings.di_env_mode}'. "
            f"Valid contexts are: {valid_contexts}"
        )

    # Parse the URL to check if it already has a context parameter
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # If the URL already has a context parameter, return it as-is
    if "context" in query_params:
        return url

    # Determine the separator to use (? or &)
    separator = "&" if parsed_url.query else "?"

    # Append the context parameter with the appropriate separator
    return f"{url}{separator}context={context_value}"


def is_valid_iso_date(date: str) -> bool:
    """
    Check if a given date string complies with ISO-8601 format.
    
    Uses datetime.fromisoformat() for common formats with regex fallback for special cases.
    
    Supports various ISO-8601 formats including:
    - Complete date-time: YYYY-MM-DDTHH:MM:SSZ, YYYY-MM-DDTHH:MM:SS+00:00
    - Date only: YYYY-MM-DD
    - Year and month with timezone: YYYY-MMZ, YYYY-MM+00:00
    - Year only with timezone: YYYYZ, YYYY+00:00
    - Week date with timezone: YYYY-WwwZ, YYYY-Www-DZ (e.g., 2025-W13Z, 2025-W13-1Z)
    - Ordinal date with timezone: YYYY-DDDZ (e.g., 2025-123Z)
    - With timezone offsets: +HH:MM, -HH:MM, Z (required for special formats)
    - With fractional seconds: .SSS, .SSSSSS
    
    Args:
        date (str): The date string to validate
        
    Returns:
        bool: True if the string is a valid ISO-8601 date, False otherwise
    """
    if not isinstance(date, str) or not date:
        return False
    
    date = date.strip()
    
    # Reject space-separated datetime format (e.g., "2025-10-23 08:54:02")
    # ISO-8601 requires 'T' as the separator between date and time
    if ' ' in date and 'T' not in date:
        return False
    
    # Try datetime.fromisoformat() first for common formats
    # This handles most standard ISO-8601 datetime and date formats
    try:
        from datetime import datetime
        datetime.fromisoformat(date.replace('Z', '+00:00'))
        return True
    except (ValueError, AttributeError):
        pass
    
    # Fallback to regex for special ISO-8601 formats not supported by fromisoformat but supported by backend
    # These include: week dates, ordinal dates, year-month, and year-only formats
    special_patterns = [
        # Week date format with day (YYYY-Www-D)
        r'^\d{4}-W\d{2}-[1-7](?:Z|[+-]\d{2}:\d{2})$',
        # Week date format without day (YYYY-Www)
        r'^\d{4}-W\d{2}(?:Z|[+-]\d{2}:\d{2})$',
        # Ordinal date (YYYY-DDD)
        r'^\d{4}-\d{3}(?:Z|[+-]\d{2}:\d{2})$',
        # Year and month (YYYY-MM)
        r'^\d{4}-\d{2}(?:Z|[+-]\d{2}:\d{2})$',
        # Year only with timezone (YYYYZ or YYYY+/-HH:MM)
        r'^\d{4}(?:Z|[+-]\d{2}:\d{2})$',
    ]
    
    # Check if the date matches any of the special patterns
    for pattern in special_patterns:
        if re.match(pattern, date):
            return True
    
    return False

def verify_dates(dates=None):
    """
    Verify and parse dates parameter into a list of two ISO 8601 dates.
    
    Args:
        dates: Can be None, a JSON string, or a list of two dates
        
    Returns:
        List of two ISO 8601 date strings, or None if dates is None
    """
    if dates:
        if isinstance(dates, str):
            dates_verified = parse_string_date(dates)
        elif isinstance(dates, list) and len(dates) == 2:
            if is_valid_iso_date(dates[0]) and is_valid_iso_date(dates[1]):
                dates_verified = dates
            else:
                dates_verified = None
        else:
            dates_verified = None
        return dates_verified
    return None

def parse_string_date(dates):
    """
    Parse a string containing dates into a list of two ISO 8601 dates.
    
    Handles multiple formats:
    - JSON array: '["2025-10-23T08:54:02.17Z","2025-10-14T06:09:58.423Z"]'
    - Space-separated: "2025-10-23T08:54:02.17Z 2025-10-14T06:09:58.423Z"
    - Comma-separated: "2025-10-23T08:54:02.17Z,2025-10-14T06:09:58.423Z"
    
    Args:
        dates: String containing two dates
        
    Returns:
        List of two ISO 8601 date strings
        
    Raises:
        ServiceError: If dates cannot be parsed or don't contain exactly 2 valid dates
    """
    # First try JSON parsing
    try:
        parsed_dates = json.loads(dates)
        if isinstance(parsed_dates, list) and len(parsed_dates) == 2:
            if is_valid_iso_date(parsed_dates[0]) and is_valid_iso_date(parsed_dates[1]):
                return parsed_dates
    except json.JSONDecodeError:
        pass  # Not JSON, try other formats
    
    # Try splitting by common separators
    for separator in [',', ' ', ';', '|']:
        parts = [p.strip() for p in dates.split(separator) if p.strip()]
        if len(parts) == 2:
            if is_valid_iso_date(parts[0]) and is_valid_iso_date(parts[1]):
                return parts
    
    # If we get here, we couldn't parse the dates
    raise ServiceError(
        f"dates parameter must contain exactly 2 ISO 8601 dates. "
        f"Supported formats: JSON array, comma-separated, or space-separated. "
        f"Received: {dates}"
    )

def parse_list_of_ids(ids):
    if isinstance(ids, str):
        req_ids = "".join(
            char for char in ids if char.isalnum() or char == ","
        )
        try:
            req_ids = json.loads(req_ids)
        except Exception:
            req_ids = [s.strip() for s in req_ids.split(",")]
    else:
        req_ids = ids
    return req_ids
