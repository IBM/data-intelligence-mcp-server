# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Tool for listing glossary business terms by category.

This module provides functionality to query the glossary API for business terms
filtered by a parent category, resolving the category name to its UUID first.
"""

from datetime import datetime
from typing import Annotated, List, Dict, Optional
from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import SEARCH_PATH
from app.services.metadata_enrichment.utils.term_generation_utils import validate_category_exists
from app.services.workflow.models.artifact import BusinessTerm
from app.services.workflow.models.list_business_terms_by_category import (
    ListBusinessTermsByCategoryRequest,
    ListBusinessTermsByCategoryResponse,
)
from app.services.tool_utils import get_user_info_from_iam_id
from app.services.workflow.tools.utils import fetch_steward_names
from app.services.workflow.utils.task_formatters import format_artifacts_as_table
from app.shared.exceptions.base import ValidationError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.client_detection import supports_rich_text_format
from app.shared.utils.tool_helper_service import tool_helper_service

from fastmcp.server.context import Context


async def _resolve_category_id(category_name: str) -> tuple[str, str]:
    """
    Resolve a human-readable category name to its single-UUID artifact ID.

    Uses validate_category_exists which reads entity.artifacts.artifact_id from the
    global search index, returning the correct plain UUID (not the compound key
    that row.artifact_id contains).

    Args:
        category_name: Human-readable category name provided by the user.

    Returns:
        Tuple of (resolved_name, category_id).

    Raises:
        ValidationError: If the category name is ambiguous or not found.
    """
    exists, category_id, resolved_name, duplicates = await validate_category_exists(category_name)

    if exists and category_id and resolved_name:
        return resolved_name, category_id

    if duplicates:
        paths = ", ".join(f"'{d['parent_path']}'" for d in duplicates)
        raise ValidationError(
            f"Category name '{category_name}' is ambiguous — multiple matches found: {paths}. "
            "Please provide the full category path or a more specific name.",
            service="workflow",
            tool="list_business_terms_by_category",
            remediation_steps="Use list_glossary_categories to see all available categories and their exact names."
        )

    raise ValidationError(
        f"Category '{category_name}' not found. Use list_glossary_categories to see all available categories.",
        service="workflow",
        tool="list_business_terms_by_category",
        remediation_steps="Call list_glossary_categories to get the full list of available category names."
    )


def _format_iso_date(iso_str: Optional[str]) -> Optional[str]:
    """Convert an ISO 8601 timestamp to a human-readable 'DD Mon YYYY' string."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y")
    except ValueError:
        return iso_str


async def _resolve_steward_display(item: dict, metadata: dict) -> Optional[str]:
    """
    Return a human-readable steward string for a single resource item.

    Resolution order:
    1. ``steward_ids`` list (metadata envelope or top-level) → resolved via
       ``fetch_steward_names`` → ``get_user_info_from_iam_id``.
    2. ``modified_by`` / ``created_by`` on the item or its metadata envelope —
       this endpoint returns flat items where these fields hold raw IAM IDs
       (e.g. ``IBMid-697001DGQN``).  Any value that looks like an IAM ID is
       resolved through ``get_user_info_from_iam_id`` before being returned.
    """
    steward_ids: List[str] = metadata.get("steward_ids") or item.get("steward_ids") or []
    if steward_ids:
        steward_names = await fetch_steward_names(steward_ids)
        return ", ".join(steward_names) if steward_names else None

    raw_id = item.get("modified_by") or metadata.get("modified_by") or item.get("created_by")
    if not raw_id:
        return None
    # Resolve the raw IAM / IBMid value to a display name
    try:
        return await get_user_info_from_iam_id(raw_id, "name")
    except Exception:
        LOGGER.warning(f"Could not resolve display name for steward '{raw_id}'; using raw value")
        return raw_id


def _build_business_term(item: dict, metadata: dict, modified_by: Optional[str]) -> BusinessTerm:
    """Build a BusinessTerm from a raw API resource dict and its pre-extracted metadata envelope."""
    entity: dict = item.get("entity", item)
    # The flat endpoint uses "modified_at"; enveloped responses use "updated_at"
    raw_updated = item.get("updated_at") or item.get("modified_at") or metadata.get("updated_at") or metadata.get("modified_at")
    return BusinessTerm(
        name=item.get("name") or metadata.get("name"),
        description=item.get("long_description") or item.get("description") or metadata.get("description"),
        artifact_id=item.get("artifact_id") or metadata.get("artifact_id"),
        modified_by=modified_by,
        state=item.get("state") or entity.get("state"),
        created_at=_format_iso_date(item.get("created_at") or metadata.get("created_at")),
        updated_at=_format_iso_date(raw_updated),
        workflow_id=item.get("workflow_id"),
        version_id=item.get("version_id"),
    )


async def _fetch_terms_by_category(category_name: str, max_results: int) -> List[BusinessTerm]:
    """
    Fetch published business terms for a given category via the global search index.

    The global search index only surfaces published artifacts, so no additional
    state filtering is required. The draft-centric
    ``/v3/governance_artifact_types/glossary_term`` endpoint is intentionally
    avoided here because combining ``workflow_status=published`` with
    ``parent_category_id`` causes a WKCBG2128E 400 error.

    Args:
        category_name: Human-readable name of the resolved category (used to
            filter on ``categories.primary_category_name`` in the index).
        max_results: Maximum number of results to retrieve.

    Returns:
        List of BusinessTerm objects (published only).
    """
    payload = {
        "from": 0,
        "size": max_results,
        "_source": ["*"],
        "query": {
            "bool": {
                "must": [
                    {"match": {"metadata.artifact_type": "glossary_term"}},
                    {"match_phrase": {"categories.primary_category_name": category_name}},
                ]
            }
        },
    }
    raw_response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}{SEARCH_PATH}",
        params={"tenant_scope": True},
        json=payload,
    )

    if not isinstance(raw_response, dict):
        LOGGER.warning(f"Received unexpected response type for category_name={category_name!r}")
        return []

    rows = raw_response.get("rows", [])
    if not rows:
        return []

    terms: List[BusinessTerm] = []
    for row in rows:
        metadata: dict = row.get("metadata", {})
        entity: dict = row.get("entity", {})
        artifacts: dict = entity.get("artifacts", {})

        item = {
            "name": metadata.get("name"),
            "long_description": metadata.get("description"),
            "artifact_id": artifacts.get("artifact_id"),
            "state": entity.get("state"),
            "created_at": metadata.get("created_at"),
            "modified_at": metadata.get("modified_at"),
            "modified_by": metadata.get("modified_by"),
            "steward_ids": metadata.get("steward_ids") or [],
            "version_id": artifacts.get("version_id"),
            "workflow_id": row.get("workflow_id"),
        }
        modified_by = await _resolve_steward_display(item, metadata)
        terms.append(_build_business_term(item, metadata, modified_by))

    return terms


def _rank_by_similarity(
    terms: List[BusinessTerm],
    description: str,
    top_n: int,
) -> List[BusinessTerm]:
    """
    Rank terms by BM25 similarity of their description against the user-supplied
    description, returning the top_n most similar terms.

    Terms with no description are excluded from ranking entirely.
    Falls back to returning all terms (up to top_n) if BM25 scoring fails.
    """
    from app.services.similarity_utils import BM25SimilarityService

    candidates = [t for t in terms if t.description]
    if not candidates:
        LOGGER.warning("No terms with descriptions found — cannot rank by similarity")
        return terms[:top_n]

    corpus: List[str] = [t.description for t in candidates if t.description]
    svc = BM25SimilarityService()
    svc.index(corpus)
    scores = svc.score(description)

    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    top = [t for t, _ in ranked[:top_n]]

    LOGGER.info(
        "BM25 similarity ranking: top %d of %d candidates for description %r",
        len(top), len(candidates), description[:60]
    )
    return top


async def _list_business_terms_by_category(
    request: ListBusinessTermsByCategoryRequest,
    ctx: Optional[Context],
) -> ListBusinessTermsByCategoryResponse:
    """
    Core implementation for listing business terms by category.

    Args:
        request: ListBusinessTermsByCategoryRequest containing filter parameters.
        ctx: MCP context.

    Returns:
        ListBusinessTermsByCategoryResponse.
    """
    LOGGER.info(
        f"Listing business terms by category='{request.primary_category}', "
        f"description={request.description!r}, "
        f"top_n={request.top_n}, max_results={request.max_results}, format={request.format}"
    )

    # Downgrade table format for clients that cannot render markdown
    if ctx is not None and not supports_rich_text_format(ctx) and request.format == "table":
        LOGGER.info("Client without rich text support detected: switching format from 'table' to 'json'")
        request.format = "json"

    # Step 1: resolve category name → UUID
    category_name, category_id = await _resolve_category_id(request.primary_category)
    LOGGER.info(f"Resolved category '{category_name}' → {category_id}")

    # Step 2: fetch all published business terms for that category
    business_terms = await _fetch_terms_by_category(category_name, request.max_results)
    LOGGER.info(f"Fetched {len(business_terms)} business terms for category '{category_name}'")

    # Step 3: if a description was provided, rank by BM25 similarity and return top_n
    if request.description:
        business_terms = _rank_by_similarity(business_terms, request.description, request.top_n)

    # Step 4: build name → artifact_id map
    name_to_artifact_id_map: Dict[str, str] = {
        bt.name: bt.artifact_id for bt in business_terms if bt.artifact_id
    }

    # Step 5: format output
    if request.format == "table":
        formatted_output = format_artifacts_as_table(
            artifacts=business_terms,
            base_url=str(tool_helper_service.base_url),
        )
    else:
        formatted_output = None

    return ListBusinessTermsByCategoryResponse(
        business_terms=business_terms,
        total_count=len(business_terms),
        category_name=category_name,
        category_id=category_id,
        name_to_artifact_id_map=name_to_artifact_id_map,
        formatted_output=formatted_output,
    )


_tool_description = """
Use this tool when you need to find business terms that belong to a specific category.
Accepts a human-readable category name (e.g. "Risk Management"), resolves it to the
correct category UUID, and returns all business terms whose primary category matches.

When a description is provided, uses BM25 similarity to rank all terms in the category
by how closely their description matches the given text, then returns the top_n most
similar terms (default 5). When omitted, all terms in the category are returned.

Use this tool instead of list_business_terms when the user asks to:
- "show all terms in category X"
- "list business terms for the <category> category"
- "find terms under <category> similar to <description>"
- "which terms in <category> are about <topic>"

If the category name is ambiguous or not found, the tool will suggest using
list_glossary_categories to see available category names.

Returns: The list of business terms in the category (all, or top_n ranked by description
similarity), total count, resolved category name and ID, name-to-artifact-ID mapping,
and optionally a formatted markdown table.
"""


@service_registry.tool(
    name="list_business_terms_by_category",
    annotations={
        "readOnlyHint": True,
        "title": "List Glossary Business Terms by Category",
    },
    description=_tool_description,
    tags={"workflow", "glossary", "business_terms", "governance", "category"},
    meta={"version": "1.0", "service": "glossary"},
)
@auto_context
async def list_business_terms_by_category(
    primary_category: Annotated[
        str,
        Field(description="Human-readable name of the category to filter business terms by. "
                           "If the name matches multiple categories, the tool will raise an error "
                           "and suggest using list_glossary_categories.")
    ],
    description: Annotated[
        Optional[str],
        Field(description=(
            "Optional description text to find similar terms for. When provided, terms are "
            "ranked by BM25 similarity against this text and the top_n most similar are "
            "returned. When omitted, all terms in the category are returned."
        ))
    ] = None,
    top_n: Annotated[
        int,
        Field(description="Number of top similar terms to return when description is provided (default 5)")
    ] = 5,
    max_results: Annotated[
        int,
        Field(description="Maximum number of business terms to fetch from the category (1–200, default 200)")
    ] = 200,
    format: Annotated[
        str,
        Field(description="Output format: 'table' for formatted markdown table, 'json' for raw data")
    ] = "table",
    ctx: Optional[Context] = None,
) -> ListBusinessTermsByCategoryResponse:
    """List business terms in a category; rank by description similarity when description is given."""

    request = ListBusinessTermsByCategoryRequest(
        primary_category=primary_category,
        description=description,
        top_n=top_n,
        max_results=max_results,
        format=format,
    )
    return await _list_business_terms_by_category(request, ctx)
