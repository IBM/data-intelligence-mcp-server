# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Utility functions for workflow tools.

This module provides shared utility functions for querying glossary artifacts
(data classes and business terms) from the workflow service.
"""

from typing import List, Literal
from app.services.workflow.models.artifact import Artifact, BusinessTerm, DataClass
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import SEARCH_PATH, GLOSSARY_ARTIFACT_TYPES_ENDPOINT
from fastmcp.exceptions import ToolError

ZERO_MINUTES = "+00:00"


def _create_artifact_from_item(item: dict, artifact_type: str):
    """
    Create appropriate artifact object based on artifact type.
    
    Args:
        item: Dictionary containing artifact data
        artifact_type: Type of artifact ('glossary_term' or 'data_class')
        
    Returns:
        BusinessTerm, DataClass, or Artifact object
    """
    from app.services.workflow.models.artifact import Artifact, BusinessTerm, DataClass
    
    common_fields = {
        'name': item.get("name"),
        'description': item.get('long_description') or item.get('description'),
        'artifact_id': item.get("artifact_id"),
        'modified_by': item.get("modified_by"),
        'state': item.get("draft_mode") or item.get("state"),
        'created_at': item.get("created_at"),
        'updated_at': item.get("updated_at"),
        'workflow_id': item.get("workflow_id"),
        'artifact_type': artifact_type
    }
    
    if artifact_type == 'glossary_term':
        return BusinessTerm(**common_fields)
    elif artifact_type == 'data_class':
        return DataClass(**common_fields)
    else:
        return Artifact(**common_fields)


def validate_search_params(search_term: str, artifact_type: str, max_results: int) -> None:
    """
    Validate search parameters for querying artifacts.
    
    Args:
        search_term: Search term to validate
        artifact_type: Artifact type to validate
        max_results: Maximum results to validate
        
    Raises:
        ValueError: If any parameter is invalid
    """
    if not search_term or not search_term.strip():
        raise ValueError("search_term cannot be empty or whitespace only")
    
    valid_artifact_types = ['glossary_term', 'data_class']
    if artifact_type not in valid_artifact_types:
        raise ValueError(f"artifact_type must be one of {valid_artifact_types}, got '{artifact_type}'")
    
    if max_results <= 0:
        raise ValueError(f"max_results must be positive, got {max_results}")
    
    if max_results > 100:
        LOGGER.warning(f"max_results ({max_results}) exceeds recommended limit of 100")


async def _query_artifact_in_draft_by_term(search_term: str, artifact_type: str, max_results: int) -> List[Artifact]:
    """
    Query the glossary API for artifacts in draft mode.

    Args:
        search_term: str: search_term in name or description
        artifact_type: str: artifact type string like 'data_class' or 'glossary_term'
        max_results: int: Maximum number of artifacts to return

    Returns:
        List[Artifact]: List of glossary artifact objects
        
    Raises:
        ValueError: If search parameters are invalid
    """
    # Validate input parameters
    validate_search_params(search_term, artifact_type, max_results)
    
    params = {"sub_string": search_term, "enabled": "both", "limit": max_results}
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{GLOSSARY_ARTIFACT_TYPES_ENDPOINT}/{artifact_type}",
            params=params
        )

        artifacts = []
        item_list = response.get('resources', [])

        for item in item_list:
            artifact_obj = _create_artifact_from_item(item, artifact_type)
            artifacts.append(artifact_obj)

        return artifacts

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        LOGGER.error(f"Error querying glossary artifacts in draft mode: {str(e)}")
        # Re-raise exceptions so callers can handle them appropriately
        raise ToolError(f"Failed to query glossary artifacts in draft mode: {str(e)}")


async def _query_artifacts_by_term(search_term: str, artifact_type: str, max_results: int) -> List[Artifact]:
    """
    Use the global search API for artifacts.

    Args:
        search_term: str: search_term in name or description
        artifact_type: str: artifact type string like 'data_class' or 'glossary_term'
        max_results: int: Maximum number of artifacts to return

    Returns:
        List[Artifact]: List of glossary artifact objects
        
    Raises:
        ValueError: If search parameters are invalid
    """
    # Validate input parameters
    validate_search_params(search_term, artifact_type, max_results)
    
    query_string = f"(metadata.name:{search_term}~1 OR metadata.description:{search_term}~1) AND metadata.artifact_type:{artifact_type}"
    payload = {
        "from": 0,
        "size": max_results,
        "_source": ["*"],
        "query": {"query_string": {"query": query_string}}
    }

    params = {}

    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}{SEARCH_PATH}",
            params={**params, "tenant_scope": True},
            json=payload
        )

        # Schema: { "size": 3, "rows": [ { "last_updated_at": 1763108155799, "metadata": { "name": "Spanish Fiscal Identification Number", ...
        artifact_objs = []
        item_list = response.get('rows', [])

        for artifact in item_list:
            metadata = artifact.get("metadata", {})
            entity = artifact.get("entity", {})
            LOGGER.debug(f"Processing entity: {entity}")
            artifacts = entity.get("artifacts", {})
            
            # Prepare item dict for artifact creation
            item = {
                'name': metadata.get("name"),
                'description': metadata.get("description"),
                'artifact_id': artifacts.get("artifact_id"),
                'modified_by': metadata.get("modified_by"),
                'state': entity.get("state"),
                'created_at': metadata.get("created_at"),
            }
            
            artifact_obj = _create_artifact_from_item(item, artifact_type)
            artifact_objs.append(artifact_obj)

        return artifact_objs

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        LOGGER.error(f"Error querying glossary artifacts: {str(e)}")
        # Re-raise exceptions so callers can handle them appropriately
        raise ToolError(f"Failed to query glossary artifacts: {str(e)}")
