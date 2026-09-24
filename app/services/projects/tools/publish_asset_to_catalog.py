# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Any, Annotated, cast

from app.core.registry import service_registry
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.services.projects.models.publish_asset_to_catalog import (
    PublishAssetToCatalogRequest,
    PublishAssetToCatalogResponse,
)
from app.services.tool_utils import find_asset_id_exact_match, retrieve_container_id
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url, is_uuid_bool
from app.shared.utils.tool_helper_service import tool_helper_service
from pydantic import Field

def _extract_error_message(e: dict[str, Any]) -> str:
    """Extract a human-readable message from a bulk_copy error entry."""
    return e.get("message") or (e.get("error", {}).get("errors") or [{}])[0].get("message", "")


def _check_bulk_copy_errors(resp: dict[str, Any]) -> None:
    """Raise ServiceError if the bulk_copy response contains inline errors."""
    all_errors = resp.get("errors", []) + resp.get("copy_errors", [])
    if not all_errors:
        return
    messages = [m for e in all_errors if (m := _extract_error_message(e))]
    raise ServiceError(
        f"Failed to publish asset to catalog: {'; '.join(messages)}",
        tool="publish_asset_to_catalog",
    )


async def _do_publish(source_asset_id: str, source_project_id: str, target_catalog_id: str) -> str:
    """Publish a project asset to a catalog via bulk_copy, auto-copying any required connections.

    Returns the target (catalog-scoped) asset ID of the published asset.
    """
    response = cast(
        dict[str, Any],
        await tool_helper_service.execute_post_request(
            url=f"{str(tool_helper_service.base_url)}{CAMS_ASSETS_BASE_ENDPOINT}/bulk_copy",
            params={
                "project_id": source_project_id,
                "auto_copy_connections_in_remote_attachments": True,
            },
            json={
                "catalog_id": target_catalog_id,
                "copy_configurations": [{"asset_id": source_asset_id}],
            },
            tool_name="publish_asset_to_catalog",
        ),
    )
    responses = response.get("responses", [])
    if responses:
        resp = responses[0]
        _check_bulk_copy_errors(resp)
        target_asset_id = (resp.get("copied_assets") or [{}])[0].get("target_asset_id", "")
        if target_asset_id:
            return target_asset_id
    raise ServiceError(
        "Publish asset to catalog succeeded but no published asset id was returned.",
        tool="publish_asset_to_catalog",
    )


async def _publish_asset_to_catalog(
    request: PublishAssetToCatalogRequest,
) -> PublishAssetToCatalogResponse:
    if not request.asset or not request.asset.strip():
        raise ServiceError(
            "Asset identifier cannot be empty. Please provide a valid asset id or name.",
            remediation_steps="Call the search_asset tool twice: first with search_prompt set to '*' and container_type set to 'catalog', then with search_prompt set to '*' and container_type set to 'project'. Retrieve the available assets from both calls, then provide a valid asset name or id from the combined results.",
            tool="publish_asset_to_catalog",
        )

    if not request.project or not request.project.strip():
        raise ServiceError(
            "Project identifier cannot be empty. Please provide a valid project id or name.",
            remediation_steps="Call the list_containers tool with container_type set to 'project' to retrieve the list of available projects. Then provide a project id or name from the list.",
            tool="publish_asset_to_catalog",
        )

    if not request.catalog or not request.catalog.strip():
        raise ServiceError(
            "Catalog identifier cannot be empty. Please provide a valid catalog id or name.",
            remediation_steps="Call the list_containers tool with container_type set to 'catalog' to retrieve the list of available catalogs. Then provide a catalog id or name from the list.",
            tool="publish_asset_to_catalog",
        )

    LOGGER.info(
        "Starting publish asset to catalog with asset: '%s', project: '%s', catalog: '%s'",
        request.asset,
        request.project,
        request.catalog,
    )

    source_project_id = await retrieve_container_id(request.project.strip(), "project")
    target_catalog_id = await retrieve_container_id(request.catalog.strip(), "catalog")

    source_asset_id = request.asset.strip()
    if not is_uuid_bool(source_asset_id):
        source_asset_id = await find_asset_id_exact_match(source_asset_id, source_project_id, "project", max_retries=0)

    published_asset_id = await _do_publish(source_asset_id, source_project_id, target_catalog_id)
    published_asset_name = request.asset.strip()

    asset_url = append_context_to_url(
        f"{tool_helper_service.ui_base_url}/data/catalogs/{target_catalog_id}/asset/{published_asset_id}"
    )

    return PublishAssetToCatalogResponse(
        message=(
            f"Successfully published asset '{published_asset_name}' from project "
            f"'{source_project_id}' to catalog '{target_catalog_id}'."
        ),
        asset_id=published_asset_id,
        asset_name=published_asset_name,
        catalog_id=target_catalog_id,
        source_project_id=source_project_id,
        source_asset_id=source_asset_id,
        url=asset_url,
    )


@service_registry.tool(
    name="publish_asset_to_catalog",
    annotations={
        "title": "Publish Asset from Project to Catalog",
        "destructiveHint": True,
    },
    description="""Use this tool to Publish an asset from a project to a catalog.
                    This tool resolves the source project, target catalog, and source asset, then invokes the
                    platform publish API so the asset is published with the platform's existing semantics,
                    including metadata and revision handling.
                    Return: The asset added to the catalog and the API location URL to access it.",

                    IMPORTANT CONSTRAINTS:
                    - asset is required and must identify an asset in the source project
                    - project is required and must identify the source project
                    - catalog is required and must identify the target catalog""",
    tags={"search", "asset_publish","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "projects"},
)
@auto_context
async def publish_asset_to_catalog(
    asset: Annotated[str, Field(description="The name of the asset to be published")],
    project: Annotated[str, Field(description="The source project")],
    catalog: Annotated[str, Field(description="The target catalog")]
) -> PublishAssetToCatalogResponse:
    request = PublishAssetToCatalogRequest(
        asset=asset,
        project=project,
        catalog=catalog,
    )
    return await _publish_asset_to_catalog(request)

# Made with Bob
