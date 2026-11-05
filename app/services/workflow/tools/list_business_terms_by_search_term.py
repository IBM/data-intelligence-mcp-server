# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing glossary business terms by search term.

This module provides functionality to query the glossary API for business terms
using a search term, similar to data classes search functionality.
"""

from typing import Annotated, List, Dict, Union  # noqa: I001, UP035 # Baseline
from pydantic import Field
from app.core.registry import service_registry
from app.services.workflow.models.list_business_terms_by_search_term import (
    BusinessTerm,
    ListBusinessTermsRequest,
    ListBusinessTermsResponse,
)
from app.services.workflow.tools.utils import (
    _query_artifact_in_draft_by_term,
    _query_artifacts_by_term,
    handle_artifact_selection_elicitation,
)
from app.services.workflow.utils.task_formatters import (
    format_artifacts_as_table,
    prompt_user_for_artifact_selection,
    workflow_artifact_categorizer,
)
from app.shared.models.pagination import PageCursor
from app.shared.utils.list_strategies import build_semantic_summary
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.client_detection import supports_rich_text_format

from fastmcp.server.context import Context

import mcp_types


_BUSINESS_TERM_INPUT_ID = "list_business_terms_elicit"


async def _handle_elicitation(
    business_terms: List,  # noqa: UP006 # Baseline
    ctx: Context,  # noqa: UP006 # Baseline
) -> Union[List, mcp_types.InputRequiredResult]:  # noqa: UP006, UP007 # Baseline
    """
    Handle user elicitation to select a single business term from the current page.

    Delegates to the shared helper ``handle_artifact_selection_elicitation`` in
    ``app.services.workflow.tools.utils``, which supports both the modern
    sessionless protocol (2026-07-28+, guard pattern) and the legacy stateful
    protocol (ctx.elicit()).

    Args:
        business_terms: List of business terms on the current page
        ctx: MCP context for elicitation

    Returns:
        Subset of business terms (either all or single selection), or an
        InputRequiredResult when the modern protocol still needs input from
        the client.
    """
    return await handle_artifact_selection_elicitation(
        artifacts=business_terms,
        ctx=ctx,
        input_id=_BUSINESS_TERM_INPUT_ID,
        selection_field="selected_term",
        item_label="business terms",
    )


list_business_terms_by_search_term_description = """
Use this tool when you need to find business terms that are part of governance workflows, especially when working with draft/unpublished business terms or when you need the artifact_id for workflow operations.
list_business_terms returns a paginated list of business terms as objects of a data governance workflow with the artifact_id included.
Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.
Use list_business_terms ONLY for requests about unpublished, draft business terms or for workflow related requests, otherwise use search_governance_artifacts.
If you find markdown text in the result show it to the user.
ALWAYS use a request json object to encapsulate the parameters.
Supports cursor-based pagination via page_size and page_token. Every response includes next_page_token / prev_page_token and a semantic_summary.
Returns: The list of business terms matching the search criteria, total count, pagination tokens, semantic summary, name-to-artifact-ID mapping, and optionally a formatted markdown table for display.
"""


async def _fetch_business_terms(
    request: ListBusinessTermsRequest,
    offset: int = 0,
) -> tuple[List[BusinessTerm], int]:  # noqa: UP006 # Baseline
    """
    Fetch a page of business terms based on draft mode.

    Args:
        request: ListBusinessTermsRequest object containing search parameters
        offset: Zero-based offset for pagination

    Returns:
        Tuple of (list of business terms for this page, total_count)
    """
    if request.draft:
        return await _query_artifact_in_draft_by_term(
            search_term=request.search_term,
            artifact_type="glossary_term",
            max_results=request.page_size,
            offset=offset,
        )
    return await _query_artifacts_by_term(
        search_term=request.search_term,
        artifact_type="glossary_term",
        max_results=request.page_size,
        offset=offset,
    )


def _build_name_to_artifact_id_map(
    business_terms: List[BusinessTerm],  # noqa: UP006 # Baseline
) -> Dict[str, str]:  # noqa: UP006 # Baseline
    """
    Build a mapping from business term name to artifact ID.

    Args:
        business_terms: List of business terms

    Returns:
        Dictionary mapping names to artifact IDs; terms without an
        artifact_id are skipped.
    """
    return {bt.name: bt.artifact_id for bt in business_terms if bt.artifact_id}


def _build_table_response(  # noqa: PLR0913 # Baseline
    business_terms: List[BusinessTerm],  # noqa: UP006 # Baseline
    total_count: int,
    name_to_artifact_id_map: Dict[str, str],  # noqa: UP006 # Baseline
    next_page_token: str | None,
    prev_page_token: str | None,
    has_more: bool,
    semantic_summary: str,
) -> ListBusinessTermsResponse:
    """
    Build the response for table format.

    A user-selection prompt is generated when multiple artifacts are returned
    on the current page; a plain table is generated otherwise.
    """
    if len(business_terms) > 1:
        formatted_output = prompt_user_for_artifact_selection(
            artifacts=business_terms, base_url=str(tool_helper_service.base_url)
        )
        LOGGER.info(
            f"Generated user selection prompt for {len(business_terms)} business terms"
        )
    else:
        formatted_output = format_artifacts_as_table(
            artifacts=business_terms, base_url=str(tool_helper_service.base_url)
        )
        LOGGER.info(
            f"Generated formatted table for {len(business_terms)} business terms"
        )

    return ListBusinessTermsResponse(
        business_terms=business_terms,
        total_count=total_count,
        name_to_artifact_id_map=name_to_artifact_id_map,
        formatted_output=formatted_output,
        next_page_token=next_page_token,
        prev_page_token=prev_page_token,
        has_more=has_more,
        semantic_summary=semantic_summary,
    )


def _build_json_response(  # noqa: PLR0913 # Baseline
    business_terms: List[BusinessTerm],  # noqa: UP006 # Baseline
    total_count: int,
    name_to_artifact_id_map: Dict[str, str],  # noqa: UP006 # Baseline
    next_page_token: str | None,
    prev_page_token: str | None,
    has_more: bool,
    semantic_summary: str,
) -> ListBusinessTermsResponse:
    """Build response for JSON format (raw data only)."""
    return ListBusinessTermsResponse(
        business_terms=business_terms,
        total_count=total_count,
        name_to_artifact_id_map=name_to_artifact_id_map,
        formatted_output=None,
        next_page_token=next_page_token,
        prev_page_token=prev_page_token,
        has_more=has_more,
        semantic_summary=semantic_summary,
    )


async def _list_business_terms_by_search_term(
    request: ListBusinessTermsRequest, ctx: Context
) -> Union[ListBusinessTermsResponse, mcp_types.InputRequiredResult]:  # noqa: UP007 # Baseline
    """
    List glossary business terms by search term.

    Args:
        request: ListBusinessTermsRequest object containing search parameters

    Returns:
        ListBusinessTermsResponse object containing list of business terms,
        total count, pagination tokens, semantic summary and name-to-artifact-id
        mapping, or an InputRequiredResult when the modern protocol still needs
        input from the client.
    """
    LOGGER.info(
        f"Listing glossary business terms by search term with page_size: {request.page_size}, "
        f"draft mode: {request.draft}, format: {request.format}"
    )

    # Auto-detect Claude Code and switch to JSON format if needed
    # Some clients don't handle markdown tables well, so we default to JSON
    if not supports_rich_text_format(ctx) and request.format == "table":
        LOGGER.info(
            "Client without rich text support detected: switching format from 'table' to 'json'"
        )
        request.format = "json"

    # Decode page_token if provided
    offset = 0
    if request.page_token:
        try:
            cursor = PageCursor.from_token(request.page_token)
            offset = cursor.offset
            if cursor.limit:
                request.page_size = cursor.limit
        except Exception as e:
            LOGGER.warning(
                f"Failed to decode page_token '{request.page_token}', defaulting offset to 0: {e}"
            )
            offset = 0

    # Fetch business terms page
    business_terms, total_count = await _fetch_business_terms(request, offset=offset)

    # Fallback total_count if backend returned nothing useful
    if total_count < 0:
        total_count = offset + len(business_terms)

    # Handle elicitation if applicable (operates on bounded current page)
    elicit_result = await _handle_elicitation(business_terms, ctx)

    # Modern protocol: propagate InputRequiredResult up as the tool result
    if isinstance(elicit_result, mcp_types.InputRequiredResult):
        return elicit_result

    business_terms = elicit_result

    # Pagination tokens
    has_more = (offset + len(business_terms)) < total_count and len(
        business_terms
    ) == request.page_size
    next_page_token = (
        PageCursor(
            limit=request.page_size, offset=offset + request.page_size
        ).to_token()
        if (offset + request.page_size) < total_count
        else None
    )
    prev_page_token = (
        PageCursor(
            limit=request.page_size, offset=max(0, offset - request.page_size)
        ).to_token()
        if offset > 0
        else None
    )

    # Semantic summary
    semantic_summary = build_semantic_summary(
        items=business_terms,
        total_count=total_count,
        page_offset=offset,
        page_limit=request.page_size,
        item_categorizer=workflow_artifact_categorizer,
    )

    # Shared values for both response builders
    response_kwargs = {
        "total_count": total_count,
        "name_to_artifact_id_map": _build_name_to_artifact_id_map(business_terms),
        "next_page_token": next_page_token,
        "prev_page_token": prev_page_token,
        "has_more": has_more,
        "semantic_summary": semantic_summary,
    }

    # Generate output based on format
    if request.format == "table":
        return _build_table_response(business_terms, **response_kwargs)

    # format='json' - return raw data only
    return _build_json_response(business_terms, **response_kwargs)


@service_registry.tool(
    name="list_business_terms",
    annotations={
        "readOnlyHint": True,
        "title": "Search and List Glossary Business Terms in Governance Workflows",
    },
    description=list_business_terms_by_search_term_description,
    tags={
        "workflow",
        "glossary",
        "business_terms",
        "governance",
        "metadata_management_and_governance",
    },
    meta={"version": "2.0", "service": "glossary"},
)
@auto_context
async def list_business_terms_by_search_term(  # noqa: PLR0913 # Baseline
    search_term: Annotated[
        str,
        Field(description="Search term for name or description of the business terms"),
    ],
    draft: Annotated[
        bool, Field(description="Business term in draft or published")
    ] = False,
    page_size: Annotated[
        int, Field(description="Number of business terms to return per page (1-50)")
    ] = 10,
    page_token: Annotated[
        str | None,
        Field(description="Opaque pagination cursor token from a previous response"),
    ] = None,
    max_results: Annotated[
        int | None,
        Field(
            description="[Deprecated: use page_size] Maximum number of business terms to return"
        ),
    ] = None,
    format: Annotated[  # noqa: A002 # Baseline
        str,
        Field(
            description="Output format: 'table' for formatted markdown table, 'json' for raw data"
        ),
    ] = "table",
    ctx: Context = None,
) -> Union[ListBusinessTermsResponse, mcp_types.InputRequiredResult]:  # noqa: UP007 # Baseline
    """Wrapper version of list_business_terms_by_search_term."""

    request = ListBusinessTermsRequest(
        search_term=search_term,
        draft=draft,
        page_size=page_size if max_results is None else max_results,
        max_results=max_results,
        page_token=page_token,
        format=format,
    )

    return await _list_business_terms_by_search_term(request, ctx)
