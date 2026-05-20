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
Utility functions for workflow task processing.

This module provides common utility functions for parsing and transforming
workflow task data, including task title parsing and variable conversion.
"""

import json
from typing import Optional

from app.shared.logging import LOGGER


def _convert_variables_to_dict(variables_list) -> dict:
    """
    Convert variables from list format to dictionary.
    
    Args:
        variables_list: Variables in list or dict format
        
    Returns:
        Dictionary mapping variable names to values
    """
    if isinstance(variables_list, dict):
        return variables_list
    
    variables_dict = {}
    if isinstance(variables_list, list):
        for var in variables_list:
            # Validate that both 'name' and 'value' keys exist before accessing
            if isinstance(var, dict) and 'name' in var:
                # Only add if 'value' key exists, otherwise skip
                if 'value' in var:
                    variables_dict[var['name']] = var['value']
    return variables_dict


def _parse_task_title_from_json(task_title_raw: str) -> Optional[str]:
    """
    Parse task title from JSON template format.
    
    Args:
        task_title_raw: Raw task title string in JSON format
        
    Returns:
        Parsed task title or original string if parsing fails
    """
    try:
        task_title_json = json.loads(task_title_raw.strip())
        default_message = task_title_json.get("defaultMessage", "")
        artifact_name = task_title_json.get("artifactName")
        artifact_type_key = task_title_json.get("§artifactType")
        
        # If defaultMessage is empty, return empty string
        if not default_message:
            return ""
        
        # Return original raw string if required fields are missing or empty
        if not artifact_name or not artifact_type_key:
            return task_title_raw
        
        # Extract artifact type from the translation key
        artifact_type = "artifact"
        if "glossary_term" in artifact_type_key:
            artifact_type = "Business term"
        elif "data_class" in artifact_type_key:
            artifact_type = "Data class"
        elif "category" in artifact_type_key:
            artifact_type = "Category"
        
        # Replace placeholders in the template
        return default_message.replace("{artifactType}", artifact_type).replace("{artifactName}", artifact_name)
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        LOGGER.debug(f"Failed to parse task_title JSON: {e}")
        return task_title_raw

# Made with Bob
