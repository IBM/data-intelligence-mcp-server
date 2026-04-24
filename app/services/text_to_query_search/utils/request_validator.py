# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.services.text_to_query_search.models.text2query_search_asset import (
    TextToQuerySearchAssetRequest,
)
from app.services.text_to_query_search.constants import (
    VALID_ARTIFACT_TYPES,
    VALID_CONTAINER_TYPES,
    VALID_NAMED_ENTITIES,
)
from app.shared.utils.helpers import is_none
from app.shared.logging import LOGGER
from app.shared.exceptions.base import ServiceError

def _validate_search_prompt(search_prompt: str) -> None:
    """Validate that search prompt is not empty."""
    if not search_prompt or search_prompt.strip() == "":
        error_msg = "Search prompt cannot be empty. Please provide a valid search term."
        LOGGER.error(error_msg)
        raise ServiceError(error_msg)


def _validate_container_type(container_type: str | None) -> None:
    """Validate that container type is valid."""
    if not is_none(container_type):
        if container_type not in VALID_CONTAINER_TYPES:
            error_msg = f"Invalid container_type: '{container_type}'. Valid values are: {VALID_CONTAINER_TYPES}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)


def _validate_artifact_types(artifact_types: list[str] | None) -> None:
    """Validate that artifact types are valid."""
    if artifact_types:
        invalid_types = [
            t for t in artifact_types if t not in VALID_ARTIFACT_TYPES
        ]
        if invalid_types:
            error_msg = f"Invalid artifact_type(s): {invalid_types}. Valid values are: {VALID_ARTIFACT_TYPES}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)


def _validate_names_mapping(names_mapping: list[dict] | None) -> None:
    """Validate names_mapping structure if provided."""
    if not names_mapping:
        return
    
    valid_entity_types = VALID_NAMED_ENTITIES
    
    for idx, entity in enumerate(names_mapping):
        if not isinstance(entity, dict):
            error_msg = f"Invalid names_mapping entry at index {idx}: must be a dictionary"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)
        
        if "name" not in entity or "type" not in entity:
            error_msg = f"Invalid names_mapping entry at index {idx}: must contain 'name' and 'type' keys"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)
        
        if entity["type"] not in valid_entity_types:
            error_msg = f"Invalid entity type '{entity['type']}' in names_mapping at index {idx}. Valid types are: {valid_entity_types}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)


def _preprocess_current_user_references(request: TextToQuerySearchAssetRequest) -> None:
    """
    Always add current user details to names_mapping by default if no user entity is provided.
    This ensures the query generation API always has access to current user context.
    
    Args:
        request: The search request to preprocess (modified in place)
    """
    # Check if user mapping already exists in names_mapping
    if request.names_mapping:
        user_types = {e.get('type') for e in request.names_mapping}
        if 'user' in user_types:
            return
    
    # Add default current user mapping
    user_mapping = {"name": "me", "type": "user"}
    if request.names_mapping is None:
        request.names_mapping = [user_mapping]
    else:
        request.names_mapping.append(user_mapping)
    
    LOGGER.info(f"Added default current user mapping to names_mapping: {user_mapping}")


def validate_request(request: TextToQuerySearchAssetRequest) -> None:
    """
    Validate and preprocess search request parameters.
    
    Preprocessing includes:
    - Always adding current user details to names_mapping by default (if no user entity provided)
    
    Args:
        request: The search request to validate and preprocess
        
    Raises:
        ServiceError: If any validation fails
    """
    _validate_search_prompt(request.search_prompt)
    _validate_container_type(request.container_type)
    _validate_artifact_types(request.artifact_types)
    _validate_names_mapping(request.names_mapping)
    
    # Preprocess: add default current user mapping
    _preprocess_current_user_references(request)

# Made with Bob
