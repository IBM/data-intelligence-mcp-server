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
import re
from typing import Optional, Union

from app.shared.logging import LOGGER

_PLACEHOLDER_TYPE = "{artifactType}"
_PLACEHOLDER_NAME = "{artifactName}"

_ARTIFACT_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("glossary_term", "Business term"),
    ("data_class", "Data class"),
    ("category", "Category"),
]


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


def _resolve_artifact_type_key(task_title_json: dict) -> tuple[str, Optional[str]]:
    """
    Extract the artifact-type translation key and, when available, a ready-to-use
    sanitised display string from Schema B's nested artifactType object.

    Returns:
        (artifact_type_key, display_override) where display_override is a
        sanitised human-readable string (Schema B fast path) or None.
    """
    # Schema A: §artifactType is a plain translation-key string
    artifact_type_key: str = task_title_json.get("§artifactType", "")
    if artifact_type_key:
        return artifact_type_key, None

    # Schema B: artifactType is a nested object {"id": "...", "defaultMessage": "..."}
    artifact_type_obj = task_title_json.get("artifactType", {})
    if not isinstance(artifact_type_obj, dict):
        return "", None

    display = artifact_type_obj.get("defaultMessage", "")
    if display:
        sanitised = re.sub(r"[^\w\s\-]", "", str(display))
        return "", sanitised

    return artifact_type_obj.get("id", ""), None


def _map_artifact_type_key(artifact_type_key: str) -> str:
    """Map a translation key to a human-readable artifact type label."""
    for keyword, label in _ARTIFACT_TYPE_KEYWORDS:
        if keyword in artifact_type_key:
            return label
    return "artifact"


def _apply_placeholders(template: str, artifact_type: str, artifact_name: str) -> str:
    """Substitute both placeholders in a title template."""
    return (
        template
        .replace(_PLACEHOLDER_TYPE, artifact_type)
        .replace(_PLACEHOLDER_NAME, artifact_name)
    )


def _parse_task_title_from_json(task_title_raw: Union[str, dict]) -> Optional[str]:
    """
    Parse task title from JSON template format.

    Two schemas are emitted by different API endpoints:

    Schema A  (inbox list / task_utils format) — §artifactType is a plain string:
        {"defaultMessage": "Send for approval {artifactType} {artifactName}",
         "§artifactType": "wkc-governance-workflows.default.artifactType.glossary_term",
         "artifactName": "My Term"}

    Schema B  (single-task GET format) — artifactType is a nested object:
        {"defaultMessage": "Send for approval {artifactType} {artifactName}",
         "artifactType": {"id": "...glossary_term", "defaultMessage": "Business term"},
         "artifactName": "My Term"}

    Args:
        task_title_raw: Raw task title — either a JSON string or an already-parsed dict.

    Returns:
        Human-readable title string, or None / empty string on failure.
    """
    try:
        task_title_json: dict = (
            task_title_raw if isinstance(task_title_raw, dict)
            else json.loads(task_title_raw.strip())
        )

        default_message: str = task_title_json.get("defaultMessage", "")
        if not default_message:
            return ""

        artifact_name: str = task_title_json.get("artifactName") or ""
        artifact_type_key, display_override = _resolve_artifact_type_key(task_title_json)

        # Schema B fast path: sanitised display string already resolved
        if display_override is not None:
            return _apply_placeholders(default_message, display_override, artifact_name)

        # Nothing useful — strip placeholders and return bare message
        if not artifact_type_key and not artifact_name:
            return _apply_placeholders(default_message, "", artifact_name).strip()

        return _apply_placeholders(
            default_message,
            _map_artifact_type_key(artifact_type_key),
            artifact_name,
        )
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        LOGGER.debug(f"Failed to parse task_title JSON: {e}")
        return task_title_raw if isinstance(task_title_raw, str) else None

# Made with Bob
