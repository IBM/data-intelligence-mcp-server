# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import json
from typing import Any, Dict, Optional

from fastmcp import Context

from app.core.registry import service_registry
from app.services.constants import GS_BASE_ENDPOINT
from app.services.glossary.constants import (
    ARTIFACT_TYPE_MAPPING,
    METADATA_NAME,
    UNUSED_KEYS,
)
from app.services.glossary.models.glossary_artifact import (
    ExplainGlossaryArtifactRequest,
    GlossaryArtifact,
    GlossaryArtifactDescription,
)
from app.services.glossary.prompts.generate_artifact_description import (
    generate_artifact_description_prompt,
)
from app.services.glossary.utils import is_empty, normalize_key
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url
from app.shared.utils.llm_utils import chat_llm_request, client_supports_sampling
from app.shared.utils.tool_helper_service import tool_helper_service


def _is_unused_key(key: str) -> bool:
    """
    Check if a key should be excluded from metadata cleaning.
    
    Keys are considered unused if they:
    - Are in the UNUSED_KEYS constant list
    - End with 'id', 'ids', 'global_id', or 'global_ids'
    - Contain 'id' anywhere in the key name
    
    Args:
        key: The key name to check
        
    Returns:
        True if the key should be excluded, False otherwise
    """
    key = key.lower()
    return (
        key in UNUSED_KEYS
        or key.endswith(("id", "ids", "global_id", "global_ids"))
        or "id" in key
    )


def _clean_value(value, shorten_text: bool, max_len: int):
    if isinstance(value, dict):
        return _clean_metadata_for_prompt(value, shorten_text, max_len)
    if isinstance(value, list):
        return _clean_list(value, shorten_text, max_len)
    return value


def _clean_list(values: list, shorten_text: bool, max_len: int):
    cleaned = [
        _clean_value(v, shorten_text, max_len)
        for v in values
        if not is_empty(_clean_value(v, shorten_text, max_len))
    ]
    if not cleaned:
        return None
    return cleaned[0] if len(cleaned) == 1 else cleaned


def _clean_metadata_for_prompt(
    data: dict,
    shorten_text: bool = True,
    max_len: int = 500,
) -> dict:
    """
    Clean metadata by removing usused keys and empty values.
    
    Args:
        data: Dictionary to clean
        shorten_text: Whether to shorten text values
        max_len: Maximum length for text values
        
    Returns:
        Cleaned dictionary
    """
    cleaned = {}

    for key, value in data.items():
        if _is_unused_key(key):
            continue

        value = _clean_value(value, shorten_text, max_len)
        if is_empty(value):
            continue

        cleaned[normalize_key(key)] = value

    return cleaned


async def _prepare_description(
    name: str,
    artifact_type: str,
    metadata: dict,
    entity: dict,
    categories: dict,
    ctx: Optional[Context] = None,
) -> tuple[str, bool, Optional[str]]:
    """
    Prepare description for a glossary artifact.
    
    This function intelligently chooses between two approaches:
    1. LLM SAMPLING: If the client supports sampling capability, generates description
       directly using the MCP server's LLM via ctx.sample()
    2. METAPROMPTING: If sampling is not supported, returns a prompt for the calling
       model to generate the description
    
    Args:
        name: Artifact name
        artifact_type: Type of artifact
        metadata: Metadata dictionary
        entity: Entity dictionary
        categories: Categories dictionary
        ctx: Optional MCP Context for checking capabilities and LLM sampling
        
    Returns:
        Tuple of (description, ai_generated, generation_prompt)
        - description: The generated or placeholder description
        - ai_generated: Whether the description was AI-generated
        - generation_prompt: The prompt used (or to be used) for generation
    """
    cleaned_metadata = _clean_metadata_for_prompt(metadata)
    cleaned_entity = _clean_metadata_for_prompt(entity)
    cleaned_categories = _clean_metadata_for_prompt(categories)

    # Build metadata string for the prompt
    metadata_str = (
        f"Useful metadata:\n{json.dumps(cleaned_metadata, indent=2)}\n\n"
        f"Entity information:\n{json.dumps(cleaned_entity, indent=2)}\n\n"
        f"Categories:\n{json.dumps(cleaned_categories, indent=2)}"
    )
    
    # Use the registered prompt function
    generation_prompt = generate_artifact_description_prompt(
        artifact_type=artifact_type,
        artifact_name=name,
        metadata=metadata_str
    )

    # Check if client supports sampling capability
    supports_sampling = client_supports_sampling(ctx)

    # LLM SAMPLING APPROACH:
    # Use when client supports sampling - generates description directly
    if supports_sampling:
        try:
            LOGGER.info("Using LLM sampling to generate description")
            raw_llm_output = await chat_llm_request(generation_prompt, ctx=ctx)
            description = (raw_llm_output.content or "").strip()
            
            if not description:
                description = "No description available."
            
            ai_generated = True
            # Return None for generation_prompt since description was already generated
            return description, ai_generated, None
            
        except Exception as e:
            LOGGER.error(f"LLM sampling failed, falling back to metaprompting: {e}")
            # Fall through to metaprompting approach

    # METAPROMPTING APPROACH (Fallback):
    # Return the prompt for the calling model to generate the description
    LOGGER.info("Using metaprompting approach - returning prompt for client")
    description = "[Description needs to be generated - see generation_prompt field]"
    ai_generated = True

    return description, ai_generated, generation_prompt


def _transform_global_search_response(
    response: dict, artifact_name: str
) -> Optional[Dict[str, Any]]:
    """
    Transform global search response into glossary artifact description structure.
    
    Args:
        response: Response from global search API
        artifact_name: Name of the artifact being searched
        
    Returns:
        Dictionary containing glossary artifact description or None if not found
    """
    rows = response.get("rows", [])
    if not rows:
        return None

    def row_score(row):
        metadata = row.get("metadata", {})
        name = metadata.get("name", "").lower()
        score = row.get("_score", 0)
        name_match = 1 if name == artifact_name.lower() else 0
        return (name_match, score)

    row = sorted(rows, key=row_score, reverse=True)[0]

    metadata = row.get("metadata", {})
    entity = row.get("entity", {})
    categories = row.get("categories", {})
    entity_artifacts = entity.get("artifacts", {})

    artifact_global_id = entity_artifacts.get("global_id")
    artifact_id = entity_artifacts.get("artifact_id")
    version_id = entity_artifacts.get("version_id")
    name = metadata.get("name", "")
    artifact_type = metadata.get("artifact_type", "glossary_term")

    if not artifact_id or not version_id:
        raise ServiceError(f"Missing required artifact identifiers in response: {row}")

    artifact_type_path = ARTIFACT_TYPE_MAPPING.get(artifact_type, "glossary_terms")
    url = f"{tool_helper_service.ui_base_url}/v3/glossary_terms/{artifact_type_path}/{artifact_id}/versions/{version_id}"

    glossary_artifact = GlossaryArtifact(
        id=artifact_global_id, name=name, artifact_type=artifact_type, url=url
    )

    return {
        "glossary_artifact": glossary_artifact,
        "metadata": metadata,
        "entity": entity,
        "categories": categories,
    }


@service_registry.tool(
    name="explain_glossary_artifact",
    description="""Explain detailed information about a glossary artifact by its name.

    This tool retrieves and explains metadata about a glossary artifact, which could be any of:
    - Glossary term
    - Classification
    - Data class
    - Reference data
    - Policy
    - Rule (Glossary artifact)

    The explanation includes the artifact's definition, purpose, and related metadata.""",
)
@auto_context
async def explain_glossary_artifact(
    request: ExplainGlossaryArtifactRequest,
    ctx: Optional[Context] = None,
) -> GlossaryArtifactDescription:
    """
    Explain a glossary artifact by its name.
    
    Args:
        request: Request containing the artifact name
        
    Returns:
        GlossaryArtifactDescription with artifact details and description
        
    Raises:
        ServiceError: If the artifact cannot be found
        ExternalAPIError: If the API call fails
    """
    LOGGER.info(
        f"explain_glossary_artifact called with artifact_name={request.artifact_name}"
    )

    payload = {
        "query": {
            "bool": {
                "must": [
                    {"match": {METADATA_NAME: {"query": request.artifact_name}}}
                ]
            }
        }
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json=payload,
    )

    transformed_data = _transform_global_search_response(response, request.artifact_name)

    if not transformed_data:
        raise ServiceError(
            f"No glossary artifact found with name '{request.artifact_name}'"
        )

    glossary_artifact = transformed_data["glossary_artifact"]
    metadata = transformed_data["metadata"]
    entity = transformed_data["entity"]
    categories = transformed_data["categories"]

    description = metadata.get("description")
    ai_generated = False
    generation_prompt = None

    if not description or not description.strip():
        description, ai_generated, generation_prompt = await _prepare_description(
            name=glossary_artifact.name,
            artifact_type=glossary_artifact.artifact_type,
            metadata=metadata,
            entity=entity,
            categories=categories,
            ctx=ctx,
        )

    glossary_artifact.url = append_context_to_url(glossary_artifact.url)

    return GlossaryArtifactDescription(
        glossary_artifact=glossary_artifact,
        description=description,
        ai_generated=ai_generated,
        generation_prompt=generation_prompt,
    )


@service_registry.tool(
    name="wxo_explain_glossary_artifact",
    description="""Explain detailed information about a glossary artifact by its name.

    This tool retrieves and explains metadata about a glossary artifact, which could be any of:
    - Glossary term
    - Classification
    - Data class
    - Reference data
    - Policy
    - Rule (Glossary artifact)

    The explanation includes the artifact's definition, purpose, and related metadata.
    
    This is the Watsonx Orchestrator compatible version.""",
)
@auto_context
async def wxo_explain_glossary_artifact(
    artifact_name: str,
    ctx: Optional[Context] = None,
) -> GlossaryArtifactDescription:
    """
    Watsonx Orchestrator compatible version of explain_glossary_artifact.
    
    This is a simplified wrapper that doesn't require the full request object.
    
    Args:
        artifact_name: Name of the glossary artifact to explain
        ctx: Optional MCP Context for checking capabilities and LLM sampling
        
    Returns:
        GlossaryArtifactDescription with artifact details and description
    """
    request = ExplainGlossaryArtifactRequest(artifact_name=artifact_name)
    return await explain_glossary_artifact(request, ctx=ctx)