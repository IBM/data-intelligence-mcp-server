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
        bool: Information if string is a valid UUID
    """
    try:
        UUID(id, version=4)
    except ValueError:
        raise ServiceError(f"'{id}' is not valid UUID")


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


def append_context_to_url(url: str) -> str:
    """
    Appends the context parameter to a URL if it doesn't already have one.
    Validates that the context is appropriate for the current environment mode.

    Args:
        url (str): The URL to append the context parameter to.

    Returns:
        str: The URL with the context parameter appended.

    Raises:
        ValueError: If the current di_context is not valid for the environment mode.
    """
    # Validate that the current context is valid for the environment mode
    if settings.di_context not in settings.valid_contexts:
        valid_contexts = ", ".join(settings.valid_contexts)
        raise ValueError(
            f"Invalid context '{settings.di_context}' for environment mode '{settings.di_env_mode}'. "
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
    return f"{url}{separator}context={settings.di_context}"
