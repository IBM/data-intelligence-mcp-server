# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Callable, Awaitable, Literal, List
from app.shared.logging import LOGGER
from app.services import tool_utils
from app.services.tool_utils import find_category_id, find_connection_id, find_metadata_enrichment_id, find_metadata_import_id
from app.shared.exceptions.base import ServiceError
from app.services.text_to_query_search.constants import CONTAINER_TYPE_PROJECT_AND_CATALOG

# Type alias for context requirements
ContextRequirement = Literal["container_id", "container_id_and_type", None]

# Mapping of entity types to their context requirements and resolver functions
ENTITY_RESOLVERS: dict[str, tuple[ContextRequirement, Callable]] = {
    "connection": ("container_id_and_type", find_connection_id),
    "metadata_import": ("container_id", find_metadata_import_id),
    "metadata_enrichment_area": ("container_id", find_metadata_enrichment_id),
    "category": (None, find_category_id)
}


def _validate_context(
    entity_name: str,
    entity_type: str,
    required_context: ContextRequirement,
    container_id: str | None,
    container_type: str | None,
) -> None:
    """
    Validate that required context is available for entity resolution.
    
    Args:
        entity_name: Name of the entity being resolved
        entity_type: Type of the entity
        required_context: What context is required ('container_id', 'container_id_and_type', or None)
        container_id: The container ID (may be None)
        container_type: The container type (may be None)
        
    Raises:
        ServiceError: If required context is not available
    """
    if required_context == "container_id_and_type":
        if not container_id or not container_type:
            raise ServiceError(
                f"Cannot resolve {entity_type} '{entity_name}': container context not available"
            )
    elif required_context == "container_id" and not container_id:
        raise ServiceError(
            f"Cannot resolve {entity_type} '{entity_name}': project context not available"
        )


async def find_container_id(container_name: str, container_type: str) -> str:
    """Find container id for given container name and type.
    
    Args:
        container_name: Name of the container to find.
        container_type: Type of container ('catalog', 'project', or 'project_and_catalog').
        
    Returns:
        The container id.
        
    Raises:
        ServiceError: If container is not found or container_type is invalid.
    """
    match container_type:
        case "catalog":
            return await tool_utils.find_catalog_id(container_name)
        case "project":
            return await tool_utils.find_project_id(container_name)
        case c if c == CONTAINER_TYPE_PROJECT_AND_CATALOG:
            return await tool_utils.find_project_or_catalog_id(container_name)
        case _:
            error_msg = f"Unknown container_type '{container_type}'. Must be 'catalog', 'project', or '{CONTAINER_TYPE_PROJECT_AND_CATALOG}'"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg)


async def _resolve_single_entity(
    entity: dict,
    container_id: str | None,
    container_type: str | None,
) -> dict | None:
    """
    Resolve a single entity from names_mapping to include its ID.
    
    Returns:
        Dict with name, type, and id if successful, None otherwise
    """
    entity_name = entity.get("name")
    entity_type = entity.get("type")
    
    if not entity_name or not entity_type:
        LOGGER.warning(
            "Skipping invalid names_mapping entry: %s (missing name or type)",
            entity
        )
        return None
    
    # Check if entity type is supported
    if entity_type not in ENTITY_RESOLVERS:
        LOGGER.warning(
            "Unsupported entity type '%s' for entity '%s'. Supported types: %s",
            entity_type,
            entity_name,
            ", ".join(ENTITY_RESOLVERS.keys()),
        )
        return None
    
    # Get resolver configuration
    required_context, resolver_func = ENTITY_RESOLVERS[entity_type]
    
    # Validate context availability
    _validate_context(entity_name, entity_type, required_context, container_id, container_type)
    
    # Call the appropriate resolver function
    if required_context == "container_id_and_type":
        entity_id = await resolver_func(entity_name, container_id, container_type)
    elif required_context == "container_id":
        entity_id = await resolver_func(entity_name, container_id)
    elif required_context is None:
        entity_id = await resolver_func(entity_name)
    else:
        raise ValueError(
            f"Unsupported required context '{required_context}' for entity '{entity_name}'"
        )
    
    if entity_id:
        return {"name": entity_name, "type": entity_type, "id": entity_id}
    
    # Log when entity is not found
    LOGGER.warning("Entity '%s' of type '%s' not found", entity_name, entity_type)
    return None


async def resolve_names_mapping_to_ids(
    names_mapping: List[dict] | None,
    container_id: str | None,
    container_type: str | None,
) -> List[dict]:
    """
    Resolve entity names to IDs for names_mapping parameter.
    
    Args:
        names_mapping: List of dicts with 'name' and 'type' keys
        container_id: Container ID (project or catalog) for context
        container_type: Container type ('project' or 'catalog')
        
    Returns:
        List of dicts with 'name', 'type', and 'id' keys (only successfully resolved entities)
    """
    if not names_mapping:
        return []
    
    resolved_mapping = []
    
    for entity in names_mapping:
        resolved_entity = await _resolve_single_entity(entity, container_id, container_type)
        if resolved_entity:
            resolved_mapping.append(resolved_entity)
    
    return resolved_mapping

# Made with Bob
