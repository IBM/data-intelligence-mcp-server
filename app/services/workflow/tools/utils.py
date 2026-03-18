# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Utility functions for workflow tools.

This module provides shared utility functions for querying glossary artefacts
(data classes and business terms) from the workflow service.
"""

from typing import List, Literal
from app.services.workflow.models.artefact import Artefact, BusinessTerm, DataClass
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import SEARCH_PATH, GLOSSARY_ARTIFACT_TYPES_ENDPOINT
from fastmcp.exceptions import ToolError

ZERO_MINUTES = "+00:00"


def validate_search_params(search_term: str, artifact_type: str, max_results: int) -> None:
    """
    Validate search parameters for querying artefacts.
    
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


async def _query_artifact_in_draft_by_term(search_term: str, artifact_type: str, max_results: int) -> List[Artefact]:
    """
    Query the glossary API for artefacts in draft mode.

    Args:
        search_term: str: search_term in name or description
        artifact_type: str: artifact type string like 'data_class' or 'glossary_term'
        max_results: int: Maximum number of artefacts to return

    Returns:
        List[Artefact]: List of glossary artefact objects
        
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

        artefacts = []
        item_list = response.get('resources', [])

        for item in item_list:
            # Create appropriate artefact type based on artifact_type
            if artifact_type == 'glossary_term':
                artefact_obj = BusinessTerm(
                    name=item.get("name"),
                    description=item.get('long_description'),
                    artifact_id=item.get("artifact_id"),
                    modified_by=item.get("modified_by"),
                    state=item.get("draft_mode"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    workflow_id=item.get("workflow_id"),
                    artifact_type=artifact_type
                )
            elif artifact_type == 'data_class':
                artefact_obj = DataClass(
                    name=item.get("name"),
                    description=item.get('long_description'),
                    artifact_id=item.get("artifact_id"),
                    modified_by=item.get("modified_by"),
                    state=item.get("draft_mode"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    workflow_id=item.get("workflow_id"),
                    artifact_type=artifact_type
                )
            else:
                artefact_obj = Artefact(
                    name=item.get("name"),
                    description=item.get('long_description'),
                    artifact_id=item.get("artifact_id"),
                    modified_by=item.get("modified_by"),
                    state=item.get("draft_mode"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    workflow_id=item.get("workflow_id"),
                    artifact_type=artifact_type
                )
            
            artefacts.append(artefact_obj)

        return artefacts

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        LOGGER.error(f"Error querying glossary artefacts in draft mode: {str(e)}")
        # Re-raise exceptions so callers can handle them appropriately
        raise ToolError(f"Failed to query glossary artefacts in draft mode: {str(e)}")


async def _query_artefacts_by_term(search_term: str, artifact_type: str, max_results: int) -> List[Artefact]:
    """
    Use the global search API for artefacts.

    Args:
        search_term: str: search_term in name or description
        artifact_type: str: artifact type string like 'data_class' or 'glossary_term'
        max_results: int: Maximum number of artefacts to return

    Returns:
        List[Artefact]: List of glossary artefact objects
        
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
            params=params,
            json=payload
        )

        # Schema: { "size": 3, "rows": [ { "last_updated_at": 1763108155799, "metadata": { "name": "Spanish Fiscal Identification Number", ...
        artefacts = []
        item_list = response.get('rows', [])

        for artefact in item_list:
            metadata = artefact.get("metadata", {})
            entity = artefact.get("entity", {})
            LOGGER.debug(f"Processing entity: {entity}")
            artifacts = entity.get("artifacts", {})
            
            # Create appropriate artefact type based on artifact_type
            if artifact_type == 'glossary_term':
                artefact_obj = BusinessTerm(
                    name=metadata.get("name"),
                    description=metadata.get("description"),
                    artifact_id=artifacts.get("artifact_id"),
                    modified_by=metadata.get("modified_by"),
                    state=entity.get("state"),
                    created_at=metadata.get("created_at"),
                    artifact_type=artifact_type
                )
            elif artifact_type == 'data_class':
                artefact_obj = DataClass(
                    name=metadata.get("name"),
                    description=metadata.get("description"),
                    artifact_id=artifacts.get("artifact_id"),
                    modified_by=metadata.get("modified_by"),
                    state=entity.get("state"),
                    created_at=metadata.get("created_at"),
                    artifact_type=artifact_type
                )
            else:
                artefact_obj = Artefact(
                    name=metadata.get("name"),
                    description=metadata.get("description"),
                    artifact_id=artifacts.get("artifact_id"),
                    modified_by=metadata.get("modified_by"),
                    state=entity.get("state"),
                    created_at=metadata.get("created_at"),
                    artifact_type=artifact_type
                )
            
            artefacts.append(artefact_obj)

        return artefacts

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        LOGGER.error(f"Error querying glossary artefacts: {str(e)}")
        # Re-raise exceptions so callers can handle them appropriately
        raise ToolError(f"Failed to query glossary artefacts: {str(e)}")
