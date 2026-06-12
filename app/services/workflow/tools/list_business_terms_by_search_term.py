# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing glossary business terms by search term.

This module provides functionality to query the glossary API for business terms
using a search term, similar to data classes search functionality.
"""

from typing import List, Dict, Literal
from app.core.registry import service_registry
from app.services.constants import SEARCH_PATH, GLOSSARY_ARTIFACT_TYPES_ENDPOINT
from app.services.workflow.models.list_business_terms_by_search_term import (
    ListBusinessTermsRequest,
    ListBusinessTermsResponse
)
from app.services.workflow.tools.utils import (
    ELICITATION_WATERMARK,
    _query_artifact_in_draft_by_term,
    _query_artifacts_by_term,
)
from app.services.workflow.utils.task_formatters import format_artifacts_as_table, prompt_user_for_artifact_selection
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.client_detection import supports_rich_text_format
from app.shared.utils.llm_utils import client_supports_elicitation

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from mcp.server.elicitation import (
    AcceptedElicitation,
    DeclinedElicitation,
    CancelledElicitation,
)

from pydantic import BaseModel, Field, create_model

async def _handle_elicitation(
    business_terms: List,
    ctx: Context
) -> List:
    """
    Handle user elicitation to select a single business term.
    
    Args:
        business_terms: List of all business terms
        ctx: MCP context for elicitation
        
    Returns:
        Subset of business terms (either all or single selection)
    """
    if len(business_terms) <= ELICITATION_WATERMARK or ctx is None:
        return business_terms
    
    # Check if both client and server support elicitation
    # If not supported, return full result set (following decline/cancel path)
    if not client_supports_elicitation(ctx):
        LOGGER.info("Elicitation not supported by client or server - returning full result set")
        return business_terms

    try:
        business_term_names = [term.name for term in business_terms]

        # Create a Literal type from the business term names for enum constraint
        SelectionLiteral = Literal[tuple(business_term_names)]
        
        # Dynamically create the elicitation model with the first option as default
        DynamicElicitationModel = create_model(
            'DynamicElicitationModel',
            selected_term=(SelectionLiteral, business_term_names[0])
        )

        # Use the dynamic model for elicitation
        response = await ctx.elicit(
            message=f"Please select one of the {len(business_term_names)} business terms",
            response_type=DynamicElicitationModel
        )
        
        LOGGER.info(f"Elicitation response: {str(response)}")
        
        if response is not None and response.action == 'accept':
            selected_term_name = response.data.selected_term
            LOGGER.info(f"Elicitation accepted: {selected_term_name}")
            
            # Find the index of the selected term
            try:
                idx = business_term_names.index(selected_term_name)
                if idx >= 0 and idx < len(business_terms):
                    return business_terms[idx:idx+1]
            except ValueError:
                LOGGER.warning(f"Selected term '{selected_term_name}' not found in business terms")
                return business_terms
        else:
            LOGGER.info("Elicitation declined or no selection made")
            
    except Exception as elicit_e:
        LOGGER.warning(f"Failed to call elicitation: {str(elicit_e)}")
    
    return business_terms


list_business_terms_by_search_term_description="""
list_business_terms_by_search_term returns a list of all business terms as objects of a data governance workflow with the artifact_id included.
Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.
Use list_business_terms_by_search_term ONLY for requests about unpublished, draft business terms or for workflow related requests, otherwise use search_governance_artifacts.
If you find markdown text in the result show it to the user.
ALWAYS use a request json object to encapsulate the parameters.
"""

async def _list_business_terms_by_search_term(
    request: ListBusinessTermsRequest,
    ctx: Context
) -> ListBusinessTermsResponse:
    """
    List glossary business terms by search term.

    Args:
        request: ListBusinessTermsRequest object containing search parameters

    Returns:
        ListBusinessTermsResponse object containing list of business terms and total count
    """
    LOGGER.info(
        f"Listing glossary business terms by search term with max_results: {request.max_results}, "
        f"draft mode: {request.draft}, format: {request.format}"
    )
    
    # Auto-detect Claude Code and switch to JSON format if needed
    # Some clients don't handle markdown tables well, so we default to JSON
    if not supports_rich_text_format(ctx) and request.format == "table":
        LOGGER.info("Client without rich text support detected: switching format from 'table' to 'json'")
        request.format = "json"

    business_terms = []
    
    if request.draft:
        business_terms = await _query_artifact_in_draft_by_term(
            search_term=request.search_term,
            artifact_type="glossary_term",
            max_results=request.max_results
        )
    else:
        business_terms = await _query_artifacts_by_term(
            search_term=request.search_term,
            artifact_type="glossary_term",
            max_results=request.max_results
        )
    
    # Handle elicitation if applicable
    business_terms = await _handle_elicitation(business_terms, ctx)

    # Build name to artifact_id mapping
    name_to_artifact_id_map = {}
    for bt in business_terms:
        if bt.artifact_id:
            name_to_artifact_id_map[bt.name] = bt.artifact_id

    # Generate output based on format
    if request.format == "table":
        # Use prompt for user selection when multiple artifacts are returned
        if len(business_terms) > 1:
            formatted_output = prompt_user_for_artifact_selection(
                artifacts=business_terms,
                base_url=str(tool_helper_service.base_url)
            )
            LOGGER.info(f"Generated user selection prompt for {len(business_terms)} business terms")
        else:
            formatted_output = format_artifacts_as_table(
                artifacts=business_terms,
                base_url=str(tool_helper_service.base_url)
            )
            LOGGER.info(f"Generated formatted table for {len(business_terms)} business terms")
        # Always include both raw data and formatted output
        return ListBusinessTermsResponse(
            business_terms=business_terms,
            total_count=len(business_terms),
            name_to_artifact_id_map=name_to_artifact_id_map,
            formatted_output=formatted_output
        )
    else:
        # format='json' - return raw data only (already includes business_terms and map)
        return ListBusinessTermsResponse(
            business_terms=business_terms,
            total_count=len(business_terms),
            name_to_artifact_id_map=name_to_artifact_id_map,
            formatted_output=None
        )


@service_registry.tool(
    name="list_business_terms_by_search_term",
    annotations={
        "readOnlyHint": True,
        "title": "Search and List Glossary Business Terms in Governance Workflows"
    },
    description=list_business_terms_by_search_term_description,
    tags={"workflow", "glossary", "business_terms", "governance"},
    meta={"version": "1.0", "service": "glossary"},
)
@auto_context
async def list_business_terms_by_search_term(
    search_term: str,
    max_results: int = 50,
    draft: bool = False,
    format: str = "table",
    ctx: Context = None,
) -> ListBusinessTermsResponse:
    """Wrapper version of list_business_terms_by_search_term."""
    
    request = ListBusinessTermsRequest(
        search_term=search_term,
        max_results=max_results,
        draft=draft,
        format=format
    )
    
    return await _list_business_terms_by_search_term(request, ctx)
