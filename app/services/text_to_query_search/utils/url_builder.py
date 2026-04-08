# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.services.text_to_query_search.constants import GOVERNANCE_GLOSSARY_PATHS
from app.shared.utils.tool_helper_service import tool_helper_service


def transform_glossary_term_id(asset_id: str) -> str:
    """Transform glossary term ID from format: prefix_part1_part2 to part1/part2"""
    id_parts = asset_id.split("_")
    if len(id_parts) < 3:
        raise ValueError(f"Unexpected glossary term ID format: {asset_id}")
    return f"{id_parts[1]}/{id_parts[2]}"


def transform_category_id(asset_id: str) -> str:
    """Transform category ID from format: prefix_category_id to category_id"""
    id_parts = asset_id.split("_", 1)
    if len(id_parts) < 2:
        raise ValueError(f"Unexpected category ID format: {asset_id}")
    return id_parts[1]


def get_container_param(project_id: str | None, catalog_id: str | None) -> str:
    """Return the query-string container parameter for the given project/catalog IDs."""
    if project_id:
        return f"project_id={project_id}"
    if catalog_id:
        return f"catalog_id={catalog_id}"
    raise ValueError("Either project_id or catalog_id must be provided")


def _build_data_asset_column_url(
    base: str, asset_id: str, project_id: str | None, catalog_id: str | None, artifact_name: str | None
) -> str:
    """Build URL for data_asset_column artifacts."""
    if not catalog_id and not project_id:
        return ""
    column_asset_id = asset_id.replace(":" + artifact_name, "") if artifact_name else asset_id
    return (
        f"{base}/data/catalogs/{catalog_id}/data-assets/{column_asset_id}"
        if catalog_id
        else f"{base}/projects/{project_id}/data-assets/{column_asset_id}"
    )


def _build_data_asset_url(base: str, asset_id: str, project_id: str | None, catalog_id: str | None) -> str:
    """Build URL for data_asset artifacts."""
    if not catalog_id and not project_id:
        return ""
    return (
        f"{base}/data/catalogs/{catalog_id}/data-assets/{asset_id}"
        if catalog_id
        else f"{base}/projects/{project_id}/data-assets/{asset_id}"
    )


def build_artifact_url(
    artifact_type: str,
    asset_id: str,
    project_id: str | None,
    catalog_id: str | None,
    artifact_name: str | None,
) -> str:
    """
    Build the UI URL for a given artifact based on its type and container.
    
    Args:
        artifact_type: Type of the artifact
        asset_id: ID of the artifact
        project_id: Project ID if artifact is in a project
        catalog_id: Catalog ID if artifact is in a catalog
        artifact_name: Name of the artifact (used for data_asset_column)
        
    Returns:
        The complete UI URL for the artifact, or empty string if URL cannot be built
    """
    base = str(tool_helper_service.ui_base_url)

    if artifact_type in GOVERNANCE_GLOSSARY_PATHS:
        return f"{base}/governance/{GOVERNANCE_GLOSSARY_PATHS[artifact_type]}/{transform_glossary_term_id(asset_id)}"

    match artifact_type:
        case "category":
            return f"{base}/governance/categories/{transform_category_id(asset_id)}"
        case "data_protection_rule":
            return f"{base}/governance/rules/dataProtection/view/{asset_id}"
        case "data_rule_definition":
            return f"{base}/data-quality/data-quality-definition/display/{asset_id}?{get_container_param(project_id, catalog_id)}"
        case "data_rule":
            return f"{base}/data-quality/data-quality-rule/display/{asset_id}?{get_container_param(project_id, catalog_id)}"
        case "job":
            return f"{base}/jobs/{asset_id}?{get_container_param(project_id, catalog_id)}"
        case "metadata_enrichment_area":
            return f"{base}/gov/metadata-enrichments/display/{asset_id}?{get_container_param(project_id, catalog_id)}"
        case "metadata_import":
            return f"{base}/gov/metadata-imports/{asset_id}?{get_container_param(project_id, catalog_id)}"
        case "connection":
            if project_id:
                return f"{base}/connections/{asset_id}?project_id={project_id}"
            if catalog_id:
                return f"{base}/data/catalogs/{catalog_id}/asset/{asset_id}"
            return ""
        case "data_asset_column":
            return _build_data_asset_column_url(base, asset_id, project_id, catalog_id, artifact_name)
        case "data_asset":
            return _build_data_asset_url(base, asset_id, project_id, catalog_id)
        case _:
            # Unknown artifact type
            return ""

# Made with Bob
