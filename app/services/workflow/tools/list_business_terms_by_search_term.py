# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing glossary business terms by search term.

This module provides functionality to query the glossary API for business terms
using a search term, similar to data classes search functionality.
"""

from typing import List, Dict
from app.core.registry import service_registry
from app.services.constants import SEARCH_PATH, GLOSSARY_ARTIFACT_TYPES_ENDPOINT
from app.services.workflow.models.list_business_terms_by_search_term import (
    ListBusinessTermsRequest,
    ListBusinessTermsResponse
)
from app.services.workflow.tools.utils import _query_artifact_in_draft_by_term, _query_artefacts_by_term
from app.services.workflow.utils.task_formatters import format_artefacts_as_table, prompt_user_for_artifact_selection
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service

from fastmcp.exceptions import ToolError

@service_registry.tool(
    name="list_business_terms_by_search_term",
    description="""
list_business_terms_by_search_term returns a list of all business terms as objects of a data governance workflow with the artifact_id included.
Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.
ALWAYS use a request json object to encapsulate the parameters.
    """,
    tags={"workflow", "glossary", "business_terms", "governance"},
    meta={"version": "1.0", "service": "glossary"},
)
@auto_context
async def list_business_terms_by_search_term(
    request: ListBusinessTermsRequest,
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

    business_terms = []
    
    if request.draft:
        business_terms = await _query_artifact_in_draft_by_term(
            search_term=request.search_term,
            artifact_type="glossary_term",
            max_results=request.max_results
        )
    else:
        business_terms = await _query_artefacts_by_term(
            search_term=request.search_term,
            artifact_type="glossary_term",
            max_results=request.max_results
        )
        

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
                artefacts=business_terms,
                base_url=str(tool_helper_service.base_url)
            )
            LOGGER.info(f"Generated user selection prompt for {len(business_terms)} business terms")
        else:
            formatted_output = format_artefacts_as_table(
                artefacts=business_terms,
                base_url=str(tool_helper_service.base_url)
            )
            LOGGER.info(f"Generated formatted table for {len(business_terms)} business terms")
        return ListBusinessTermsResponse(
            business_terms=None,
            total_count=len(business_terms),
            name_to_artifact_id_map=None,
            formatted_output=formatted_output
        )
    else:
        # format='json' - return raw data only
        return ListBusinessTermsResponse(
            business_terms=business_terms,
            total_count=len(business_terms),
            name_to_artifact_id_map=name_to_artifact_id_map,
            formatted_output=None
        )


@service_registry.tool(
    name="list_business_terms_by_search_term",
    description="""Watsonx Orchestrator compatible wrapper for list_business_terms_by_search_term.
list_business_terms_by_search_term returns a list of all business terms as objects of a data governance workflow with the artifact_id included.
Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.
Make sure to use a request json object to encapsulate the parameters.
    """,
    tags={"workflow", "wxo", "glossary", "business_terms", "governance"},
    meta={"version": "1.0", "service": "glossary"},
)
@auto_context
async def wxo_list_business_terms_by_search_term(
    search_term: str,
    max_results: int = 50,
    draft: bool = False,
    format: str = "table",
) -> ListBusinessTermsResponse:
    """Watsonx Orchestrator compatible version of list_business_terms_by_search_term."""
    
    request = ListBusinessTermsRequest(
        search_term=search_term,
        max_results=max_results,
        draft=draft,
        format=format
    )
    
    return await list_business_terms_by_search_term(request)
