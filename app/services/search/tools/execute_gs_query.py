# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json as _json
from typing import Annotated, Any, Dict, Optional

from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.services.search.models.execute_gs_query import (
    ExecuteGSQueryRequest,
    ExecuteGSQueryResponse,
    GSCamsRow,
    SemanticSearchExpansion,
)
from app.services.text_to_query_search.utils.query_generator import generate_gs_query
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.tool_helper_service import create_default_headers, tool_helper_service

TABLE_TITLE_GS_QUERY_RESULTS = "Global Search Query Results"


def _build_query_params(request: ExecuteGSQueryRequest) -> Dict[str, Any]:
    """Return only the optional query-string parameters that were explicitly set."""
    optional_fields = ("role", "auth_cache", "auth_scope", "type")
    return {field: getattr(request, field) for field in optional_fields if getattr(request, field) is not None}


def _build_request_body(gs_query: str | dict) -> Any:
    """Return the ES DSL body dict from *gs_query*.

    Accepts either a pre-parsed ``dict`` (from ``generate_gs_query``) or a
    JSON/Lucene string supplied directly by the caller.  Plain strings that
    cannot be parsed as JSON are wrapped in a Lucene ``query_string`` clause.
    """
    if isinstance(gs_query, dict):
        return gs_query
    try:
        return _json.loads(gs_query)
    except _json.JSONDecodeError:
        return {"query": {"query_string": {"query": gs_query}}}


def _parse_semantic_expansions(response: Dict[str, Any]):
    """Convert the raw ``semantic_search_expansions`` list to typed objects, or ``None``."""
    raw = response.get("semantic_search_expansions") or []
    parsed = [
        SemanticSearchExpansion.model_validate(entry) if isinstance(entry, dict)
        else SemanticSearchExpansion(search_string=str(entry))
        for entry in raw
    ]
    return parsed or None


def _emit_ui_table_if_results(rows: list) -> None:
    """Emit a UI summary table when *rows* is non-empty."""
    if not rows:
        return
    table_rows = [
        {
            "Name": (row.metadata.name or "") if row.metadata else "",
            "Artifact ID": row.artifact_id or "",
            "Artifact Type": (row.metadata.artifact_type or "") if row.metadata else "",
            "Provider Type": row.provider_type_id or "",
            "Catalog ID": (row.entity.assets.catalog_id or "") if (row.entity and row.entity.assets) else "",
            "Score": row.score if row.score is not None else "",
            "Semantic": row.semantic_search_result if row.semantic_search_result is not None else "",
        }
        for row in rows
    ]
    ui_message_context.add_table_ui_message(
        tool_name="run_gs_query",
        formatted_data=table_rows,
        title=TABLE_TITLE_GS_QUERY_RESULTS,
    )


async def _resolve_gs_query(request: ExecuteGSQueryRequest) -> tuple[str | dict, dict | None]:
    """Return the final ES DSL query and an optional pre-fetched validation response.

    Returns a ``str`` when the caller supplied ``gs_query`` directly, or a ``dict``
    when the query was generated from ``natural_language_query``.  In the latter case
    ``generate_gs_query`` already executed a validation search internally, so that
    response is returned here to avoid a redundant round-trip to the GS endpoint.
    """
    if request.gs_query:
        return request.gs_query, None
    LOGGER.info(
        "Generating ES DSL query from natural language: '%s'",
        request.natural_language_query,
    )
    query_data, validation_response = await generate_gs_query(search_prompt=request.natural_language_query)
    LOGGER.info("Generated ES DSL query: '%s'", query_data)
    return query_data, validation_response


async def _execute_gs_query(
    request: ExecuteGSQueryRequest,
) -> ExecuteGSQueryResponse:
    """Execute a GS formatted Elasticsearch DSL query via POST /v3/search.

    When ``request.natural_language_query`` is set the ES DSL body is generated
    automatically from that prompt via the text-to-query service and the result
    is used as ``gs_query``.  An explicit ``gs_query`` value always takes
    precedence over ``natural_language_query``.
    """
    gs_query, validation_response = await _resolve_gs_query(request)
    LOGGER.info("In the execute_gs_query tool, executing GS query: '%s'.", gs_query)

    headers = create_default_headers()
    if request.run_as_tenant:
        headers["Run-as-Tenant"] = request.run_as_tenant

    try:
        if validation_response is not None:
            LOGGER.info("Reusing validation response from query generation, skipping GS POST.")
            response = validation_response
        else:
            response = await tool_helper_service.execute_post_request(
                url=f"{tool_helper_service.base_url}{GS_BASE_ENDPOINT}",
                headers=headers,
                params=_build_query_params(request),
                json=_build_request_body(gs_query),
                tool_name="run_gs_query",
            )

        raw_rows = response.get("rows", [])
        rows = [GSCamsRow.model_validate(row) for row in raw_rows]
        LOGGER.info(f"execute_gs_query returned {len(rows)} result(s).")

        _emit_ui_table_if_results(rows)

        return ExecuteGSQueryResponse(
            size=response.get("size", len(rows)),
            rows=rows,
            aggregations=response.get("aggregations"),
            semantic_search_expansions=_parse_semantic_expansions(response),
        )

    except ExternalAPIError as e:
        LOGGER.error(f"Failed to run execute_gs_query tool. External API error: {str(e)}")
        raise ExternalAPIError(f"Failed to execute GS query. External API error: {str(e)}")
    except Exception as e:
        LOGGER.error(f"Failed to run execute_gs_query tool. Unexpected error: {str(e)}")
        raise ServiceError(f"Failed to execute GS query. Unexpected error: {str(e)}")


@service_registry.tool(
    name="run_gs_query",
    annotations={
        "readOnlyHint": True,
        "title": "Search the Global Search Index via ES DSL or Natural Language",
    },
    description="""Use this tool to execute a GS (Global Search) formatted query directly against the global search index.
    The query is an Elasticsearch DSL body passed as the request body. Results are capped at 10000 documents.
    Use this tool when you need fine-grained control over the search query, such as filtering by specific fields,
    combining boolean clauses, or running a query that has already been formulated in GS/ES DSL syntax.

    IMPORTANT — when using this tool, prefer gs_query over natural_language_query:
    For simple keywords, phrases, or complex filters passed to this tool, always construct and pass gs_query
    directly using the gs_user_query form shown in the examples below.
    Only use natural_language_query as a last resort when you are completely unable to express the search
    as an Elasticsearch DSL — for example, when the user's intent involves multi-step reasoning that cannot
    be directly mapped to ES DSL fields.
    gs_query always takes precedence when both are supplied.

    Asset count by type workflow (e.g. 'how many assets', 'asset count by type', 'breakdown by type'):
    Step 1 — call find_container to resolve the catalog or project name to its ID.
    Step 2 — call this tool with EXACTLY this gs_query structure (do not change field names):
      IMPORTANT: always include the must_not data_asset_column exclusion —
      For a catalog: {\"query\":{\"bool\":{\"filter\":[{\"term\":{\"entity.assets.catalog_id\":\"<id>\"}}],\"must_not\":[{\"term\":{\"metadata.artifact_type\":\"data_asset_column\"}}]}},\"size\":0,\"aggs\":{\"asset_count_by_type\":{\"terms\":{\"field\":\"metadata.artifact_type\",\"size\":50}}}}
      For a project: {\"query\":{\"bool\":{\"filter\":[{\"term\":{\"entity.assets.project_id\":\"<id>\"}}],\"must_not\":[{\"term\":{\"metadata.artifact_type\":\"data_asset_column\"}}]}},\"size\":0,\"aggs\":{\"asset_count_by_type\":{\"terms\":{\"field\":\"metadata.artifact_type\",\"size\":50}}}}
      Set auth_scope to \"catalog\" or \"project\" accordingly.

    Query forms supported:
    1. Standard ES DSL — e.g. match_all, match, bool, term, range.
    2. GS 'gs_user_query' — full-text search with optional field restriction and NLQ analysis.
       - 'search_fields': restricts search to the listed fields; omit to search all configured fields.
       - 'nlq_analyzer_enabled': ignores stop-words and prioritises common phrases.
       - 'nested': controls nested-document matching.
    3. GS semantic / AI search — set 'semantic_search_enabled': true inside gs_user_query.
       - 'semantic_search_enabled' defaults to false; options under 'semantic_search_options'
         are only effective when it is true.
       - 'semantic_search_expansion_exclusions': suppresses specific expansions returned by a
         previous call's 'semantic_search_expansions' response field.
       - 'semantic_search_expansions' in the response is always empty for lexical (non-semantic) search.

    Note: response fields such as 'custom_attributes' apply only to assets, and 'categories'
    only to artifacts — not all fields are populated for every result type.

    Examples:
        - Match-all: {\"query\":{\"match_all\":{}}}
        - Lexical GS search with field restriction and NLQ:
          {\"query\":{\"gs_user_query\":{\"search_string\":\"the quick red fox\",\"search_fields\":[\"metadata.name\",\"metadata.description\"],\"nlq_analyzer_enabled\":true,\"nested\":false}}}
        - Semantic / AI search:
          {\"query\":{\"gs_user_query\":{\"search_string\":\"bank\",\"semantic_search_enabled\":true,\"semantic_search_options\":{\"semantic_search_expansion_exclusions\":{\"bank\":[\"repository\"]}}}}}
        - Simple keyword search (preferred form — always use this, not natural_language_query):
          {\"query\":{\"gs_user_query\":{\"search_string\":\"rugby\",\"nlq_analyzer_enabled\":true,\"nested\":false}}}
        - natural_language_query is ONLY a fallback when the intent cannot be expressed as ES DSL.

    Returns: Structured response with size (hit count), typed rows
    (each containing provider_type_id, tenant_id, metadata, artifact_id, entity with CAMS asset
    fields, custom_attributes, semantic_search_result, _score), aggregations, and
    semantic_search_expansions (non-empty only for semantic search).
    """,
    tags={"search", "gs_query", "global_search","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "search"},
)
@auto_context
async def execute_gs_query(
    gs_query: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "The Elasticsearch DSL query body as a JSON string, sent as the request body "
            "to the global search index. "
            "Supports standard ES DSL (e.g. match_all, match, bool) as well as the GS-specific "
            "'gs_user_query' function for full-text and semantic (AI) search. "
            "In gs_user_query: 'search_fields' restricts search to named fields; "
            "'nlq_analyzer_enabled' ignores irrelevant words and prioritises common phrases; "
            "'semantic_search_enabled' (default false) enables LLM-based semantic search — "
            "when true, 'semantic_search_options' may be provided to fine-tune behaviour, "
            "including 'semantic_search_expansion_exclusions' to suppress unwanted semantic expansions "
            "returned in a previous response via 'semantic_search_expansions'. "
            "'semantic_search_expansions' in the response is always empty for lexical (non-semantic) search. "
            "Example (match-all): '{\"query\":{\"match_all\":{}}}' "
            "Example (lexical GS search): '{\"query\":{\"gs_user_query\":{\"search_string\":\"revenue\","
            "\"search_fields\":[\"metadata.name\",\"metadata.description\"],"
            "\"nlq_analyzer_enabled\":true,\"nested\":false}}}' "
            "Example (semantic/AI search): '{\"query\":{\"gs_user_query\":{\"search_string\":\"bank\","
            "\"semantic_search_enabled\":true,\"semantic_search_options\":"
            "{\"semantic_search_expansion_exclusions\":{\"bank\":[\"repository\"]}}}}}'"
            )
        ),
    ] = None,
    natural_language_query: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "FALLBACK ONLY — use gs_query instead whenever possible. "
                "A plain-English question or search prompt used only when the search intent cannot be expressed "
                "as an Elasticsearch DSL query. When provided (and gs_query is absent), the text-to-query "
                "service automatically generates an ES DSL body from this prompt. "
                "For simple keyword or phrase searches always use gs_query with gs_user_query instead. "
                "Example of when natural_language_query is appropriate: "
                "'Find all customer data assets tagged PII in the Finance catalog'"
            ),
        ),
    ] = None,
    role: Annotated[
        Optional[str],
        Field(
            default="viewer",
            description=(
                "Role for governance artifacts limited by zone. "
                "Allowed values: 'viewer', 'editor'."
            ),
        ),
    ] = None,
    auth_cache: Annotated[
        Optional[bool],
        Field(
            default=False,
            description="Use cached authorization info for building ACL filters.",
        ),
    ] = None,
    auth_scope: Annotated[
        Optional[str],
        Field(
            default="all",
            description=(
                "ACL scope filter applied to the query. "
                "Allowed values: 'all', 'catalog', 'project', 'space', 'category', "
                "'ibm_watsonx_governance_catalog', 'ibm_data_product_catalog', 'system_scope_data'. "
            ),
        ),
    ] = None,
    type: Annotated[
        Optional[str],
        Field(
            default="metadata",
            description=(
                "Index type inside which the document will be searched. "
                "Allowed values: 'metadata', 'data', 'semantic_cache', "
                "'metadata_vector', 'system_metadata_vector_store'. "
            ),
        ),
    ] = None,
    run_as_tenant: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Tenant ID (BSS Account ID) to run the query as. "
            ),
        ),
    ] = None,
) -> ExecuteGSQueryResponse:
    """Wrapper that expands ExecuteGSQueryRequest into individual parameters."""

    request = ExecuteGSQueryRequest(
        gs_query=gs_query,
        natural_language_query=natural_language_query,
        role=role,
        auth_cache=auth_cache,
        auth_scope=auth_scope,
        type=type,
        run_as_tenant=run_as_tenant,
    )

    return await _execute_gs_query(request)
