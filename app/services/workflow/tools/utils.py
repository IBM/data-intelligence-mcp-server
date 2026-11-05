# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""
Utility functions for workflow tools.

This module provides shared utility functions for querying glossary artifacts
(data classes and business terms) from the workflow service, and for the
shared artifact-selection elicitation used by the list tools.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple, Union  # noqa: I001, UP035 # Baseline
from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.server.elicitation import get_elicitation_schema
from pydantic import create_model
import mcp_types
from app.services.workflow.models.artifact import Artifact, BusinessTerm, DataClass  # noqa: F401 # Baseline
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.llm_utils import client_supports_elicitation
from app.services.constants import SEARCH_PATH, GLOSSARY_ARTIFACT_TYPES_ENDPOINT
from app.shared.exceptions.base import ServiceError, ValidationError, ExternalAPIError  # noqa: F401 # Baseline

ZERO_MINUTES = "+00:00"
ELICITATION_WATERMARK = 10


def _create_artifact_from_item(item: dict, artifact_type: str):  # noqa: ANN202 # Baseline
    """
    Create appropriate artifact object based on artifact type.

    Args:
        item: Dictionary containing artifact data
        artifact_type: Type of artifact ('glossary_term' or 'data_class')

    Returns:
        BusinessTerm, DataClass, or Artifact object
    """
    from app.services.workflow.models.artifact import Artifact, BusinessTerm, DataClass  # noqa: F811, I001 # Baseline

    common_fields = {
        "name": item.get("name"),
        "description": item.get("long_description") or item.get("description"),
        "artifact_id": item.get("artifact_id"),
        "modified_by": item.get("modified_by"),
        "state": item.get("draft_mode") or item.get("state"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "workflow_id": item.get("workflow_id"),
        "artifact_type": artifact_type,
        "version_id": item.get("version_id"),  # Include version_id if available
    }

    if artifact_type == "glossary_term":
        return BusinessTerm(**common_fields)
    if artifact_type == "data_class":
        return DataClass(**common_fields)
    return Artifact(**common_fields)


def validate_search_params(
    search_term: str, artifact_type: str, max_results: int
) -> None:
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

    valid_artifact_types = ["glossary_term", "data_class"]
    if artifact_type not in valid_artifact_types:
        raise ValueError(
            f"artifact_type must be one of {valid_artifact_types}, got '{artifact_type}'"
        )

    if max_results <= 0:
        raise ValueError(f"max_results must be positive, got {max_results}")

    if max_results > 100:  # noqa: PLR2004 # Baseline
        LOGGER.warning(f"max_results ({max_results}) exceeds recommended limit of 100")


# ---------------------------------------------------------------------------
# Shared artifact-selection elicitation
# ---------------------------------------------------------------------------


def _build_selection_model(artifact_names: List[str], selection_field: str) -> type:  # noqa: UP006 # Baseline
    """
    Create a dynamic pydantic elicitation model constrained to the given names.

    Args:
        artifact_names: Names of the artifacts on the current page.
        selection_field: Field name of the selection (e.g. 'selected_term').

    Returns:
        A pydantic model class with a single Literal field that defaults to
        the first artifact name.
    """
    SelectionLiteral = Literal[tuple(artifact_names)]  # noqa: N806 # Baseline
    return create_model(
        "DynamicElicitationModel",
        **{selection_field: (SelectionLiteral, artifact_names[0])},
    )


def _select_single_item(
    selected_name: str,
    artifacts: List,  # noqa: UP006 # Baseline
    artifact_names: List[str],  # noqa: UP006 # Baseline
) -> Optional[List]:  # noqa: UP006, UP045 # Baseline
    """
    Resolve a selected artifact name to a single-item page.

    Args:
        selected_name: Name selected by the user.
        artifacts: Artifacts on the current page.
        artifact_names: Names of the artifacts on the current page.

    Returns:
        A single-item list, or None when the name is not on the current page.
    """
    try:
        idx = artifact_names.index(selected_name)
    except ValueError:
        LOGGER.warning(f"Selected item '{selected_name}' not found in current page")
        return None
    if 0 <= idx < len(artifacts):
        return artifacts[idx : idx + 1]
    return None


def _validated_selection(
    content: Any,
    model: type,
    artifacts: List,  # noqa: UP006 # Baseline
    artifact_names: List[str],  # noqa: UP006 # Baseline
    selection_field: str,
) -> Optional[List]:  # noqa: UP006, UP045 # Baseline
    """
    Validate raw elicitation content against the dynamic model (modern protocol).

    Returns a single-item list on success, or None when validation fails.
    """
    try:
        validated = model.model_validate(content)
        selected_name = getattr(validated, selection_field)
        LOGGER.info(f"Elicitation accepted: {selected_name}")
        return _select_single_item(selected_name, artifacts, artifact_names)
    except Exception as exc:
        LOGGER.warning(f"Failed to validate elicitation response: {exc}")
        return None


def _is_modern_elicitation_ctx(ctx: Any) -> bool:
    """
    Check whether ctx uses the modern sessionless elicitation protocol (2026-07-28+).

    The context must advertise the protocol via ``_is_modern_protocol()`` and
    carry its ``input_responses`` in a dict-or-None shape.
    """
    if not (hasattr(ctx, "_is_modern_protocol") and ctx._is_modern_protocol()):
        return False
    return isinstance(getattr(ctx, "input_responses", None), (dict, type(None)))


def _apply_modern_elicitation_response(
    resp: Any,
    artifacts: List,  # noqa: UP006 # Baseline
    artifact_names: List[str],  # noqa: UP006 # Baseline
    model: type,
    selection_field: str,
) -> List:  # noqa: UP006 # Baseline
    """Apply a received modern-protocol response; always returns the final page."""
    if not isinstance(resp, mcp_types.ElicitResult):
        return artifacts
    if resp.action == "accept" and resp.content:
        selected = _validated_selection(
            resp.content, model, artifacts, artifact_names, selection_field
        )
        if selected is not None:
            return selected
    else:
        LOGGER.info(f"Elicitation declined or cancelled (modern, action={resp.action})")
    return artifacts


def _build_input_required_result(
    model: type, input_id: str, message: str
) -> mcp_types.InputRequiredResult:
    """Build the guard result that asks the client for a selection (modern protocol)."""
    LOGGER.info(f"Returning InputRequiredResult for '{input_id}'")
    schema = get_elicitation_schema(model)
    elicit_req = mcp_types.ElicitRequest(
        params=mcp_types.ElicitRequestFormParams(
            message=message,
            requestedSchema=schema,
        )
    )
    return mcp_types.InputRequiredResult(input_requests={input_id: elicit_req})


def _handle_modern_elicitation(  # noqa: PLR0913 # Baseline
    artifacts: List,  # noqa: UP006 # Baseline
    artifact_names: List[str],  # noqa: UP006 # Baseline
    model: type,
    ctx: Any,
    input_id: str,
    selection_field: str,
    message: str,
) -> Optional[Union[List, mcp_types.InputRequiredResult]]:  # noqa: UP006, UP007, UP045 # Baseline
    """
    Handle the modern sessionless protocol (guard / InputRequiredResult pattern).

    Returns:
        The final page (or a single-selection subset), an InputRequiredResult
        when the client still needs to answer, or None when ctx does not use
        the modern protocol so the caller should fall back to the legacy one.
    """
    if not _is_modern_elicitation_ctx(ctx):
        return None
    input_responses = getattr(ctx, "input_responses", None)
    if input_responses is not None and input_id in input_responses:
        return _apply_modern_elicitation_response(
            input_responses[input_id], artifacts, artifact_names, model, selection_field
        )
    return _build_input_required_result(model, input_id, message)


def _accepted_legacy_selection(
    response: Any,
    artifacts: List,  # noqa: UP006 # Baseline
    artifact_names: List[str],  # noqa: UP006 # Baseline
    selection_field: str,
) -> Optional[List]:  # noqa: UP006, UP045 # Baseline
    """Extract the single selected item from a legacy-protocol elicitation response."""
    if response is None or response.action != "accept":
        LOGGER.info("Elicitation declined or no selection made")
        return None
    selected_name = getattr(response.data, selection_field)
    LOGGER.info(f"Elicitation accepted: {selected_name}")
    return _select_single_item(selected_name, artifacts, artifact_names)


async def _handle_legacy_elicitation(  # noqa: PLR0913 # Baseline
    artifacts: List,  # noqa: UP006 # Baseline
    artifact_names: List[str],  # noqa: UP006 # Baseline
    model: type,
    ctx: Any,
    message: str,
    selection_field: str,
) -> List:  # noqa: UP006 # Baseline
    """Run the legacy stateful elicitation (ctx.elicit()) and apply the response."""
    try:
        response = await ctx.elicit(message=message, response_type=model)
        LOGGER.info(f"Elicitation response: {response!s}")
        selected = _accepted_legacy_selection(
            response, artifacts, artifact_names, selection_field
        )
        if selected is not None:
            return selected
    except Exception as elicit_e:
        LOGGER.warning(f"Failed to call elicitation: {elicit_e!s}")
    return artifacts


async def handle_artifact_selection_elicitation(
    artifacts: List,  # noqa: UP006 # Baseline
    ctx: Optional[Context],  # noqa: UP045 # Baseline
    input_id: str,
    selection_field: str,
    item_label: str,
) -> Union[List, mcp_types.InputRequiredResult]:  # noqa: UP006, UP007 # Baseline
    """
    Handle user elicitation to select a single artifact from the current page.

    Supports both the modern sessionless protocol (2026-07-28+, guard pattern)
    and the legacy stateful protocol (ctx.elicit()).

    Args:
        artifacts: Artifacts on the current page; each must expose a ``name`` attribute.
        ctx: MCP context for elicitation.
        input_id: Unique key for this tool's elicitation request/response.
        selection_field: Field name of the selection in the dynamic elicitation model.
        item_label: Plural artifact label for the user-facing message (e.g. 'business terms').

    Returns:
        Subset of artifacts (either all or a single selection), or an
        InputRequiredResult when the modern protocol still needs input from
        the client (must be propagated up as the tool result).
    """
    if len(artifacts) <= ELICITATION_WATERMARK or ctx is None:
        return artifacts

    # Check if both client and server support elicitation
    # If not supported, return full result set (following decline/cancel path)
    if not client_supports_elicitation(ctx):
        LOGGER.info(
            "Elicitation not supported by client or server - returning full result set"
        )
        return artifacts

    artifact_names = [artifact.name for artifact in artifacts]
    model = _build_selection_model(artifact_names, selection_field)
    message = f"Please select one of the {len(artifact_names)} {item_label}"

    modern_result = _handle_modern_elicitation(
        artifacts, artifact_names, model, ctx, input_id, selection_field, message
    )
    if modern_result is not None:
        return modern_result

    return await _handle_legacy_elicitation(
        artifacts, artifact_names, model, ctx, message, selection_field
    )


async def _query_artifact_in_draft_by_term(
    search_term: str,
    artifact_type: str,
    max_results: int,
    offset: int = 0,
) -> Tuple[List[Artifact], int]:  # noqa: UP006 # Baseline
    """
    Query the glossary API for artifacts in draft mode.

    Args:
        search_term: Search term matching name or description.
        artifact_type: Artifact type string, e.g. 'data_class' or 'glossary_term'.
        max_results: Maximum number of artifacts to return (page size).
        offset: Zero-based index of the first artifact to return.

    Returns:
        Tuple of (list of matching draft Artifact objects, total_count).
        total_count is the total number of draft artifacts across all pages;
        -1 is returned when the API does not expose a count.

    Raises:
        ValueError: If search parameters are invalid.
    """
    # Validate input parameters
    validate_search_params(search_term, artifact_type, max_results)

    # Fetch a window large enough to cover offset + page without over-fetching excessively
    fetch_limit = (offset + max_results) * 3
    params = {"sub_string": search_term, "limit": fetch_limit}
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{GLOSSARY_ARTIFACT_TYPES_ENDPOINT}/{artifact_type}",
            params=params,
        )

        # Handle None response or missing resources
        if response is None:
            LOGGER.warning(f"Received None response for artifact_type={artifact_type}")
            return [], 0

        all_draft_artifacts = []
        item_list = response.get("resources", [])
        if item_list is None:
            LOGGER.warning(f"Received None resources for artifact_type={artifact_type}")
            return [], 0

        for item in item_list:
            # Only include artifacts that are in draft state
            # Draft artifacts have workflow_id or draft_mode=True or state="DRAFT"
            is_draft = (
                item.get("workflow_id") is not None
                or item.get("draft_mode") is True
                or (item.get("state") and item.get("state").upper() == "DRAFT")
            )

            if is_draft:
                artifact_obj = _create_artifact_from_item(item, artifact_type)
                all_draft_artifacts.append(artifact_obj)

        total_count = len(all_draft_artifacts)
        page = all_draft_artifacts[offset : offset + max_results]
        return page, total_count

    except ValueError:
        # Re-raise validation errors
        raise
    except KeyError as e:
        error_msg = f"Missing required field in draft artifact response for '{artifact_type}': {e!s}"
        LOGGER.error(error_msg)
        raise ServiceError(
            error_msg,
            service="workflow",
            tool="query_artifact_in_draft",
            remediation_steps=f"Verify the glossary API is returning complete data for artifact type '{artifact_type}'. Contact support if the issue persists.",
        ) from e
    except (ConnectionError, TimeoutError) as e:
        error_msg = f"Network error while querying draft artifacts for '{artifact_type}' with search term '{search_term}': {e!s}"
        LOGGER.error(error_msg)
        raise ExternalAPIError(
            error_msg,
            service="workflow",
            tool="query_artifact_in_draft",
            remediation_steps="Check network connectivity and verify the glossary service is accessible. Retry the operation after ensuring network stability.",
        ) from e
    except Exception as e:
        error_msg = f"Unexpected error querying glossary artifacts in draft mode for '{artifact_type}' with search term '{search_term}': {e!s}"
        LOGGER.error(error_msg)
        raise ServiceError(
            error_msg,
            service="workflow",
            tool="query_artifact_in_draft",
            remediation_steps=f"Verify that artifact type '{artifact_type}' is valid and the glossary service is functioning correctly. Check the service logs for more details.",
        ) from e


async def _query_artifacts_by_term(
    search_term: str,
    artifact_type: str,
    max_results: int,
    offset: int = 0,
) -> Tuple[List[Artifact], int]:  # noqa: UP006 # Baseline
    """
    Use the global search API for artifacts.

    Args:
        search_term: Search term matching name or description.
        artifact_type: Artifact type string, e.g. 'data_class' or 'glossary_term'.
        max_results: Maximum number of artifacts to return (page size).
        offset: Zero-based index of the first artifact to return
                (maps to Elasticsearch ``from``).

    Returns:
        Tuple of (list of matching Artifact objects, total_count).
        total_count is the value of ``size`` in the Elasticsearch response;
        -1 is returned when it is absent.

    Raises:
        ValueError: If search parameters are invalid.
    """
    # Validate input parameters
    validate_search_params(search_term, artifact_type, max_results)

    query_string = f"(metadata.name:{search_term}~1 OR metadata.description:{search_term}~1) AND metadata.artifact_type:{artifact_type}"
    payload = {
        "from": offset,
        "size": max_results,
        "_source": ["*"],
        "query": {"query_string": {"query": query_string}},
    }

    params = {}

    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}{SEARCH_PATH}",
            params={**params, "tenant_scope": True},
            json=payload,
        )

        if response is None:
            LOGGER.warning(f"Received None response for artifact_type={artifact_type}")
            return [], 0

        # Schema: { "size": 3, "rows": [ { "last_updated_at": ..., "metadata": { ... }, "entity": { ... } } ] }
        # "size" in the ES response is the total hit count (not the page size).
        total_count: int = -1
        raw_total = response.get("size")
        if raw_total is not None:
            try:
                total_count = int(raw_total)
            except (TypeError, ValueError):
                LOGGER.warning(f"Could not parse ES 'size' field as int: {raw_total!r}")

        artifact_objs = []
        item_list = response.get("rows", [])
        if item_list is None:
            LOGGER.warning(f"Received None rows for artifact_type={artifact_type}")
            return [], max(0, total_count)

        for artifact in item_list:
            metadata = artifact.get("metadata", {})
            entity = artifact.get("entity", {})
            LOGGER.debug(f"Processing entity: {entity}")
            artifacts = entity.get("artifacts", {})

            # Prepare item dict for artifact creation
            item = {
                "name": metadata.get("name"),
                "description": metadata.get("description"),
                "artifact_id": artifacts.get("artifact_id"),
                "modified_by": metadata.get("modified_by"),
                "state": entity.get("state"),
                "created_at": metadata.get("created_at"),
            }

            artifact_obj = _create_artifact_from_item(item, artifact_type)
            artifact_objs.append(artifact_obj)

        # Fall back to page length if ES didn't return a total
        if total_count < 0:
            total_count = offset + len(artifact_objs)

        return artifact_objs, total_count

    except ValueError:
        # Re-raise validation errors
        raise
    except KeyError as e:
        error_msg = f"Missing required field in artifact search response for '{artifact_type}': {e!s}"
        LOGGER.error(error_msg)
        raise ServiceError(
            error_msg,
            service="workflow",
            tool="query_artifacts_by_term",
            remediation_steps=f"Verify the search API is returning complete data for artifact type '{artifact_type}'. Contact support if the issue persists.",
        ) from e
    except (ConnectionError, TimeoutError) as e:
        error_msg = f"Network error while searching artifacts for '{artifact_type}' with search term '{search_term}': {e!s}"
        LOGGER.error(error_msg)
        raise ExternalAPIError(
            error_msg,
            service="workflow",
            tool="query_artifacts_by_term",
            remediation_steps="Check network connectivity and verify the search service is accessible. Retry the operation after ensuring network stability.",
        ) from e
    except Exception as e:
        error_msg = f"Unexpected error querying glossary artifacts for '{artifact_type}' with search term '{search_term}': {e!s}"
        LOGGER.error(error_msg)
        raise ServiceError(
            error_msg,
            service="workflow",
            tool="query_artifacts_by_term",
            remediation_steps=f"Verify that artifact type '{artifact_type}' is valid and the search service is functioning correctly. Check the service logs for more details.",
        ) from e


# Helper functions for artifact details
from app.services.constants import (  # noqa: E402 # Baseline
    GLOSSARY_BUSINESS_TERMS_ENDPOINT,
    GLOSSARY_DATA_CLASS_ENDPOINT,
)
from app.services.tool_utils import get_user_info_from_iam_id  # noqa: E402 # Baseline


def get_artifact_api_endpoint(artifact_type: str) -> str:
    """Return the dedicated details API endpoint for the requested artifact type."""
    if artifact_type == "glossary_term":
        return GLOSSARY_BUSINESS_TERMS_ENDPOINT
    if artifact_type == "data_class":
        return GLOSSARY_DATA_CLASS_ENDPOINT
    raise ToolError(
        f"Unsupported artifact_type '{artifact_type}'. "
        "Must be one of: 'glossary_term', 'data_class'."
    )


def get_artifact_search_endpoint(artifact_type: str) -> str:
    """Return the governance artifact types endpoint for resolving artifact names."""
    return f"{GLOSSARY_ARTIFACT_TYPES_ENDPOINT}/{artifact_type}"


def is_draft_metadata(metadata: dict, response: Optional[dict] = None) -> bool:  # noqa: UP045 # Baseline
    """Check draft state across the metadata shapes returned by glossary APIs."""
    response = response or {}
    state = metadata.get("state") or response.get("state")
    draft_mode = metadata.get("draft_mode") or response.get("draft_mode")
    return (
        (isinstance(state, str) and state.upper() == "DRAFT")
        or metadata.get("workflow_id") is not None
        or response.get("workflow_id") is not None
        or draft_mode is True
        or (isinstance(draft_mode, str) and draft_mode.casefold() == "draft")
    )


def extract_artifact_id(item: dict) -> Optional[str]:  # noqa: UP045 # Baseline
    """Extract artifact_id from the response shapes used by glossary APIs."""
    metadata = item.get("metadata", {})
    entity = item.get("entity", {})
    artifacts = entity.get("artifacts", {}) if isinstance(entity, dict) else {}
    return (
        metadata.get("artifact_id")
        or item.get("artifact_id")
        or artifacts.get("artifact_id")
    )


def extract_artifact_name(item: dict) -> Optional[str]:  # noqa: UP045 # Baseline
    """Extract artifact name from the response shapes used by glossary APIs."""
    metadata = item.get("metadata", {})
    return metadata.get("name") or item.get("name")


def extract_version_id(version: dict) -> Optional[str]:  # noqa: UP045 # Baseline
    """Extract version_id from a version list response item."""
    metadata = version.get("metadata", {})
    return (
        metadata.get("version_id")
        or version.get("version_id")
        or metadata.get("global_id")
    )


def extract_relationships(relationships_response: dict) -> List[Dict]:  # noqa: UP006 # Baseline
    """
    Extract and format relationships from the API response.

    The API response structure:
    - Top level keys are relationship types (e.g., 'is_a_type_of_terms', 'parent_category')
    - Each relationship type contains a 'resources' array
    - Each resource has 'entity.parent_name' for the name and 'entity.relationship_type' for the type

    Returns:
        List of relationship dictionaries with 'name' and 'type' keys
    """
    relationships = []

    for key, value in relationships_response.items():
        if key == "custom_relationships":
            relationships.extend(_extract_custom_relationships(value))
        else:
            relationships.extend(_extract_standard_relationships(key, value))

    return relationships


def _extract_custom_relationships(custom_rels_value) -> List[Dict]:  # noqa: ANN001, UP006 # Baseline
    """Extract custom relationships from the response."""
    relationships = []
    custom_rels = custom_rels_value if isinstance(custom_rels_value, list) else []

    for custom_rel in custom_rels:
        if isinstance(custom_rel, dict):
            name = custom_rel.get("name", "Unknown")
            relationships.append({"name": name, "type": "custom"})

    return relationships


def _extract_standard_relationships(key: str, value) -> List[Dict]:  # noqa: ANN001, UP006 # Baseline
    """Extract standard relationships from a relationship type key."""
    relationships = []

    if not isinstance(value, dict):
        return relationships

    resources = value.get("resources", [])

    for item in resources:
        if not isinstance(item, dict):
            continue

        relationship = _extract_relationship_from_item(item, key)
        if relationship:
            relationships.append(relationship)

    return relationships


def _extract_relationship_from_item(item: dict, default_type: str) -> Optional[Dict]:  # noqa: UP006, UP045 # Baseline
    """Extract a single relationship from a resource item."""
    entity = item.get("entity", {})
    metadata = item.get("metadata", {})

    # Extract name from multiple possible sources
    name = _get_relationship_name(entity, metadata)
    if not name:
        return None

    # Extract type from entity or use default
    rel_type = _get_relationship_type(entity, default_type)

    return {"name": name, "type": rel_type}


def _get_relationship_name(entity: dict, metadata: dict) -> Optional[str]:  # noqa: UP045 # Baseline
    """Get relationship name from entity or metadata."""
    if isinstance(entity, dict):
        parent_name = entity.get("parent_name")
        if parent_name:
            return parent_name
        entity_name = entity.get("name")
        if entity_name:
            return entity_name

    if isinstance(metadata, dict):
        metadata_name = metadata.get("name")
        if metadata_name:
            return metadata_name

    return None


def _get_relationship_type(entity: dict, default_type: str) -> str:
    """Get relationship type from entity or use default."""
    if isinstance(entity, dict):
        entity_rel_type = entity.get("relationship_type")
        if entity_rel_type:
            return entity_rel_type

    return default_type


async def fetch_steward_names(steward_ids: Optional[List[str]]) -> List[str]:  # noqa: UP006, UP045 # Baseline
    """Fetch steward names from steward IDs using the user profiles API."""
    if not steward_ids:
        return []

    steward_names = []
    for steward_id in steward_ids:
        try:
            # Use the existing utility function to fetch user display name
            name = await get_user_info_from_iam_id(steward_id, "name")
            steward_names.append(name)
        except Exception as e:
            LOGGER.warning(f"Could not fetch steward name for ID {steward_id}: {e!s}")
            steward_names.append(steward_id)  # Fallback to ID if name fetch fails

    return steward_names


def _extract_match_summary(item: dict) -> dict:
    """Extract identifying fields from a search result item for disambiguation."""
    metadata = item.get("metadata", {})
    entity = item.get("entity", {}) if isinstance(item.get("entity"), dict) else {}

    long_description = metadata.get("long_description") or entity.get(
        "long_description"
    )

    return {
        "artifact_id": extract_artifact_id(item),
        "name": extract_artifact_name(item),
        "long_description": long_description,
        "created_at": metadata.get("created_at"),
        "modified_at": metadata.get("modified_at"),
        "workflow_state": metadata.get("workflow_state"),
    }


async def enrich_matches_with_long_description(
    matches: List[dict],  # noqa: UP006 # Baseline
    artifact_api_endpoint: str,
) -> List[dict]:  # noqa: UP006 # Baseline
    """Fetch the draft version for each match to populate long_description.

    long_description lives on the version body at
    /v3/glossary_terms/{id}/versions/{version_id}, not on the root artifact.
    We fetch the latest draft version for each match and read it from there.
    """
    enriched = []
    for match in matches:
        artifact_id = match.get("artifact_id")
        if not artifact_id:
            enriched.append(match)
            continue
        try:
            # Fetch the draft versions list to get the latest version_id
            versions_response = await tool_helper_service.execute_get_request(
                url=f"{tool_helper_service.base_url}{artifact_api_endpoint}/{artifact_id}/versions",
                params={"status": "DRAFT", "limit": 1},
            )
            versions = versions_response.get("resources", []) or versions_response.get(
                "versions", []
            )
            if not versions:
                enriched.append(match)
                continue

            # Read long_description from the version body
            version = versions[0]
            version_id = (
                version.get("metadata", {}).get("version_id")
                or version.get("version_id")
                or version.get("metadata", {}).get("global_id")
            )
            if not version_id:
                enriched.append(match)
                continue

            version_response = await tool_helper_service.execute_get_request(
                url=f"{tool_helper_service.base_url}{artifact_api_endpoint}/{artifact_id}/versions/{version_id}",
            )
            entity = (
                version_response.get("entity", {})
                if isinstance(version_response.get("entity"), dict)
                else {}
            )
            metadata = version_response.get("metadata", {})
            long_desc = (
                entity.get("long_description")
                or metadata.get("long_description")
                or match.get("long_description")
            )
            enriched.append({**match, "long_description": long_desc})
        except Exception as e:
            LOGGER.warning(
                "Could not enrich match artifact_id=%s with long_description: %s",
                artifact_id,
                str(e),
            )
            enriched.append(match)
    return enriched


async def resolve_artifact_id_by_name(
    artifact_name: str,
    artifact_type: str,
) -> Tuple[Optional[str], Optional[List[dict]]]:  # noqa: UP006, UP045 # Baseline
    """Resolve an artifact name to an artifact ID using governance artifact types.

    Returns:
        (artifact_id, None)  when exactly one match is found.
        (None, matches)      when multiple exact-name matches exist; each entry is a
                             dict with keys: artifact_id, name, short_description,
                             created_at, modified_at, workflow_state.

    Raises:
        ToolError: when no artifact is found or artifact_id cannot be extracted.
    """
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}{get_artifact_search_endpoint(artifact_type)}",
        params={
            "starts_with": artifact_name,
            "limit": 10,
        },
    )

    resources = response.get("resources", [])
    LOGGER.debug(
        "resolve_artifact_id_by_name: artifact_name=%r, resources_count=%d, names=%r",
        artifact_name,
        len(resources),
        [
            (extract_artifact_name(item), extract_artifact_id(item))
            for item in resources
        ],
    )
    if not resources:
        raise ToolError(
            f"Could not find {artifact_type} artifact with name '{artifact_name}'"
        )

    exact_matches = [
        item
        for item in resources
        if (extract_artifact_name(item) or "").casefold() == artifact_name.casefold()
    ]
    LOGGER.debug(
        "resolve_artifact_id_by_name: exact_matches_count=%d",
        len(exact_matches),
    )

    if not exact_matches:
        raise ToolError(
            f"Could not find {artifact_type} artifact with exact name '{artifact_name}'"
        )

    # Multiple exact-name matches — return all of them for the caller to disambiguate
    if len(exact_matches) > 1:
        return None, [_extract_match_summary(item) for item in exact_matches]

    selected_artifact = exact_matches[0]

    artifact_id = extract_artifact_id(selected_artifact)
    if not artifact_id:
        raise ToolError(
            f"Could not resolve artifact_id for {artifact_type} artifact '{artifact_name}'"
        )

    return artifact_id, None
