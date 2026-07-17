# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Update asset metadata for fields: asset name, display name, description, privacy, format, tags, business terms, classifications and related items."""

from typing import Annotated, Optional, List, Dict, Any, Literal
from app.core.registry import service_registry
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.services.data_protection_rules.tools.search_glossary import get_rhs_terms_by_query
from app.services.search.constants import RELATED_ITEMS_GUIDE
from app.services.search.models.update_asset_metadata import (
    RelatedAssetRequest,
    UpdateAssetMetadataRequest,
    UpdateAssetMetadataResponse,
)
from app.services.tool_utils import find_asset_id, find_catalog_id, find_project_id
from app.shared.exceptions.base import ExternalAPIError, ServiceError, ValidationError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import is_uuid_bool
from app.shared.utils.tool_helper_service import tool_helper_service


def _artifact_id_from_global_id(global_id: str) -> str:
    """Extract the artifact UUID from an IBM governance global_id."""
    return global_id.split("_", 1)[1] if "_" in global_id else global_id


async def _resolve_container_id(container_id_or_name: str, container_type: str) -> str:
    """
    Resolve container name to ID if needed.
    
    Args:
        container_id_or_name: Container name or UUID
        container_type: 'catalog' or 'project'
    
    Returns:
        Container UUID
    """
    if is_uuid_bool(container_id_or_name):
        return container_id_or_name
    
    # It's a name, resolve to ID
    if container_type == "catalog":
        return await find_catalog_id(container_id_or_name)
    else:  # project
        return await find_project_id(container_id_or_name)


async def _resolve_asset_id(asset_id_or_name: str, container_id: str, container_type: str) -> str:
    """
    Resolve asset name to ID if needed.
    
    Args:
        asset_id_or_name: Asset name or UUID
        container_id: Container UUID (must already be resolved)
        container_type: 'catalog' or 'project'
    
    Returns:
        Asset UUID
    """
    if is_uuid_bool(asset_id_or_name):
        return asset_id_or_name
    
    # It's a name, resolve to ID
    return await find_asset_id(asset_id_or_name, container_id, container_type)


def _add_asset_name_operation(
    operations: List[Dict[str, Any]],
    updated_fields: List[str],
    new_name: str,
    metadata: Dict[str, Any]
) -> None:
    """
    Add asset name update operation to the operations list.
    
    Args:
        operations: List of JSON Patch operations to append to
        updated_fields: List of field names that were updated
        new_name: New name for the asset
        metadata: Current asset metadata to check if field exists
    """
    op = "replace" if "name" in metadata else "add"
    operations.append({
        "op": op,
        "path": "/metadata/name",
        "value": new_name
    })
    updated_fields.append("asset_name")


def _add_display_name_operation(
    operations: List[Dict[str, Any]],
    updated_fields: List[str],
    display_name: str,
    entity: Dict[str, Any]
) -> None:
    """
    Add display name (semantic name) update operation to the operations list.
    
    Args:
        operations: List of JSON Patch operations to append to
        updated_fields: List of field names that were updated
        display_name: New display name for the asset
        entity: Current asset entity to check if field exists
    """
    data_asset = entity.get("data_asset", {})
    op = "replace" if "semantic_name" in data_asset else "add"
    operations.append({
        "op": op,
        "path": "/entity/data_asset/semantic_name",
        "value": {
            "expanded_name": display_name,
            "status": "accepted"
        }
    })
    updated_fields.append("display_name")


def _add_description_operation(
    operations: List[Dict[str, Any]],
    updated_fields: List[str],
    description: str,
    metadata: Dict[str, Any]
) -> None:
    """
    Add description update operation to the operations list.
    
    Args:
        operations: List of JSON Patch operations to append to
        updated_fields: List of field names that were updated
        description: New description for the asset
        metadata: Current asset metadata to check if field exists
    """
    op = "replace" if ("description" in metadata and metadata.get("description") is not None) else "add"
    operations.append({
        "op": op,
        "path": "/metadata/description",
        "value": description
    })
    updated_fields.append("description")


def _add_tags_operation(
    operations: List[Dict[str, Any]],
    updated_fields: List[str],
    new_tags: List[str],
    metadata: Dict[str, Any]
) -> None:
    """
    Add tags update operation to the operations list, merging with existing tags.
    
    Args:
        operations: List of JSON Patch operations to append to
        updated_fields: List of field names that were updated
        new_tags: New tags to add (will be merged with existing)
        metadata: Current asset metadata to get existing tags
    """
    existing_tags = metadata.get("tags", []) or []
    merged_tags = list(set(existing_tags + new_tags))
    op = "replace" if ("tags" in metadata and metadata.get("tags") is not None) else "add"
    operations.append({
        "op": op,
        "path": "/metadata/tags",
        "value": merged_tags
    })
    updated_fields.append("tags")


def _build_patch_operations(
    request: UpdateAssetMetadataRequest,
    metadata: Dict[str, Any],
    entity: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], List[str]]:
    """
    Build JSON Patch operations based on the request and current metadata/entity state.
    
    Args:
        request: The update request
        metadata: The metadata section from current asset
        entity: The entity section from current asset
    
    Returns:
        Tuple of (operations list, updated_fields list)
    """
    operations = []
    updated_fields = []
    
    if request.new_asset_name is not None:
        _add_asset_name_operation(operations, updated_fields, request.new_asset_name, metadata)
    
    if request.display_name is not None:
        _add_display_name_operation(operations, updated_fields, request.display_name, entity)
    
    if request.description is not None:
        _add_description_operation(operations, updated_fields, request.description, metadata)
    
    if request.privacy is not None:
        operations.append({
            "op": "replace",
            "path": "/metadata/rov/mode",
            "value": request.privacy
        })
        updated_fields.append("privacy")
    
    if request.format is not None:
        operations.append({
            "op": "replace",
            "path": "/entity/data_asset/mime_type",
            "value": request.format
        })
        updated_fields.append("format")
    
    if request.tags is not None:
        _add_tags_operation(operations, updated_fields, request.tags, metadata)
    
    return operations, updated_fields


async def _resolve_governance_artifacts(
    artifact_names_or_ids: List[str],
    artifact_type: Literal["glossary_term", "classification"]
) -> List[Dict[str, Any]]:
    """
    Resolve business term or classification names/IDs to their full metadata.
    
    Args:
        artifact_names_or_ids: List of artifact names or global_ids
        artifact_type: Type of artifact ("glossary_term" for business terms, "classification" for classifications)
    
    Returns:
        List of dictionaries with resolved artifact metadata
    
    Raises:
        ServiceError: If any artifact cannot be resolved
    """
    resolved_artifacts = []
    
    for name_or_id in artifact_names_or_ids:
        # Check if it's a global_id by validating the artifact_id part (format: {repository_id}_{artifact_id})
        uuid_part = name_or_id.split("_", 1)[1] if "_" in name_or_id else ""
        if uuid_part and is_uuid_bool(uuid_part):
            # It's a valid global_id, use it directly
            resolved_artifacts.append({
                "global_id": name_or_id,
                "artifact_id": _artifact_id_from_global_id(name_or_id),
                "name": name_or_id  # We don't have the name, use ID
            })
        else:
            # It's a name, search for it
            results = await get_rhs_terms_by_query(artifact_type, name_or_id)
            
            if not results:
                remediation_step = f"Use search_governance_artifacts tool with rhs_type='{artifact_type}' to find valid {artifact_type}s and their correct names"
                raise ServiceError(
                    f"Cannot find {artifact_type} '{name_or_id}'. "
                    f"Use search_governance_artifacts tool to find valid {artifact_type}s.",
                    remediation_steps=remediation_step
                )
            
            # If multiple results, use the first exact match or the first result
            exact_match = next((r for r in results if r["name"].lower() == name_or_id.lower()), None)
            artifact = exact_match if exact_match else results[0]
            
            resolved_artifacts.append({
                "global_id": artifact["global_id"],
                "artifact_id": artifact.get("artifact_id") or _artifact_id_from_global_id(artifact["global_id"]),
                "name": artifact["name"],
                "description": artifact.get("description"),
                "context": artifact.get("context", []),
            })
    
    return resolved_artifacts


async def _build_business_terms_operation(
    business_terms: List[str],
    entity: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build the CAMS patch operation that MERGES business terms with existing ones.
    
    Args:
        business_terms: List of business term names or global_ids to ADD
        entity: The entity section from current asset
    """
    # Resolve business term names to global_ids
    resolved_terms = await _resolve_governance_artifacts(business_terms, "glossary_term")
    
    # Build the value list for new terms
    new_term_list = [
        {
            "term_display_name": term["name"],
            "term_id": term["global_id"]
        }
        for term in resolved_terms
    ]
    
    # Get existing business terms
    asset_terms = entity.get("asset_terms", {})
    existing_terms = asset_terms.get("list", [])
    
    # Merge with existing terms, avoiding duplicates by term_id
    existing_term_ids = {term["term_id"] for term in existing_terms}
    merged_terms = existing_terms.copy()
    
    for new_term in new_term_list:
        if new_term["term_id"] not in existing_term_ids:
            merged_terms.append(new_term)

    if "list" in asset_terms:
        return {
            "op": "replace",
            "path": "/entity/asset_terms/list",
            "value": merged_terms
        }

    return {
        "op": "add",
        "path": "/entity/asset_terms",
        "value": {"list": merged_terms}
    }


def _build_classification_value(classification: Dict[str, Any]) -> Dict[str, str]:
    """
    Build the data_profile classification shape stored on the asset.
    
    Args:
        classification: Dictionary containing classification metadata with global_id, artifact_id, and name
        
    Returns:
        Dict[str, str]: Classification object with id, name, and global_id fields
    """
    global_id = classification["global_id"]
    return {
        "id": classification.get("artifact_id") or _artifact_id_from_global_id(global_id),
        "name": classification["name"],
        "global_id": global_id,
    }


async def _build_classifications_operation(
    classifications: List[str],
    entity: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build the CAMS patch operation that MERGES manual classifications with existing ones.
    
    Args:
        classifications: List of classification names or global_ids to ADD
        entity: The entity section from current asset
    """
    # Resolve classification names to full metadata
    resolved_classifications = await _resolve_governance_artifacts(classifications, "classification")
    new_classification_list = [
        _build_classification_value(classification)
        for classification in resolved_classifications
    ]
    
    # Get existing classifications
    data_profile = entity.get("data_profile", {})
    existing_classifications = data_profile.get("data_classification_manual", [])
    
    # Merge with existing classifications, avoiding duplicates by global_id
    existing_global_ids = {cls["global_id"] for cls in existing_classifications}
    merged_classifications = existing_classifications.copy()
    
    for new_cls in new_classification_list:
        if new_cls["global_id"] not in existing_global_ids:
            merged_classifications.append(new_cls)

    if "data_classification_manual" in data_profile:
        return {
            "op": "replace",
            "path": "/entity/data_profile/data_classification_manual",
            "value": merged_classifications
        }

    if data_profile:
        return {
            "op": "add",
            "path": "/entity/data_profile/data_classification_manual",
            "value": merged_classifications
        }

    return {
        "op": "add",
        "path": "/entity/data_profile",
        "value": {"data_classification_manual": merged_classifications}
    }


def _extract_relationship_key(resource: Dict[str, Any]) -> tuple:
    """
    Extract unique relationship key from an EXISTING relationship resource for deduplication.
    
    This function creates a unique identifier for relationships that already exist on the asset.
    Used to prevent creating duplicate relationships when adding new ones.
    
    Args:
        resource: Existing relationship resource dictionary from get_relationships API response
                 Contains: relationship_name, asset_id, catalog_id/project_id, or artifact_id
        
    Returns:
        tuple: Unique key tuple (relationship_name, target_id, container_or_type)
    """
    rel_name = resource.get("relationship_name", "")
    target_asset = resource.get("asset_id", "")
    target_catalog = resource.get("catalog_id", "")
    target_project = resource.get("project_id", "")
    target_artifact = resource.get("artifact_id", "")
    
    if target_artifact:
        return (rel_name, target_artifact, "artifact")
    if target_catalog:
        return (rel_name, target_asset, target_catalog)
    if target_project:
        return (rel_name, target_asset, target_project)
    return (rel_name, target_asset, "")


async def _fetch_existing_relationships(
    asset_id: str,
    container_id: str,
    container_type: str
) -> set:
    """
    Fetch all existing relationships for an asset and return as a set of unique keys.
    
    This function retrieves the current relationships from the asset and converts them
    into a set of unique keys for efficient duplicate detection when adding new relationships.
    
    Args:
        asset_id: UUID of the source asset
        container_id: UUID of the container (catalog or project) containing the asset
        container_type: Type of container ('catalog' or 'project')
        
    Returns:
        set: Set of unique relationship keys extracted from existing relationships.
             Each key is a tuple: (relationship_name, target_id, container_or_type).
             Returns empty set if fetch fails (to allow operation to proceed).
             
    """
    get_relationships_url = f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/get_relationships"
    get_params = {
        "asset_id": asset_id,
        f"{container_type}_id": container_id,
    }
    
    try:
        existing_response = await tool_helper_service.execute_post_request(
            url=get_relationships_url,
            params=get_params,
            tool_name="update_asset_metadata"
        )
    except Exception as e:
        LOGGER.warning("Failed to fetch existing relationships, proceeding without deduplication: %s", str(e))
        return set()
    
    existing_dict: Dict[str, Any] = existing_response if isinstance(existing_response, dict) else {}
    resources = existing_dict.get("resources", [])
    
    return {_extract_relationship_key(resource) for resource in resources}


async def _build_asset_relationship_target(
    item: RelatedAssetRequest,
    container_type: str
) -> tuple[Dict[str, Any], str, str]:
    """Build target dict for asset-to-asset relationship."""
    if not item.target_container_id_or_name:
        remediation_step = "Use dynamic_query_search tool to find the target asset and its container information, then provide target_container_id_or_name"
        raise ServiceError(
            "target_container_id_or_name is required for asset relationships",
            remediation_steps=remediation_step
        )
    
    target_container_id = await _resolve_container_id(item.target_container_id_or_name, container_type)
    target_asset_id = await _resolve_asset_id(item.target_id_or_name, target_container_id, container_type)
    
    target = {
        f"{container_type}_id": target_container_id,
        "asset_id": target_asset_id,
    }
    
    return target, target_asset_id, target_container_id


async def _build_artifact_relationship_target(
    item: RelatedAssetRequest
) -> tuple[Dict[str, Any], str]:
    """
    Build target dictionary for creating a NEW asset-to-artifact relationship.
    
    This function resolves the artifact name/ID and prepares
    the relationship target structure.
    
    IMPORTANT: artifact_type MUST be specified to avoid ambiguity since artifacts
    can be either 'glossary_term' (business terms) or 'classification'.
    
    Args:
        item: RelatedAssetRequest containing:
              - target_id_or_name: Artifact name or global_id
              - artifact_type: REQUIRED - 'glossary_term' or 'classification'
              - relationship_name: Optional relationship type (default: 'accesses')
              
    Returns:
        tuple: (target_dict, artifact_global_id) where:
               - target_dict: Contains artifact_id and artifact_type for API call
               - artifact_global_id: The resolved global_id of the artifact
               
    Raises:
        ServiceError: If artifact_type is not specified or artifact cannot be resolved
        
    """
    if not item.artifact_type:
        remediation_step = "Specify artifact_type='glossary_term' or artifact_type='classification' in the related_items parameter"
        raise ServiceError(
            "artifact_type must be specified when connecting to governance artifacts. "
            "Artifacts can be either 'glossary_term' or 'classification'.",
            remediation_steps=remediation_step
        )
    
    artifact_type = item.artifact_type
    
    # Check if it's a global_id by validating the artifact_id part (format: {repository_id}_{artifact_id})
    uuid_part = item.target_id_or_name.split("_", 1)[1] if "_" in item.target_id_or_name else ""
    if uuid_part and is_uuid_bool(uuid_part):
        # It's a global_id - use it directly
        artifact_global_id = item.target_id_or_name
    else:
        # It's a name - resolve it to global_id using the specified type
        resolved_artifacts = await _resolve_governance_artifacts([item.target_id_or_name], artifact_type)
        if not resolved_artifacts:
            remediation_step = "Use search_governance_artifacts tool to search for the artifact and get its correct name or global_id"
            raise ServiceError(
                f"Could not resolve artifact name '{item.target_id_or_name}' of type '{artifact_type}' to global_id.",
                remediation_steps=remediation_step
            )
        artifact_global_id = resolved_artifacts[0]["global_id"]
    
    target = {
        "artifact_id": artifact_global_id,
        "artifact_type": artifact_type,
    }
    
    return target, artifact_global_id




async def _build_column_relationship_target(
    item: RelatedAssetRequest,
    container_type: str
) -> tuple[Dict[str, Any], str, str]:
    """
    Build target dict for asset-to-column relationship.
    
    Args:
        item: RelatedAssetRequest containing column and asset information
        container_type: Type of container ('catalog' or 'project')
        
    Returns:
        tuple[Dict[str, Any], str, str]: (target dict, column_asset_id, target_container_id)
        
    Raises:
        ServiceError: If required fields (target_container_id_or_name, target_asset_id_or_name) are missing
    """
    if not item.target_container_id_or_name:
        remediation_step = "Use dynamic_query_search tool to find the target column's asset and container information, then provide target_container_id_or_name"
        raise ServiceError(
            "target_container_id_or_name is required for column relationships",
            remediation_steps=remediation_step
        )
    if not item.target_asset_id_or_name:
        remediation_step = "Use dynamic_query_search tool to find the asset containing the target column, then provide target_asset_id_or_name"
        raise ServiceError(
            "target_asset_id_or_name is required for column relationships",
            remediation_steps=remediation_step
        )
    
    target_container_id = await _resolve_container_id(item.target_container_id_or_name, container_type)
    target_asset_id = await _resolve_asset_id(item.target_asset_id_or_name, target_container_id, container_type)
    column_asset_id = f"{target_asset_id}#COLUMN#{item.target_id_or_name}"
    
    target = {
        f"{container_type}_id": target_container_id,
        "asset_id": column_asset_id,
    }
    
    return target, column_asset_id, target_container_id


def _build_relationship_key(item: RelatedAssetRequest, target: Dict[str, Any], artifact_id: Optional[str] = None) -> tuple:
    """
    Build unique relationship key for deduplication.
    
    Args:
        item: RelatedAssetRequest containing relationship information
        target: Target dictionary with asset/artifact IDs
        artifact_id: Optional artifact global_id for artifact relationships
        
    Returns:
        tuple: Unique key (relationship_name, target_id, container_or_type)
    """
    if item.item_type == "artifact" and artifact_id:
        return (item.relationship_name, artifact_id, "artifact")
    
    target_container = target.get("catalog_id") or target.get("project_id", "")
    return (item.relationship_name, target.get("asset_id", ""), target_container)


async def _build_relationship_from_item(
    item: RelatedAssetRequest,
    source: Dict[str, Any],
    container_type: str
) -> tuple[Dict[str, Any], tuple]:
    """
    Build a single relationship dict and its deduplication key.
    
    Args:
        item: RelatedAssetRequest specifying the relationship to create
        source: Source asset dictionary with container and asset IDs
        container_type: Type of container ('catalog' or 'project')
        
    Returns:
        tuple[Dict[str, Any], tuple]: (relationship dict, deduplication key)
        
    Raises:
        ServiceError: If item_type is invalid or required fields are missing
    """
    if item.item_type == "asset":
        target, _, _ = await _build_asset_relationship_target(item, container_type)
        rel_key = _build_relationship_key(item, target)
    elif item.item_type == "artifact":
        target, artifact_global_id = await _build_artifact_relationship_target(item)
        rel_key = _build_relationship_key(item, target, artifact_global_id)
    elif item.item_type == "column":
        target, _, _ = await _build_column_relationship_target(item, container_type)
        rel_key = _build_relationship_key(item, target)
    else:
        raise ServiceError(f"Invalid item_type: {item.item_type}. Must be 'asset', 'artifact', or 'column'")
    
    relationship = {
        "relationship_name": item.relationship_name,
        "source": source,
        "target": target,
    }
    
    return relationship, rel_key


async def _update_related_items(
    asset_id: str,
    container_id: str,
    container_type: str,
    related_items: List[RelatedAssetRequest]
) -> None:
    """
    Create related item relationships from this asset to target items (assets, artifacts, or columns).
    
    This function MERGES new relationships with existing ones, avoiding duplicates.
    """
    # Fetch existing relationships
    existing_relationships = await _fetch_existing_relationships(asset_id, container_id, container_type)
    
    # Build source (same for all relationships)
    source = {
        f"{container_type}_id": container_id,
        "asset_id": asset_id,
    }
    
    # Build new relationships, skipping duplicates
    relationships = []
    for item in related_items:
        relationship, rel_key = await _build_relationship_from_item(item, source, container_type)
        
        if rel_key not in existing_relationships:
            relationships.append(relationship)
            LOGGER.debug("Adding new relationship: %s", rel_key)
        else:
            LOGGER.debug("Skipping duplicate relationship: %s", rel_key)
    
    # Create relationships if any new ones exist
    if relationships:
        LOGGER.info(
            "Creating %d new related item relationship(s) for asset_id=%s (skipped %d duplicates)",
            len(relationships),
            asset_id,
            len(related_items) - len(relationships)
        )
        
        try:
            await tool_helper_service.execute_post_request(
                url=f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/set_relationships",
                json={"relationships": relationships},
                tool_name="update_asset_metadata",
            )
        except Exception as e:
            raise ExternalAPIError(f"Failed to update related items: {str(e)}")
    else:
        LOGGER.info(
            "All %d relationship(s) already exist for asset_id=%s, skipping",
            len(related_items),
            asset_id
        )


def _validate_update_request(request: UpdateAssetMetadataRequest) -> None:
    """Validate that at least one field is provided for update."""
    if not any([
        request.new_asset_name is not None,
        request.display_name is not None,
        request.description is not None,
        request.privacy is not None,
        request.format is not None,
        request.tags is not None,
        request.business_terms is not None,
        request.classifications is not None,
        request.related_items is not None
    ]):
        remediation_step = "Use get_asset_details tool to view current asset metadata and decide which fields to modify. Provide at least one field to update."
        raise ValidationError(
            "At least one field must be provided for update: new_asset_name, display_name, description, privacy, format, tags, business_terms, classifications, or related_items",
            remediation_steps=remediation_step
        )


async def _fetch_asset_document(
    asset_id: str,
    container_id: str,
    container_type: str
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Fetch current asset state and return metadata and entity sections."""
    params = {
        f"{container_type}_id": container_id,
        "hide_deprecated_response_fields": False
    }
    
    asset_url = f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/{asset_id}"
    LOGGER.info("Fetching current asset state for asset_id=%s", asset_id)
    
    try:
        asset_document = await tool_helper_service.execute_get_request(
            url=asset_url,
            params=params,
            tool_name="update_asset_metadata"
        )
    except Exception as e:
        raise ExternalAPIError(f"Failed to fetch asset details: {str(e)}")
    
    asset_dict: Dict[str, Any] = asset_document  # type: ignore
    return asset_dict.get("metadata", {}), asset_dict.get("entity", {})


async def _add_governance_operations(
    request: UpdateAssetMetadataRequest,
    entity: Dict[str, Any],
    operations: List[Dict[str, Any]],
    updated_fields: List[str]
) -> None:
    """Add business terms and classifications operations."""
    if request.business_terms is not None:
        try:
            operations.append(
                await _build_business_terms_operation(request.business_terms, entity)
            )
            updated_fields.append("business_terms")
        except Exception as e:
            raise ServiceError(f"Failed to prepare business terms update: {str(e)}")

    if request.classifications is not None:
        try:
            operations.append(
                await _build_classifications_operation(request.classifications, entity)
            )
            updated_fields.append("classifications")
        except Exception as e:
            raise ServiceError(f"Failed to prepare classifications update: {str(e)}")


async def _execute_bulk_patch(
    asset_id: str,
    container_id: str,
    container_type: str,
    operations: List[Dict[str, Any]]
) -> None:
    """Execute bulk_patch API call and validate response."""
    payload = {
        "resources": [
            {
                "asset_id": asset_id,
                "operations": operations
            }
        ]
    }
    
    bulk_url = f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/bulk_patch"
    
    LOGGER.info(
        "Calling CAMS bulk_patch for asset_id=%s with %d operation(s)",
        asset_id,
        len(operations)
    )
    
    try:
        bulk_response = await tool_helper_service.execute_post_request(
            url=bulk_url,
            json=payload,
            params={f"{container_type}_id": container_id},
            tool_name="update_asset_metadata"
        )
    except Exception as e:
        raise ExternalAPIError(f"Failed to update asset metadata: {str(e)}")
    
    # Validate the response
    bulk_dict: Dict[str, Any] = bulk_response  # type: ignore
    resources = bulk_dict.get("resources", [])
    if not resources:
        raise ServiceError("No resources returned from bulk_patch API")
    
    resource = resources[0]
    status = resource.get("http_status", resource.get("status"))
    
    # Accept both 200 and 204 as success status codes
    if status and int(status) not in [200, 204]:
        error_msg = resource.get("errors") or resource.get("message") or "Unknown error"
        raise ServiceError(f"Bulk patch failed with HTTP {status}: {error_msg}")


async def _update_asset_metadata(
    request: UpdateAssetMetadataRequest,
) -> UpdateAssetMetadataResponse:
    """
    Internal function to update catalog asset metadata.
    
    This function performs the following steps:
    1. Validates that at least one field is provided for update
    2. Gets the current asset state to determine if fields exist (for add vs replace operations)
    3. Builds JSON Patch operations for each field to update
    4. Calls the CAMS bulk_patch API to apply the updates
    5. Returns a response with the updated asset information
    """
    # Validate request
    _validate_update_request(request)
    
    # Resolve container and asset names to IDs
    LOGGER.info(
        "Resolving container_id_or_name='%s' and asset_id_or_name='%s'",
        request.container_id_or_name,
        request.asset_id_or_name
    )
    
    container_id = await _resolve_container_id(request.container_id_or_name, request.container_type)
    asset_id = await _resolve_asset_id(request.asset_id_or_name, container_id, request.container_type)
    
    LOGGER.info(
        "Starting update asset metadata for asset_id=%s, container_id=%s, container_type=%s",
        asset_id,
        container_id,
        request.container_type
    )
    
    # Fetch current asset state
    metadata, entity = await _fetch_asset_document(asset_id, container_id, request.container_type)
    
    # Build JSON Patch operations
    operations, updated_fields = _build_patch_operations(request, metadata, entity)
    await _add_governance_operations(request, entity, operations, updated_fields)
    
    # Execute bulk_patch if there are operations
    if operations:
        await _execute_bulk_patch(asset_id, container_id, request.container_type, operations)

    # Update related items if provided
    if request.related_items is not None:
        await _update_related_items(
            asset_id=asset_id,
            container_id=container_id,
            container_type=request.container_type,
            related_items=request.related_items,
        )
        updated_fields.append("related_items")
    
    # Return success response
    return UpdateAssetMetadataResponse(
        message=f"Successfully updated {len(updated_fields)} field(s) for asset {asset_id}",
        asset_id=asset_id,
        updated_fields=updated_fields
    )


@service_registry.tool(
    name="update_asset_metadata",
    description="""Update metadata for assets in either catalog or project including asset name, display name, description, privacy, format, tags, business terms, classifications and related items.

**WORKFLOW**
This tool accepts BOTH names and UUIDs for assets, containers, and governance artifacts. You can directly provide:
- Asset name OR UUID
- Container name OR UUID
- Business term/classification names OR global_ids
- Related item names OR UUIDs

The tool will automatically resolve names to IDs internally.

**Example User Request (Catalog):**
"For asset claims in catalog DATA PRODUCT CATALOG, update description to 'SAMPLE TESTING', privacy to Private, and tags to 'DATAPRODUCT'"

**Workflow (Catalog):**
Call: update_asset_metadata(asset_id_or_name="claims", container_id_or_name="DATA PRODUCT CATALOG", container_type="catalog", description="SAMPLE TESTING", privacy=16, tags=["DATAPRODUCT"])

**Example User Request (Project):**
"For asset customer_data in project Analytics Project, update description to 'Analytic project' and add tags 'Analytics'"

**Workflow (Project):**
Call: update_asset_metadata(asset_id_or_name="customer_data", container_id_or_name="Analytics", container_type="project", description="Analytic project", tags=["Analytics"])

**related_items** — List of related items (assets, artifacts, or columns) to ADD/connect to this asset. Each item requires:
- item_type: 'asset', 'artifact', or 'column' (REQUIRED)
- target_id_or_name: Name or ID of the target item (REQUIRED)
  - For assets: asset name or UUID
  - For artifacts: business term/classification name or global_id
  - For columns: column name
- artifact_type: 'glossary_term' or 'classification' (optional, for artifacts only)
- target_asset_id_or_name: Asset name or UUID containing the column (REQUIRED for columns only)
- target_container_id_or_name: Target's container name or UUID (REQUIRED for assets and columns, NOT for artifacts)
  - IMPORTANT: Target container TYPE (catalog/project) is inherited from source asset's container_type
  - Target container ID/NAME MUST be DIFFERENT from source container (never use source container here)
  - Example: Source in "Catalog A" can connect to target in "Catalog B" (both catalogs, different IDs)
  - If container info is missing, use dynamic_query_search to find target and ask user to select
- relationship_name: Relationship type (optional, defaults to 'accesses'). ONLY set this if the user explicitly specifies a relationship type. If the user does not mention a relationship, omit this field entirely and let the default 'accesses' apply.

Examples:
- Asset (no relationship specified): {"item_type": "asset", "target_id_or_name": "customer_data", "target_container_id_or_name": "Target Catalog"}
- Artifact (business term, no relationship specified): {"item_type": "artifact", "target_id_or_name": "Customer ID", "artifact_type": "glossary_term"}
- Artifact (classification, no relationship specified): {"item_type": "artifact", "target_id_or_name": "Sensitive Data", "artifact_type": "classification"}
- Artifact (user said consists_of): {"item_type": "artifact", "target_id_or_name": "Customer ID", "artifact_type": "glossary_term", "relationship_name": "consists_of"}
- Column: {"item_type": "column", "target_id_or_name": "account_id", "target_asset_id_or_name": "account", "target_container_id_or_name": "Target Catalog", "relationship_name": "asset-column1"}

{RELATED_ITEMS_GUIDE}

**IMPORTANT CONSTRAINTS:**
- At least one of new_asset_name, display_name, description, privacy, format, tags, business_terms, classifications, or related_items must be provided
- For privacy field, only values 0 or 16 are valid""",
    tags={"update", "search", "asset_metadata", "edit", "metadata"},
    meta={"version": "1.0", "service": "search"},
    annotations={
        "title": "Update Asset Metadata Including Tags, Terms, Classifications, and Relationships",
        "destructiveHint": True
    }
)
@auto_context
async def update_asset_metadata(
    asset_id_or_name: Annotated[str, "Asset name OR UUID"],
    container_id_or_name: Annotated[str, "Container name OR UUID"],
    container_type: Annotated[Literal["catalog", "project"], "Type of container - 'catalog' or 'project' (default: 'catalog')"] = "catalog",
    new_asset_name: Annotated[Optional[str], "New name for the asset - updates /metadata/name (optional)"] = None,
    display_name: Annotated[Optional[str], "Display name for the asset - updates /entity/data_asset/semantic_name (optional)"] = None,
    description: Annotated[Optional[str], "Description of the asset - updates /metadata/description (optional)"] = None,
    privacy: Annotated[Optional[Literal[0, 16]], "Privacy/ROV mode: 0 (Public) or 16 (Private) - updates /metadata/rov/mode (optional)"] = None,
    format: Annotated[Optional[str], "MIME type/format of the asset e.g. 'application/x-ibm-rel-table' - updates /entity/data_asset/mime_type (optional)"] = None,
    tags: Annotated[Optional[List[str]], "List of tags to ADD - merges with existing tags, updates /metadata/tags (optional)"] = None,
    business_terms: Annotated[Optional[List[str]], "List of business term names or global_ids to ADD - merges with existing (optional)"] = None,
    classifications: Annotated[Optional[List[str]], "List of classification names or global_ids to ADD - merges with existing (optional)"] = None,
    related_items: Annotated[Optional[List[RelatedAssetRequest]], "List of related items (assets, artifacts, or columns) to ADD/connect (optional)"] = None
) -> UpdateAssetMetadataResponse:
    """
    Update asset metadata in catalog or project including governance artifacts and related items.
    
    Args:
        asset_id_or_name: Asset name OR UUID
        container_id_or_name: Container name OR UUID
        container_type: Type of container - 'catalog' or 'project' (default: 'catalog')
        new_asset_name: New name for the asset (optional)
        display_name: Display name for the asset (optional)
        description: New description for the asset (optional)
        privacy: Privacy/ROV mode - 0 (Public), 16 (Private) (optional)
        format: New format/MIME type for the asset (optional)
        tags: List of tags to ADD (merges with existing tags) (optional)
        business_terms: List of business term names or global_ids to ADD (merges with existing) (optional)
        classifications: List of classification names or global_ids to ADD (merges with existing) (optional)
        related_items: List of related items to ADD/connect (optional)
    
    Returns:
        UpdateAssetMetadataResponse with update status and updated fields
    """
    
    request = UpdateAssetMetadataRequest(
        asset_id_or_name=asset_id_or_name,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
        new_asset_name=new_asset_name,
        display_name=display_name,
        description=description,
        privacy=privacy,
        format=format,
        tags=tags,
        business_terms=business_terms,
        classifications=classifications,
        related_items=related_items
    )
    
    return await _update_asset_metadata(request)
