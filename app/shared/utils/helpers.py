# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from difflib import get_close_matches
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
    try:
        UUID(id, version=4)
    except ValueError:
        raise ServiceError(f"'{id}' is not valid UUID")


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
    if 'context' in query_params:
        return url
    
    # Determine the separator to use (? or &)
    separator = '&' if parsed_url.query else '?'
    
    # Append the context parameter with the appropriate separator
    return f"{url}{separator}context={settings.di_context}"