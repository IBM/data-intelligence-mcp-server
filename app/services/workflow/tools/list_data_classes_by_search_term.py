# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing glossary data classes.

This module provides functionality to query the glossary API for data classes
and establish their mapping to artifact IDs.
"""

from typing import List, Dict, Optional
from app.core.registry import service_registry
from app.services.constants import SEARCH_PATH, GLOSSARY_DATA_CLASS_ENDPOINT, GLOSSARY_ARTIFACT_TYPES_ENDPOINT, GLOSSARY_DATA_CLASS

from app.services.workflow.models.list_data_classes_by_search_term import (
    ListDataClassesRequest,
    ListDataClassesResponse,
    DataClass
)
from app.services.workflow.models.artefact import Artefact
from app.services.workflow.tools.utils import _query_artifact_in_draft_by_term, _query_artefacts_by_term
from app.services.workflow.utils.task_formatters import format_artefacts_as_table, prompt_user_for_artifact_selection
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from mcp.server.elicitation import (
    AcceptedElicitation,
    DeclinedElicitation,
    CancelledElicitation,
)

from pydantic import BaseModel, Field
class ElicitationResponse(BaseModel):
    class_nr: Optional[int] = Field(default=None)

async def _fetch_data_classes(request: ListDataClassesRequest) -> List[DataClass]:
    """
    Fetch data classes based on draft mode.
    
    Args:
        request: ListDataClassesRequest object containing filter parameters
        
    Returns:
        List of data classes
    """
    if request.draft:
        return await _query_artifact_in_draft_by_term(
            search_term=request.search_term,
            artifact_type="data_class",
            max_results=request.max_results
        )
    else:
        return await _query_artefacts_by_term(
            search_term=request.search_term,
            artifact_type="data_class",
            max_results=request.max_results
        )


def _build_name_to_artifact_id_map(data_classes: List[DataClass]) -> dict:
    """
    Build a mapping from data class name to artifact ID.
    
    Args:
        data_classes: List of data classes
        
    Returns:
        Dictionary mapping names to artifact IDs
    """
    return {dc.name: dc.artifact_id for dc in data_classes if dc.artifact_id}


async def _handle_elicitation(
    data_classes: List[DataClass],
    ctx: Context
) -> List[DataClass]:
    """
    Handle user elicitation to select a single data class.
    
    Args:
        data_classes: List of all data classes
        ctx: MCP context for elicitation
        
    Returns:
        Subset of data classes (either all or single selection)
    """
    if len(data_classes) <= 1 or ctx is None:
        return data_classes

    
    # Generate formatted output for elicitation
    formatted_output = format_artefacts_as_table(
        artefacts=data_classes,
        base_url=str(tool_helper_service.base_url)
    )
    
    try:
        data_class_names = [data_class.name for data_class in data_classes]

        response = await ctx.elicit(
            message="Please select one of the classes",
            response_type=data_class_names
        )
        
        LOGGER.info(f"Elicitation response: {str(response)}")
        
        if response is not None and response.action == 'accept':
            idx = data_class_names.index(response.data)
            LOGGER.info(f"Elicitation accepted: {str(idx)}")
            
            if idx >= 0 and idx < len(data_classes):
                return data_classes[idx:idx+1]
        else:
            LOGGER.info("Elicitation declined")
            
    except Exception as elicit_e:
        LOGGER.warning(f"Failed to call elicitation: {str(elicit_e)}")
    
    return data_classes


def _build_table_response(data_classes: List[DataClass]) -> ListDataClassesResponse:
    """
    Build response for table format.
    
    Args:
        data_classes: List of data classes
        
    Returns:
        ListDataClassesResponse with formatted table output
    """
    formatted_output = format_artefacts_as_table(
        artefacts=data_classes,
        base_url=str(tool_helper_service.base_url)
    )
    
    LOGGER.info(f"Generated formatted table for {len(data_classes)} data classes")
    
    # Always include both raw data and formatted output
    name_to_artifact_id_map = _build_name_to_artifact_id_map(data_classes)
    
    return ListDataClassesResponse(
        data_classes=data_classes,
        total_count=len(data_classes),
        name_to_artifact_id_map=name_to_artifact_id_map,
        formatted_output=formatted_output
    )


def _build_json_response(data_classes: List[DataClass]) -> ListDataClassesResponse:
    """
    Build response for JSON format.
    
    Args:
        data_classes: List of data classes
        
    Returns:
        ListDataClassesResponse with raw data and mapping
    """
    name_to_artifact_id_map = _build_name_to_artifact_id_map(data_classes)
    
    return ListDataClassesResponse(
        data_classes=data_classes,
        total_count=len(data_classes),
        name_to_artifact_id_map=name_to_artifact_id_map,
        formatted_output=None
    )

@service_registry.tool(
    name="list_data_classes_by_search_term",
    description="""
list_data_classes_by_search_term returns a list of all data classes as objects of a data governance workflow pertaining to the search term
with the artifact_id included. Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.
If you find markdown text in the result show it to the user.
ALWAYS use a request json object to encapsulate the parameters.
    """,
    tags={"workflow", "glossary", "data_classes", "governance"},
    meta={"version": "1.0", "service": "glossary"},
)
# explicit context for MCP elicitation, no autocontext
async def list_data_classes_by_search_term(
    request: ListDataClassesRequest,
    ctx: Context
) -> ListDataClassesResponse:
    """
    List glossary data classes.

    Args:
        request: ListDataClassesRequest object containing filter parameters

    Returns:
        ListDataClassesResponse object containing list of data classes,
        total count, and name-to-artifact-id mapping
    """
    LOGGER.info(
        f"Listing glossary data classes with max_results: {request.max_results}, "
        f"draft mode: {request.draft}, format: {request.format}"
    )

    # Fetch data classes
    data_classes = await _fetch_data_classes(request)
    
    # Handle elicitation if applicable
    data_classes = await _handle_elicitation(data_classes, ctx)
    
    # Generate output based on format
    if request.format == "table":
        return _build_table_response(data_classes)
    elif request.format == "json":
        return _build_json_response(data_classes)
    else:
        raise ToolError("Invalid output format")


@service_registry.tool(
    name="list_data_classes_by_search_term",
    description="""Watsonx Orchestrator compatible wrapper for list_data_classes_by_search_term.
list_data_classes_by_search_term returns a list of all data classes as objects of a data governance workflow pertaining to the search term
with the artifact_id included. Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.
ALWAYS use a request json object to encapsulate the parameters.
    """,
    tags={"workflow", "wxo", "glossary", "data_classes", "governance"},
    meta={"version": "1.0", "service": "glossary"},
)
@auto_context
async def wxo_list_data_classes_by_search_term(
    search_term: str,
    max_results: int = 50,
    draft: bool = False,
    format: str = "table",
) -> ListDataClassesResponse:
    """Watsonx Orchestrator compatible version of list_data_classes_by_search_term."""
    
    request = ListDataClassesRequest(
        search_term=search_term,
        max_results=max_results,
        draft=draft,
        format=format
    )
    
    # Create a minimal context for the main function
    class MinimalContext:
        async def elicit(self, message, response_type):
            # Skip elicitation for wxo version
            logger.info("Empty elicitation " + str(message) + ", " + str(response_type))
            return None
    
    return await list_data_classes_by_search_term(request, MinimalContext())
