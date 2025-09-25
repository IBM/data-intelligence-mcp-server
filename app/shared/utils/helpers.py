# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from difflib import get_close_matches
from uuid import UUID

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


def get_closest_match(word_list_with_id: list, search_word: str) -> str:
    """
    This function takes a list of objects, where each objects contains a 'name' and 'id' key,
    and a search word as input. It returns the 'id' of the objects in the list whose 'name' is the closest match
    to the search word, based on a fuzzy matching algorithm.

    Args:
        word_list_with_id (list): A list of objects, each containing 'name' and 'id' keys.
        search_word (str): The word to search for in the list of names.

    Returns:
        str: The 'id' of the dictionary in the list whose 'name' is the closest match to the search word.
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