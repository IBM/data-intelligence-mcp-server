# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing glossary data classes.

This module provides functionality to query the glossary API for data classes
and establish their mapping to artifact IDs.
"""

from typing import Annotated, List, Union  # noqa: I001, UP035 # Baseline
from pydantic import Field
import mcp_types
from app.core.registry import service_registry

from app.services.workflow.models.list_data_classes_by_search_term import (
    ListDataClassesRequest,
    ListDataClassesResponse,
    DataClass,
)
from app.services.workflow.tools.utils import (
    _query_artifact_in_draft_by_term,
    _query_artifacts_by_term,
    handle_artifact_selection_elicitation,
)
from app.services.workflow.utils.task_formatters import (
    format_artifacts_as_table,
    workflow_artifact_categorizer,
)
from app.shared.models.pagination import PageCursor
from app.shared.utils.list_strategies import build_semantic_summary
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.client_detection import supports_rich_text_format, MinimalContext
from app.shared.exceptions.base import ValidationError

from fastmcp.server.context import Context

_DATA_CLASS_INPUT_ID = "list_data_classes_elicit"


async def _fetch_data_classes(
    request: ListDataClassesRequest,
    offset: int = 0,
) -> tuple[List[DataClass], int]:  # noqa: UP006 # Baseline
    """
    Fetch a page of data classes based on draft mode.

    Args:
        request: ListDataClassesRequest object containing filter parameters
        offset: Zero-based offset for pagination

    Returns:
        Tuple of (list of data classes for this page, total_count)
    """
    if request.draft:
        return await _query_artifact_in_draft_by_term(
            search_term=request.search_term,
            artifact_type="data_class",
            max_results=request.page_size,
            offset=offset,
        )
    return await _query_artifacts_by_term(
        search_term=request.search_term,
        artifact_type="data_class",
        max_results=request.page_size,
        offset=offset,
    )


def _build_name_to_artifact_id_map(data_classes: List[DataClass]) -> dict:  # noqa: UP006 # Baseline
    """
    Build a mapping from data class name to artifact ID.

    Args:
        data_classes: List of data classes

    Returns:
        Dictionary mapping names to artifact IDs
    """
    return {dc.name: dc.artifact_id for dc in data_classes if dc.artifact_id}


async def _handle_elicitation(
    data_classes: List[DataClass],  # noqa: UP006 # Baseline
    ctx: Context,  # noqa: UP006 # Baseline
) -> Union[List[DataClass], mcp_types.InputRequiredResult]:  # noqa: UP006, UP007 # Baseline
    """
    Handle user elicitation to select a single data class from the current page.

    Delegates to the shared helper ``handle_artifact_selection_elicitation`` in
    ``app.services.workflow.tools.utils``, which supports both the modern
    sessionless protocol (2026-07-28+, guard pattern) and the legacy stateful
    protocol (ctx.elicit()).

    Args:
        data_classes: List of data classes on the current page
        ctx: MCP context for elicitation

    Returns:
        Subset of data classes (either all or single selection), or an
        InputRequiredResult when the modern protocol still needs input from
        the client (must be propagated up as the tool result).
    """
    return await handle_artifact_selection_elicitation(
        artifacts=data_classes,
        ctx=ctx,
        input_id=_DATA_CLASS_INPUT_ID,
        selection_field="selected_class",
        item_label="data classes",
    )


def _build_table_response(  # noqa: PLR0913 # Baseline
    data_classes: List[DataClass],  # noqa: UP006 # Baseline
    total_count: int,
    offset: int,
    page_size: int,
    next_page_token: str | None,
    prev_page_token: str | None,
    has_more: bool,
    semantic_summary: str,
) -> ListDataClassesResponse:
    """Build response for table format."""
    del offset
    del page_size
    formatted_output = format_artifacts_as_table(
        artifacts=data_classes, base_url=str(tool_helper_service.base_url)
    )

    LOGGER.info(f"Generated formatted table for {len(data_classes)} data classes")

    name_to_artifact_id_map = _build_name_to_artifact_id_map(data_classes)

    return ListDataClassesResponse(
        data_classes=data_classes,
        total_count=total_count,
        name_to_artifact_id_map=name_to_artifact_id_map,
        formatted_output=formatted_output,
        next_page_token=next_page_token,
        prev_page_token=prev_page_token,
        has_more=has_more,
        semantic_summary=semantic_summary,
    )


def _build_json_response(  # noqa: PLR0913 # Baseline
    data_classes: List[DataClass],  # noqa: UP006 # Baseline
    total_count: int,
    offset: int,
    page_size: int,
    next_page_token: str | None,
    prev_page_token: str | None,
    has_more: bool,
    semantic_summary: str,
) -> ListDataClassesResponse:
    """Build response for JSON format."""
    del offset
    del page_size
    name_to_artifact_id_map = _build_name_to_artifact_id_map(data_classes)

    return ListDataClassesResponse(
        data_classes=data_classes,
        total_count=total_count,
        name_to_artifact_id_map=name_to_artifact_id_map,
        formatted_output=None,
        next_page_token=next_page_token,
        prev_page_token=prev_page_token,
        has_more=has_more,
        semantic_summary=semantic_summary,
    )


list_data_classes_by_search_term_description = """
Use this tool when you need to find data classes that are part of governance workflows, especially when working with draft/unpublished data classes or when you need the artifact_id for workflow operations.
list_data_classes returns a paginated list of data classes as objects of a data governance workflow pertaining to the search term
with the artifact_id included. Always define the draft parameter: if the text refers to future approvals set it true, otherwise false.
Use list_data_classes ONLY for requests about unpublished, draft data classes or for workflow related requests, otherwise use search_governance_artifacts.
If you find markdown text in the result show it to the user.
ALWAYS use a request json object to encapsulate the parameters.
Supports cursor-based pagination via page_size and page_token. Every response includes next_page_token / prev_page_token and a semantic_summary.
Returns: The list of data classes matching the search criteria, total count, pagination tokens, semantic summary, name-to-artifact-ID mapping, and optionally a formatted markdown table for display.
"""


# explicit context for MCP elicitation, no autocontext
async def _list_data_classes_by_search_term(
    request: ListDataClassesRequest, ctx: Context
) -> Union[ListDataClassesResponse, mcp_types.InputRequiredResult]:  # noqa: UP007 # Baseline
    """
    List glossary data classes.

    Args:
        request: ListDataClassesRequest object containing filter parameters

    Returns:
        ListDataClassesResponse object containing list of data classes,
        total count, pagination tokens, semantic summary, and name-to-artifact-id
        mapping, or an InputRequiredResult when the modern protocol still needs
        input from the client.
    """
    LOGGER.info(
        f"Listing glossary data classes with page_size: {request.page_size}, "
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

    # Fetch data classes page
    data_classes, total_count = await _fetch_data_classes(request, offset=offset)

    # Fallback total_count if backend returned nothing useful
    if total_count < 0:
        total_count = offset + len(data_classes)

    # Handle elicitation if applicable (operates on bounded current page)
    elicit_result = await _handle_elicitation(data_classes, ctx)

    # Modern protocol: propagate InputRequiredResult up as the tool result
    if isinstance(elicit_result, mcp_types.InputRequiredResult):
        return elicit_result

    data_classes = elicit_result

    # Pagination tokens
    has_more = (offset + len(data_classes)) < total_count and len(
        data_classes
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
        items=data_classes,
        total_count=total_count,
        page_offset=offset,
        page_limit=request.page_size,
        item_categorizer=workflow_artifact_categorizer,
    )

    # Shared kwargs for both response builders
    pagination_kwargs = {
        "total_count": total_count,
        "offset": offset,
        "page_size": request.page_size,
        "next_page_token": next_page_token,
        "prev_page_token": prev_page_token,
        "has_more": has_more,
        "semantic_summary": semantic_summary,
    }

    # Generate output based on format
    if request.format == "table":
        return _build_table_response(data_classes, **pagination_kwargs)
    if request.format == "json":
        return _build_json_response(data_classes, **pagination_kwargs)
    raise ValidationError(
        f"Invalid output format '{request.format}'. Supported formats are 'table' or 'json'.",
        service="workflow",
        tool="list_data_classes_by_search_term",
        remediation_steps="Use format='table' for formatted markdown output or format='json' for raw data. Default is 'table'.",
    )


@service_registry.tool(
    name="list_data_classes",
    annotations={
        "readOnlyHint": True,
        "title": "Search and List Glossary Data Classes in Governance Workflows",
    },
    description=list_data_classes_by_search_term_description,
    tags={
        "workflow",
        "glossary",
        "data_classes",
        "governance",
        "metadata_management_and_governance",
    },
    meta={"version": "2.0", "service": "glossary"},
)
@auto_context
async def list_data_classes_by_search_term(  # noqa: PLR0913 # Baseline
    search_term: Annotated[
        str,
        Field(description="Search term for name or description of the data classes"),
    ],
    draft: Annotated[
        bool, Field(description="Data class in draft or published")
    ] = False,
    page_size: Annotated[
        int, Field(description="Number of data classes to return per page (1-50)")
    ] = 10,
    page_token: Annotated[
        str | None,
        Field(description="Opaque pagination cursor token from a previous response"),
    ] = None,
    max_results: Annotated[
        int | None,
        Field(
            description="[Deprecated: use page_size] Maximum number of data classes to return"
        ),
    ] = None,
    format: Annotated[  # noqa: A002 # Baseline
        str,
        Field(
            description="Output format: 'table' for formatted markdown table, 'json' for raw data"
        ),
    ] = "table",
    ctx: Context = None,
) -> Union[ListDataClassesResponse, mcp_types.InputRequiredResult]:  # noqa: UP007 # Baseline
    """Wrapper version of list_data_classes_by_search_term."""

    request = ListDataClassesRequest(
        search_term=search_term,
        draft=draft,
        page_size=page_size if max_results is None else max_results,
        max_results=max_results,
        page_token=page_token,
        format=format,
    )

    # Use the real context if available, otherwise use minimal context
    if ctx is not None:
        return await _list_data_classes_by_search_term(request, ctx)

    # Fallback for wxo version or when context is not available
    return await _list_data_classes_by_search_term(request, MinimalContext())
