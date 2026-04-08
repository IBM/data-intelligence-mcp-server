# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Dict, List, Literal, Optional

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.services.glossary.constants import (
    METADATA_NAME,
    NO_GLOSSARY_ARTIFACTS_FOUND_MESSAGE,
    NO_GLOSSARY_ARTIFACTS_FOR_ASSET_IN_CONTAINER_MESSAGE,
)
from app.services.glossary.models.glossary_artifact import (
    GetGlossaryArtifactsForAssetRequest,
    GlossaryArtifact,
)
from app.services.tool_utils import find_asset_id, find_catalog_id, find_project_id
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.helpers import append_context_to_url, confirm_uuid, is_uuid_bool as is_uuid
from app.shared.utils.tool_helper_service import tool_helper_service

def _extract_glossary_artifacts_from_metadata(metadata: Dict) -> List[GlossaryArtifact]:
    """
    Extract glossary terms and classifications from Global Search metadata.
    
    Args:
        metadata: Metadata dictionary from global search response
        
    Returns:
        List of GlossaryArtifact models
    """
    results: List[GlossaryArtifact] = []

    # Extract terms
    term_ids = metadata.get("term_global_ids", [])
    term_names = metadata.get("terms", [])

    for term_id, term_name in zip(term_ids, term_names):
        version_id = _fetch_version_id(term_name)
        url = f"{tool_helper_service.ui_base_url}/v3/glossary_terms/glossary_terms/{term_id}/versions/{version_id}"
        
        results.append(
            GlossaryArtifact(
                id=term_id,
                name=term_name,
                artifact_type="term",
                url=append_context_to_url(url)
            )
        )

    # Extract classifications
    class_ids = metadata.get("classification_global_ids", [])
    class_names = metadata.get("classifications", [])

    for class_id, class_name in zip(class_ids, class_names):
        version_id = _fetch_version_id(class_name)
        url = f"{tool_helper_service.ui_base_url}/v3/glossary_terms/classifications/{class_id}/versions/{version_id}"
        
        results.append(
            GlossaryArtifact(
                id=class_id,
                name=class_name,
                artifact_type="classification",
                url=append_context_to_url(url)
            )
        )

    return results


async def _fetch_version_id(name: str) -> Optional[str]:
    """
    Fetch version ID for a glossary artifact by name.
    
    Args:
        name: Name of the glossary artifact
        
    Returns:
        Version ID if found, None otherwise
    """
    payload = {
        "query": {
            "bool": {
                "must": [
                    {"match": {METADATA_NAME: {"query": name}}}
                ]
            }
        }
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json=payload,
        params={"auth_cache": True},
    )

    rows = response.get("rows", [])
    if rows:
        return rows[0].get("entity", {}).get("artifacts", {}).get("version_id")
    return None


def _format_glossary_artifacts_for_display(artifacts: List[GlossaryArtifact]) -> str:
    """
    Format glossary artifacts for display to the user.
    
    Args:
        artifacts: List of glossary artifacts
        
    Returns:
        Formatted string representations
    """
    if not artifacts:
        return NO_GLOSSARY_ARTIFACTS_FOUND_MESSAGE
    
    result_lines = [f"Found {len(artifacts)} glossary artifact(s):"]
    for artifact in artifacts:
        artifact_type = artifact.artifact_type.replace("_", " ").capitalize()
        result_lines.append(f"- {artifact.name} ({artifact_type}): {artifact.url}")
    
    return "\n".join(result_lines)


@service_registry.tool(
    name="get_glossary_artifacts_for_asset",
    description="""Retrieve all business terms and classifications (these are the only two supported types of glossary artifacts) associated with a specific asset.
    When a user requests "get/list glossary items" without specifying asset details, prompt them to provide the following required parameters: asset_id_or_name, container_id_or_name, and container_type.

    This tool finds all glossary terms and classification that have been assigned to a particular asset.
    This helps understand the business context and semantic meaning of the asset.""",
)
@auto_context
async def get_glossary_artifacts_for_asset(
    request: GetGlossaryArtifactsForAssetRequest,
) -> str:
    """
    Retrieve glossary artifacts associated with an asset.
    
    Args:
        request: Request containing asset and container information
        
    Returns:
        Formatted string with glossary artifacts information
        
    Raises:
        ServiceError: If the artifacts cannot be retrieved
    """
    LOGGER.info(
        f"get_glossary_artifacts_for_asset called with asset_id_or_name={request.asset_id_or_name}, "
        f"container_id_or_name={request.container_id_or_name}, container_type={request.container_type}"
    )

    # Resolve container ID
    container_id = await confirm_uuid(
        request.container_id_or_name,
        find_catalog_id if request.container_type == "catalog" else find_project_id,
    )

    # Resolve asset ID
    asset_id = await confirm_uuid(
        request.asset_id_or_name,
        lambda name: find_asset_id(name, container_id, request.container_type),
    )

    # Build search query
    if is_uuid(request.asset_id_or_name):
        asset_match = {"match": {"artifact_id": asset_id}}
    else:
        asset_match = {"match": {METADATA_NAME: request.asset_id_or_name}}

    container_match = {
        "match": {
            f"entity.assets.{request.container_type}_id": container_id
        }
    }

    payload = {
        "query": {
            "bool": {
                "must": [
                    asset_match,
                    container_match
                ]
            }
        }
    }

    params = {
        "role": "viewer",
        "auth_cache": True,
        "auth_scope": request.container_type
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json=payload,
        params=params,
    )

    rows = response.get("rows", [])
    if not rows:
        return NO_GLOSSARY_ARTIFACTS_FOR_ASSET_IN_CONTAINER_MESSAGE.format(
            asset=request.asset_id_or_name,
            container_type=request.container_type,
            container=request.container_id_or_name
        )
    
    metadata = rows[0].get("metadata", {})
    results = _extract_glossary_artifacts_from_metadata(metadata)

    if not results:
        return NO_GLOSSARY_ARTIFACTS_FOR_ASSET_IN_CONTAINER_MESSAGE.format(
            asset=request.asset_id_or_name,
            container_type=request.container_type,
            container=request.container_id_or_name
        )

    if results:
        ui_message_context.add_table_ui_message(
            tool_name="get_glossary_artifacts_for_asset",
            formatted_data=_format_glossary_artifacts_for_table(results),
            title="Glossary artifacts",
        )
    return _format_glossary_artifacts_for_display(results)


@service_registry.tool(
    name="get_glossary_artifacts_for_asset",
    description="""Retrieve all business terms and classifications associated with a specific asset.
    
    This tool finds all glossary terms and classification that have been assigned to a particular asset.
    This helps understand the business context and semantic meaning of the asset.""",
)
@auto_context
async def wxo_get_glossary_artifacts_for_asset(
    asset_id_or_name: str,
    container_id_or_name: str,
    container_type: Literal["catalog", "project"],
) -> str:
    """Watsonx Orchestrator compatible version of get_glossary_artifacts_for_asset."""
    request = GetGlossaryArtifactsForAssetRequest(
        asset_id_or_name=asset_id_or_name,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
    )
    return await get_glossary_artifacts_for_asset(request)

def _format_glossary_artifacts_for_table(artifacts: list[GlossaryArtifact]) -> list:
    return [
        {
            "Name": ui_message_context.create_markdown_link(item.url, item.name),
            "Type": item.artifact_type.replace("_", " ").capitalize(),
        }
        for item in artifacts
    ]