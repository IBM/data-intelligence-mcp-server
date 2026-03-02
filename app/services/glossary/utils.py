# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Utility functions for glossary service operations.

This module provides common utilities for processing and cleaning glossary-related data.
"""

import re
from typing import Any


def is_empty(value: Any) -> bool:
    """
    Check if a value is considered empty.
    
    A value is considered empty if it is:
    - An empty string ("")
    - None
    - An empty dictionary ({})
    - An empty list ([])
    
    Args:
        value: The value to check
        
    Returns:
        True if the value is empty, False otherwise
    """
    return value in ("", None, {}, [])


def normalize_key(key: str) -> str:
    """
    Normalize a string key to a consistent format.
    
    This function:
    1. Replaces non-alphanumeric characters with underscores
    2. Converts camelCase to snake_case
    3. Removes consecutive underscores
    4. Converts to lowercase
    5. Strips leading/trailing underscores
    
    Args:
        key: The string key to normalize
        
    Returns:
        Normalized key in snake_case format
    """
    # Replace non-alphanumeric characters with underscores
    key = re.sub(r"[^0-9a-zA-Z]+", "_", key)
    
    # Convert camelCase to snake_case
    key = re.sub(r"([a-z])([A-Z])", r"\1_\2", key)
    
    # Remove consecutive underscores
    key = re.sub(r"_+", "_", key)
    
    # Convert to lowercase and strip leading/trailing underscores
    return key.lower().strip("_")