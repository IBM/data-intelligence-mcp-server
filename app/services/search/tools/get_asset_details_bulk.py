# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Bulk asset details retrieval tool."""

import asyncio
from typing import Annotated, Any, Literal

from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT
from app.services.search.models.get_asset_details import (
    AssetUsage,
    GetAssetDetailsResponse,
)
from app.services.search.models.get_asset_details_bulk import (
    AssetDetails,
    GetAssetDetailsForAssetsRequest,
    GetAssetDetailsForAssetsResponse,
)
from app.services.search.tools.get_asset_details import (
    _get_user_info,
    retrieve_rov,
    retrieve_source_asset,
)
from app.services.tool_utils import (
    find_asset_id,
    retrieve_container_id,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.ui_message.ui_message_context import ui_message_context
from app.shared.utils.helpers import is_uuid_bool
from app.shared.utils.tool_helper_service import tool_helper_service

_HTTP_OK = 200


def _format_bulk_asset_details_for_table(
    response: GetAssetDetailsForAssetsResponse,
) -> list:
    """Format bulk asset details response into a compact table."""
    formatted_rows = []
    for asset in response.assets:
        if asset.details:
            row = {
                "Asset": asset.asset_id_or_name,
                "Type": asset.details.asset_type,
                "Owner": asset.details.owner_name or asset.details.owner_id or "N/A",
                "Created": asset.details.created_at,
                "Size": f"{asset.details.size} bytes",
                "Rating": f"{asset.details.rating:.1f} ({asset.details.total_ratings})",
            }
        else:
            row = {
                "Asset": asset.asset_id_or_name,
                "Type": "ERROR",
                "Owner": "N/A",
                "Created": "N/A",
                "Size": "N/A",
                "Rating": "N/A",
                "Error": asset.error or "Unknown error",
            }
        formatted_rows.append(row)
    return formatted_rows


async def _bulk_fetch_user_info(
    iam_ids: list[str],
) -> dict[str, tuple[str, str]]:
    """Fetch user information for multiple IAM IDs concurrently.

    Filters out empty/None IAM IDs, deduplicates, then fetches all
    remaining IDs in parallel and caches the results.

    Args:
        iam_ids: List of IAM IDs to resolve.

    Returns:
        Mapping of IAM ID to (name, email).
    """
    unique_ids = set(filter(None, (i.strip() if i else "" for i in iam_ids)))
    if not unique_ids:
        return {}

    LOGGER.info("Fetching user info for %d unique IAM IDs", len(unique_ids))

    async def _fetch_one(iam_id: str) -> tuple[str, tuple[str, str]]:
        try:
            name, email = await _get_user_info(iam_id)
        except Exception as e:  # noqa: BLE001
            LOGGER.warning(
                "Failed to fetch user info for IAM ID %s: %s", iam_id, e
            )
            return (iam_id, ("", ""))
        else:
            return (iam_id, (name, email))

    results = await asyncio.gather(*[_fetch_one(i) for i in unique_ids])
    return dict(results)


def _build_asset_usage_from_cache(
    usage_info: dict[str, Any],
    user_info_cache: dict[str, tuple[str, str]],
) -> AssetUsage:
    """Build an AssetUsage object using a pre-fetched user-info cache."""
    last_updater_id = usage_info.get("last_updater_id", "")
    last_accessor_id = usage_info.get("last_accessor_id", "")
    last_updater_name, last_updater_email = user_info_cache.get(
        last_updater_id, ("", "")
    )
    last_accessor_name, last_accessor_email = user_info_cache.get(
        last_accessor_id, ("", "")
    )
    return AssetUsage(
        last_updated_at=usage_info["last_updated_at"],
        last_updater_id=last_updater_id,
        last_updater_name=last_updater_name,
        last_updater_email=last_updater_email,
        last_update_time=usage_info["last_update_time"],
        last_accessed_at=usage_info["last_accessed_at"],
        last_access_time=usage_info["last_access_time"],
        last_accessor_id=last_accessor_id,
        last_accessor_name=last_accessor_name,
        last_accessor_email=last_accessor_email,
        access_count=usage_info["access_count"],
    )


def _build_asset_metadata_from_cache(
    metadata: dict[str, Any],
    user_info_cache: dict[str, tuple[str, str]],
) -> GetAssetDetailsResponse:
    """Build a GetAssetDetailsResponse using a pre-fetched user-info cache."""
    owner_id = metadata.get("owner_id")
    creator_id = metadata.get("creator_id", "")
    owner_name, owner_email = user_info_cache.get(owner_id or "", ("", ""))
    creator_name, creator_email = user_info_cache.get(creator_id, ("", ""))
    return GetAssetDetailsResponse(
        usage=_build_asset_usage_from_cache(metadata.get("usage", {}), user_info_cache),
        rov=retrieve_rov(metadata.get("rov", {})),
        sub_container_id=metadata.get("sub_container_id"),
        is_linked_with_sub_container=metadata["is_linked_with_sub_container"],
        name=metadata["name"],
        description=metadata.get("description"),
        tags=metadata.get("tags"),
        asset_type=metadata["asset_type"],
        origin_country=metadata.get("origin_country"),
        resource_key=metadata["resource_key"],
        identity_key=metadata.get("identity_key"),
        delete_processing_state=metadata.get("delete_processing_state"),
        delete_reason=metadata.get("delete_reason"),
        rating=metadata["rating"],
        total_ratings=metadata["total_ratings"],
        catalog_id=metadata.get("catalog_id"),
        project_id=metadata.get("project_id"),
        space_id=metadata.get("space_id"),
        created=metadata["created"],
        created_at=metadata["created_at"],
        owner_id=owner_id,
        owner_name=owner_name,
        owner_email=owner_email,
        size=metadata["size"],
        version=metadata["version"],
        asset_state=metadata.get("asset_state", "available"),
        asset_attributes=metadata.get("asset_attributes"),
        asset_id=metadata["asset_id"],
        source_asset=retrieve_source_asset(metadata.get("source_asset", {})),
        asset_category=metadata.get("asset_category", "USER"),
        revision_id=metadata.get("revision_id"),
        number_of_shards=metadata.get("number_of_shards"),
        creator_id=creator_id,
        creator_name=creator_name,
        creator_email=creator_email,
        is_branched=metadata.get("is_branched"),
        set_id=metadata.get("set_id"),
        is_managed_asset=metadata.get("is_managed_asset", False),
        entity={},
    )


def _parse_resource(
    resource: dict[str, Any] | None,
    asset_name: str,
    user_info_cache: dict[str, tuple[str, str]],
) -> tuple[GetAssetDetailsResponse | None, str | None]:
    """Parse a single /v2/assets/bulk resource entry into (details, error).

    Returns (details, None) on success, (None, error_message) on failure.
    """
    if resource is None:
        return None, "Asset not found in bulk response"

    http_status = resource.get("http_status", _HTTP_OK)
    status = resource.get("status", "")

    if http_status != _HTTP_OK or status != "success":
        raw_errors = resource.get("errors", [])
        error_msg = (
            "; ".join(str(err) for err in raw_errors)
            if raw_errors
            else f"HTTP {http_status}, status: {status}"
        )
        return None, error_msg

    asset_data = resource.get("asset", {})
    metadata = asset_data.get("metadata", {})
    if not metadata:
        return None, "No metadata found in response"

    try:
        details = _build_asset_metadata_from_cache(metadata, user_info_cache)
        details.entity = asset_data.get("entity", {})
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "Failed to parse metadata for asset %s: %s", asset_name, exc
        )
        return None, f"Failed to parse metadata: {exc!s}"
    else:
        return details, None


def _collect_iam_ids(resources: list[dict[str, Any]]) -> list[str]:
    """Collect all IAM IDs from successful bulk API resources."""
    iam_ids: list[str] = []
    for resource in resources:
        if (
            resource.get("http_status") == _HTTP_OK
            and resource.get("status") == "success"
        ):
            meta = resource.get("asset", {}).get("metadata", {})
            if meta:
                usage = meta.get("usage", {})
                iam_ids += [
                    meta.get("owner_id", ""),
                    meta.get("creator_id", ""),
                    usage.get("last_updater_id", ""),
                    usage.get("last_accessor_id", ""),
                ]
    return iam_ids


async def _fetch_bulk_asset_details(
    asset_ids: list[str],
    name_to_id_map: dict[str, str],
    container_id: str,
    container_type: Literal["catalog", "project"],
) -> list[AssetDetails]:
    """Fetch details for multiple assets via the /v2/assets/bulk endpoint.

    The endpoint supports up to 20 comma-separated asset IDs per call.
    User info for all assets is fetched concurrently using a shared cache.
    """
    LOGGER.info(
        "Batch fetching details for %d assets from %s:%s",
        len(asset_ids),
        container_type,
        container_id,
    )

    query_params: dict[str, str] = {
        "asset_ids": ",".join(asset_ids),
        "hide_deprecated_response_fields": "false",
    }
    if container_type == "catalog":
        query_params["catalog_id"] = container_id
    else:
        query_params["project_id"] = container_id

    id_to_name_map = {v: k for k, v in name_to_id_map.items()}

    try:
        response_data = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url!s}{CAMS_ASSETS_BASE_ENDPOINT}/bulk",
            params=query_params,
            tool_name="get_asset_details_for_assets",
        )
        response: dict[str, Any] = (
            response_data if isinstance(response_data, dict) else {}
        )
        resources: list[dict[str, Any]] = response.get("resources", [])
        resource_map: dict[str, dict[str, Any]] = {
            r["asset_id"]: r for r in resources if r.get("asset_id")
        }

        user_info_cache = await _bulk_fetch_user_info(_collect_iam_ids(resources))

        results: list[AssetDetails] = []
        for asset_id in asset_ids:
            original_name = id_to_name_map.get(asset_id, asset_id)
            details, error = _parse_resource(
                resource_map.get(asset_id),
                original_name,
                user_info_cache,
            )
            results.append(
                AssetDetails(
                    asset_id_or_name=original_name,
                    details=details,
                    error=error,
                )
            )
    except Exception as e:  # noqa: BLE001
        LOGGER.error("Bulk API call failed for %d assets: %s", len(asset_ids), e)
        return [
            AssetDetails(
                asset_id_or_name=id_to_name_map.get(asset_id, asset_id),
                details=None,
                error=f"Bulk API call failed: {e!s}",
            )
            for asset_id in asset_ids
        ]
    else:
        return results


async def _resolve_all_asset_ids(
    asset_ids_or_names: list[str],
    container_id: str,
    container_type: Literal["catalog", "project"],
) -> dict[str, str | None]:
    """Resolve a list of asset names/IDs to UUIDs concurrently.

    Returns a mapping of original name/ID → resolved UUID (or None on failure).
    """

    async def _resolve_one(asset_id_or_name: str) -> tuple[str, str | None]:
        try:
            asset_id = asset_id_or_name.strip()
            if not is_uuid_bool(asset_id):
                asset_id = await find_asset_id(
                    asset_id, container_id, container_type
                )
        except Exception as e:  # noqa: BLE001
            LOGGER.warning(
                "Failed to resolve asset %s: %s", asset_id_or_name, e
            )
            return (asset_id_or_name, None)
        else:
            return (asset_id_or_name, asset_id)

    results = await asyncio.gather(
        *[_resolve_one(name) for name in asset_ids_or_names]
    )
    return dict(results)


async def _get_asset_details_for_assets(
    request: GetAssetDetailsForAssetsRequest,
) -> GetAssetDetailsForAssetsResponse:
    """Retrieve asset details for multiple assets using the bulk API.

    Automatically chunks requests into batches of 20 assets (API limit).
    """
    LOGGER.info(
        "Getting bulk asset details for %d assets in %s %s",
        len(request.asset_ids_or_names),
        request.container_type,
        request.container_id_or_name,
    )

    container_id = await retrieve_container_id(
        request.container_id_or_name,
        request.container_type,
    )

    name_to_id_map = await _resolve_all_asset_ids(
        request.asset_ids_or_names, container_id, request.container_type
    )

    resolved = [(n, aid) for n, aid in name_to_id_map.items() if aid is not None]
    unresolved = [(n, aid) for n, aid in name_to_id_map.items() if aid is None]

    assets: list[AssetDetails] = [
        AssetDetails(
            asset_id_or_name=name,
            details=None,
            error="Asset not found or could not be resolved",
        )
        for name, _ in unresolved
    ]

    if resolved:
        resolved_ids = [aid for _, aid in resolved]
        resolved_name_map = {aid: name for name, aid in resolved}
        batch_size = 20
        total_batches = (len(resolved_ids) + batch_size - 1) // batch_size
        for i in range(0, len(resolved_ids), batch_size):
            batch_ids = resolved_ids[i : i + batch_size]
            LOGGER.info(
                "Processing batch %d/%d (%d assets)",
                i // batch_size + 1,
                total_batches,
                len(batch_ids),
            )
            batch_results = await _fetch_bulk_asset_details(
                asset_ids=batch_ids,
                name_to_id_map=resolved_name_map,
                container_id=container_id,
                container_type=request.container_type,
            )
            assets.extend(batch_results)

    requested_count = len(request.asset_ids_or_names)
    total_count = sum(1 for a in assets if a.details is not None)
    failed_count = requested_count - total_count

    response = GetAssetDetailsForAssetsResponse(
        assets=assets,
        total_count=total_count,
        requested_count=requested_count,
        failed_count=failed_count,
    )

    if total_count > 0:
        ui_message_context.add_table_ui_message(
            tool_name="get_asset_details_for_assets",
            formatted_data=_format_bulk_asset_details_for_table(response),
            title=f"Asset Details for {total_count} Assets",
        )
        if failed_count > 0:
            LOGGER.warning(
                "%d/%d assets failed to retrieve details",
                failed_count,
                requested_count,
            )
    else:
        LOGGER.warning(
            "No asset details retrieved for any of the %d requested assets",
            requested_count,
        )

    return response


@service_registry.tool(
    name="get_asset_details_for_assets",
    annotations={
        "readOnlyHint": True,
        "title": "Get Comprehensive Metadata and Details for Multiple Assets",
    },
    description=(
        "Use this tool when you need comprehensive metadata and details for multiple assets at once.\n\n"
        "Retrieves: usage, ROV (collaborators/members), asset attributes, creation/update timestamps, "
        "owner information, ratings, tags, and entity information (columns, etc.).\n"
        "Uses the /v2/assets/bulk endpoint — up to 20 assets per API call, automatically batched for "
        "larger lists. More efficient than calling get_asset_details repeatedly.\n"
        "You can pass either IDs or names for both assets and container.\n\n"
        "REQUIRED: ALL THREE parameters are mandatory. Ask for any missing information:\n"
        "- If asset names are missing: Ask \"Which assets would you like to get details for?\"\n"
        "- If container is missing: Ask \"Which project or catalog contains these assets?\"\n"
        "- If container type is missing: Ask \"Are these assets in a project or catalog?\""
    ),
    tags={"search", "asset_metadata", "metadata_management_and_governance"},
    meta={"version": "1.0", "service": "search"},
)
@auto_context
async def get_asset_details_for_assets(
    asset_ids_or_names: Annotated[
        list[str],
        Field(description="List of asset UUIDs or names to retrieve details for."),
    ],
    container_id_or_name: Annotated[
        str,
        Field(
            description="UUID or name of the project or catalog that contains the assets."
        ),
    ],
    container_type: Annotated[
        Literal["catalog", "project"],
        Field(
            description=(
                "The container type in which the assets reside - 'catalog' or 'project'."
            )
        ),
    ],
) -> GetAssetDetailsForAssetsResponse:
    """Build the request model and delegate to the main implementation."""
    request = GetAssetDetailsForAssetsRequest(
        asset_ids_or_names=asset_ids_or_names,
        container_id_or_name=container_id_or_name,
        container_type=container_type,
    )
    return await _get_asset_details_for_assets(request)
