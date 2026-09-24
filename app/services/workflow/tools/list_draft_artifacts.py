# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

"""Tool for listing draft business terms and data classes."""

from typing import Annotated, Optional
from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import GLOSSARY_ARTIFACT_TYPES_ENDPOINT
from app.services.workflow.models.get_artifact_details import ArtifactType
from app.services.workflow.models.list_draft_artifacts import (
    DraftArtifactOverview,
    DraftArtifactType,
    ListDraftArtifactsRequest,
    ListDraftArtifactsResponse,
)
from app.services.workflow.tools.utils import (
    get_artifact_api_endpoint,
    is_draft_metadata,
)
from app.services.tool_utils import get_user_info_from_iam_id
from app.services.workflow.tools.get_artifact_details import (
    _format_artifact_url,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.client_detection import supports_rich_text_format
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ValidationError
from fastmcp.server.context import Context


def _artifact_types_to_fetch(artifact_type: DraftArtifactType) -> list[ArtifactType]:
    """Expand the public artifact type selector into concrete API artifact types."""
    if artifact_type == "all":
        return ["glossary_term", "data_class"]
    return [artifact_type]


def _get_item_metadata(item: dict) -> dict:
    """Return metadata when present, otherwise use the item shape directly."""
    return item.get("metadata", {}) or item


def _extract_artifact_id(item: dict) -> Optional[str]:
    """Extract artifact_id from governance artifact response shapes."""
    metadata = item.get("metadata", {})
    entity = item.get("entity", {})
    artifacts = entity.get("artifacts", {}) if isinstance(entity, dict) else {}
    return (
        metadata.get("artifact_id")
        or item.get("artifact_id")
        or artifacts.get("artifact_id")
    )


def _extract_version_id(item: dict) -> Optional[str]:
    """Extract version_id from governance artifact response shapes."""
    metadata = item.get("metadata", {})
    return (
        metadata.get("version_id")
        or item.get("version_id")
        or metadata.get("global_id")
    )


async def _fetch_draft_version_id(
    artifact_id: str,
    artifact_type: ArtifactType,
) -> Optional[str]:
    """Fetch the draft version id when it is not present in the list response."""
    endpoint = f"{get_artifact_api_endpoint(artifact_type)}/{artifact_id}/versions"
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{endpoint}",
            params={
                "status": "DRAFT",
                "limit": 10,
            },
        )
    except Exception as e:
        LOGGER.warning(
            f"Could not fetch draft version for artifact_id={artifact_id}: {str(e)}"
        )
        return None

    versions = response.get("resources", []) or response.get("versions", [])
    for version in versions:
        metadata = version.get("metadata", {})
        if is_draft_metadata(metadata, version):
            return (
                metadata.get("version_id")
                or version.get("version_id")
                or metadata.get("global_id")
            )

    if versions:
        metadata = versions[0].get("metadata", {})
        return (
            metadata.get("version_id")
            or versions[0].get("version_id")
            or metadata.get("global_id")
        )
    return None


def _is_draft_mode_active(draft_mode) -> bool:
    """Check if draft_mode indicates an active draft state."""
    if draft_mode is True:
        return True
    if isinstance(draft_mode, str) and draft_mode.casefold() == "draft":
        return True
    return False


def _determine_state(metadata: dict, item: dict) -> Optional[str]:
    """Determine the state of an artifact, defaulting to DRAFT if draft_mode is active."""
    state = metadata.get("state") or item.get("state")
    if state is not None:
        return state
    
    draft_mode = metadata.get("draft_mode") or item.get("draft_mode")
    if _is_draft_mode_active(draft_mode):
        return "DRAFT"
    
    return None


async def _resolve_modified_by_name(metadata: dict, item: dict) -> Optional[str]:
    """Resolve modified_by IAM ID to user name, falling back to ID on error."""
    modified_by_id = metadata.get("modified_by") or item.get("modified_by")
    if not modified_by_id:
        return None
    
    try:
        return await get_user_info_from_iam_id(modified_by_id, "name")
    except Exception as e:
        LOGGER.warning(f"Could not fetch user name for ID {modified_by_id}: {str(e)}")
        return modified_by_id


async def _create_draft_artifact_overview(
    item: dict,
    artifact_type: ArtifactType,
) -> Optional[DraftArtifactOverview]:
    """Build one overview object from a governance artifact response item."""
    metadata = _get_item_metadata(item)
    artifact_id = _extract_artifact_id(item)
    name = metadata.get("name") or item.get("name")

    if not artifact_id or not name:
        LOGGER.warning(f"Skipping draft artifact with missing id or name: {item}")
        return None

    version_id = _extract_version_id(item)
    if not version_id:
        version_id = await _fetch_draft_version_id(artifact_id, artifact_type)

    state = _determine_state(metadata, item)
    modified_by_name = await _resolve_modified_by_name(metadata, item)

    return DraftArtifactOverview(
        name=name,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        version_id=version_id,
        state=state,
        workflow_id=metadata.get("workflow_id") or item.get("workflow_id"),
        workflow_state=metadata.get("workflow_state") or item.get("workflow_state"),
        created_at=metadata.get("created_at") or item.get("created_at"),
        modified_at=metadata.get("modified_at") or item.get("modified_at"),
        modified_by=modified_by_name,
        url=_format_artifact_url(artifact_id, artifact_type, version_id),
    )


async def _fetch_draft_artifacts_for_type(
    artifact_type: ArtifactType,
    max_results: int,
) -> list[DraftArtifactOverview]:
    """Fetch draft artifact overviews for one artifact type."""
    fetch_limit = min(max_results * 3, 200)
    endpoint = f"{GLOSSARY_ARTIFACT_TYPES_ENDPOINT}/{artifact_type}"
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{endpoint}",
            params={
                "sub_string": "",
                "limit": fetch_limit,
            },
        )
    except Exception as e:
        LOGGER.error(f"Failed to fetch draft artifacts for {artifact_type}: {str(e)}")
        return []

    # Handle None response or missing resources
    if response is None:
        LOGGER.warning(f"Received None response for artifact_type={artifact_type}")
        return []
    
    artifacts: list[DraftArtifactOverview] = []
    resources = response.get("resources", [])
    if resources is None:
        LOGGER.warning(f"Received None resources for artifact_type={artifact_type}")
        return []
    
    for item in resources:
        metadata = item.get("metadata", {})
        if not is_draft_metadata(metadata, item):
            continue

        overview = await _create_draft_artifact_overview(item, artifact_type)
        if overview:
            artifacts.append(overview)
        if len(artifacts) >= max_results:
            break

    return artifacts


def _format_draft_artifacts_as_table(artifacts: list[DraftArtifactOverview]) -> str | None:
    """Format draft artifact overviews as a markdown table."""
    if not artifacts:
        return None

    # Add summary with total count
    lines = [
        f"**Found {len(artifacts)} draft artifact(s)**\n",
        "| Name | Type | Modified By | Link |",
        "| --- | --- | --- | --- |",
    ]
    for artifact in artifacts:
        # Shorten URL with markdown link
        url_display = f"[View]({artifact.url})" if artifact.url else ""
        lines.append(
            "| "
            f"{artifact.name or ''} | "
            f"{artifact.artifact_type or ''} | "
            f"{artifact.modified_by or ''} | "
            f"{url_display} |"
        )
    return "\n".join(lines)


async def _list_draft_artifacts(
    request: ListDraftArtifactsRequest,
    ctx: Optional[Context] = None,
) -> ListDraftArtifactsResponse:
    """List draft business terms and/or data classes."""
    LOGGER.info(
        f"Listing draft artifacts for artifact_type={request.artifact_type}, "
        f"max_results={request.max_results}, format={request.format}"
    )

    if not supports_rich_text_format(ctx) and request.format == "table":
        LOGGER.info("Client without rich text support detected: switching format from 'table' to 'json'")
        request.format = "json"

    artifacts: list[DraftArtifactOverview] = []
    concrete_types = _artifact_types_to_fetch(request.artifact_type)

    for artifact_type in concrete_types:
        artifacts.extend(
            await _fetch_draft_artifacts_for_type(artifact_type, request.max_results)
        )

    artifacts = artifacts[:request.max_results]

    formatted_output = None
    if request.format == "table":
        formatted_output = _format_draft_artifacts_as_table(artifacts)
    elif request.format != "json":
        raise ValidationError(
            "Invalid output format. Must be one of: 'table', 'json'.",
            service="workflow",
            tool="list_draft_artifacts",
            remediation_steps="Retry with format set to either 'table' or 'json'.",
        )

    return ListDraftArtifactsResponse(
        artifacts=artifacts,
        total_count=len(artifacts),
        formatted_output=formatted_output,
    )


list_draft_artifacts_description = """
List draft workflow glossary artifacts.

**When to use this tool:**
- When you need to see all draft business terms and/or data classes
- When you want an overview of artifacts currently in workflow
- When you need to find which artifacts are pending approval

**Example:**
To list all draft artifacts (both business terms and data classes):
- artifact_type: "all"
- max_results: 50
- format: "table"

To list only draft business terms:
- artifact_type: "glossary_term"
- max_results: 50
- format: "table"

**Returns:**
A ListDraftArtifactsResponse containing:
- artifacts: List of DraftArtifactOverview objects with complete details for each draft
- total_count: Number of draft artifacts returned
- formatted_output: Markdown table showing Name, Type, Modified By, and Link (when format="table")

The table displays user-friendly information (with shortened URLs as clickable links) while the JSON
response includes all technical details (artifact IDs, version IDs, workflow IDs, states, timestamps).
"""


@service_registry.tool(
    name="list_draft_artifacts",
    annotations={
        "readOnlyHint": True,
        "title": "List Draft Workflow Glossary Artifacts: Business Terms and Data Classes"
    },
    description=list_draft_artifacts_description,
    tags={"workflow", "glossary", "artifacts", "drafts", "governance","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "glossary"},
)
@auto_context
async def list_draft_artifacts(
    artifact_type: Annotated[DraftArtifactType, Field(description="Type of artifacts to list: 'glossary_term' for business terms, 'data_class' for data classes, or 'all' for both")] = "all",
    max_results: Annotated[int, Field(description="Maximum number of draft artifacts to return (default: 50)")] = 50,
    format: Annotated[str, Field(description="Output format: 'table' for markdown table or 'json' for structured data only")] = "table",
    ctx: Context = None,
) -> ListDraftArtifactsResponse:
    """
    List draft business terms and data classes.

    Args:
        artifact_type: Artifact type to list: 'glossary_term', 'data_class', or 'all'
        max_results: Maximum number of draft artifacts to return
        format: Output format ('table' for formatted output, 'json' for structured data)
        ctx: Optional MCP Context

    Returns:
        ListDraftArtifactsResponse with draft artifact overviews
    """
    request = ListDraftArtifactsRequest(
        artifact_type=artifact_type,
        max_results=max_results,
        format=format,
    )
    return await _list_draft_artifacts(request, ctx)
