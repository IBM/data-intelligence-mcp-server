# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Shared utility for generating Elasticsearch DSL queries from natural language.

This module is intentionally *not* an MCP tool — it is a pure utility used by
both ``dynamic_query_search`` and ``run_gs_query`` to convert a plain-English
prompt into a valid Global Search ES DSL query body.
"""

import json
from typing import List

from app.services.constants import GS_BASE_ENDPOINT, TEXT_TO_QUERY_BASE_ENDPOINT
from app.services.text_to_query_search.constants import MAX_SEARCH_RESULTS
from app.services.text_to_query_search.models.text2query_search_asset import Container
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service

# Maximum number of retry attempts for query generation
MAX_QUERY_GENERATION_ATTEMPTS = 2


def parse_and_enrich_query_data(query_data: dict | str) -> dict:
    """Parse query data from string if needed and ensure required _source fields are present."""
    if not isinstance(query_data, str):
        return query_data
    parsed: dict = json.loads(query_data)
    LOGGER.info("Parsed query string to object")
    if parsed.get("_source"):
        source = parsed["_source"]
        if isinstance(source, list):
            for required_field in ("metadata", "entity.assets", "artifact_id"):
                if required_field not in source:
                    source.append(required_field)
    return parsed


async def call_text_to_query_api(
    search_prompt: str,
    artifact_types: List[str] | None,
    container_details: Container | None,
    resolved_names_mapping: List[dict] | None = None,
) -> dict:
    """Call the text-to-query API and return a validated ES DSL query dict.

    Args:
        search_prompt: Natural language question from the user.
        artifact_types: Optional list of artifact type filters
                        (e.g. ``["data_asset", "glossary_term"]``).
        container_details: Resolved container (project/catalog) to scope the query, or ``None``.
        resolved_names_mapping: Pre-resolved ``[{name, type, id}]`` entries for named entities
                                 such as connections or metadata imports.

    Returns:
        A dict representing the ES DSL query body, ready to POST to the GS endpoint.
    """
    instructions = [
        "When asked to search for assets by name, Look for assets that match filter metadata.name. Try to match against singular and plural forms of the name. E.g If the user asks about policies, search for assets with name matching policy or policies",
        "When asked to search for assets related to a keyword, search in: name, semantic name, description, and tags. Include keyword variations ONLY when word forms differ significantly (e.g., 'policy' → 'policies'). Examples: 'policy' → search for 'policy' AND 'policies'; 'analysis' → search for 'analysis' AND 'analyses'; 'investment' → search for 'investment' AND 'investing'. Do NOT add variations when wildcard would suffice. Do NOT use synonyms or unrelated meanings. Apply this to generic questions like 'find assets about X', 'get data related to X'",
        "Only if there is specific named container mentioned in the search prompt apply container id (project_id/catalog_id) filter. E.g find assets related to schools in projects. -> There is no specific project mentioned; Do not apply container filter. E.g find assets related to schools in project 'schools' -> Apply project ID filter",
        "If the user asks about glossary terms, use metadata.artifact_type=glossary_term",
        "When searching for tags, filter by metadata.tags",
        "When asked about abbreviations try to match by name or by entity.artifacts.abbreviation",
    ]
    if artifact_types:
        instructions.append(
            f"Apply filter to match searched data type ->  metadata.artifact_type: {', '.join(artifact_types)}"
        )

    names_to_ids = []
    if (
        container_details
        and container_details.id
        and container_details.type
        and container_details.name
    ):
        names_to_ids.append(
            {
                "name": container_details.name,
                "type": str(container_details.type),
                "id": container_details.id,
            }
        )

    if resolved_names_mapping:
        names_to_ids.extend(resolved_names_mapping)
        LOGGER.info("Added %d resolved entities to names_to_ids", len(resolved_names_mapping))

    text_to_query_payload = {
        "include_raw_model_input_output": False,
        "input_question": search_prompt,
        "parameters": {
            "type": "elastic_query",
            "names_to_ids": names_to_ids,
            "instructions": instructions,
        },
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + TEXT_TO_QUERY_BASE_ENDPOINT,
        json=text_to_query_payload,
    )

    results = response.get("results", [])
    query_data = results[0].get("generated_query", {}) if results else {}
    query_data = parse_and_enrich_query_data(query_data)

    # Ensure query has sort parameter
    if "sort" not in query_data:
        query_data["sort"] = [{"metadata.created_on": "desc"}]

    inject_must_not_exclusions(query_data)

    return query_data


_EXCLUDED_ARTIFACT_TYPES = ["project_mde_settings"]


def inject_must_not_exclusions(query_data: dict) -> None:
    """Inject must_not exclusions into the query to filter out internal artifact types.

    Modifies *query_data* in-place. Works for both top-level bool queries and
    nested bool queries so the exclusions are always applied regardless of what
    the text-to-query API generated.
    """
    if not query_data:
        return

    exclusion_clauses = [
        {"term": {"metadata.artifact_type": t}} for t in _EXCLUDED_ARTIFACT_TYPES
    ]

    query = query_data.get("query", {})
    if "bool" in query:
        must_not = query["bool"].setdefault("must_not", [])
        if isinstance(must_not, list):
            must_not.extend(exclusion_clauses)
    else:
        # Wrap existing query in a bool with must_not
        query_data["query"] = {
            "bool": {
                "must": [query],
                "must_not": exclusion_clauses,
            }
        }


async def fetch_search_page(query: dict) -> dict:
    """Execute a single search page request against the global search endpoint."""
    return await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json=query,
        params={"auth_cache": True, "tenant_scope": True},
    )


async def generate_gs_query(
    search_prompt: str,
    artifact_types: List[str] | None = None,
    container_details: Container | None = None,
    resolved_names_mapping: List[dict] | None = None,
    max_attempts: int = MAX_QUERY_GENERATION_ATTEMPTS,
) -> tuple[dict, dict | None]:
    """Generate an ES DSL query from a natural language prompt, with retry logic.

    Validates each generated query by executing it once against the GS endpoint to
    ensure the query is syntactically valid and returns results.  The validation
    response is returned alongside the query so callers can reuse it and avoid a
    redundant round-trip.

    Args:
        search_prompt: Natural language question from the user.
        artifact_types: Optional list of artifact type filters.
        container_details: Resolved container to scope the query, or ``None``.
        resolved_names_mapping: Pre-resolved named entity mappings with IDs.
        max_attempts: How many generation attempts to make before raising.

    Returns:
        ``(query_data, validation_response)`` — the ES DSL dict and the first
        search response (which can be reused by the caller to skip a second call).

    Raises:
        ExternalAPIError: If the text-to-query or GS API fails on all attempts.
        ServiceError: If all attempts are exhausted for an unexpected reason.
    """
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            LOGGER.info("Query generation attempt %d of %d", attempt + 1, max_attempts)
            query_data = await call_text_to_query_api(
                search_prompt, artifact_types, container_details, resolved_names_mapping
            )

            # Validate query by executing it with the default size to confirm:
            # 1. Query syntax is accepted by the GS API
            # 2. Query actually returns results (empty → retry)
            # 3. API auth and connectivity work
            user_requested_limit = query_data.get("size", MAX_SEARCH_RESULTS)
            validation_size = min(MAX_SEARCH_RESULTS, user_requested_limit)
            test_query = {**query_data, "size": validation_size}
            validation_response: dict = await fetch_search_page(query=test_query)

            LOGGER.info(
                "Query validated successfully on attempt %d with size %d",
                attempt + 1,
                validation_size,
            )
            return query_data, validation_response

        except (ExternalAPIError, ConnectionError, TimeoutError) as e:
            last_exception = e
            LOGGER.warning("Query generation attempt %d failed: %s", attempt + 1, str(e))
            if attempt == max_attempts - 1:
                LOGGER.error(
                    "All %d query generation attempts failed. Last error: %s",
                    max_attempts,
                    str(e),
                )
                raise

    raise last_exception if last_exception else ServiceError("Query generation failed")
