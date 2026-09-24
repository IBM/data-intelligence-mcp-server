# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import asyncio
from typing import Any, List

from aiocache import cached

from app.services.constants import CATALOGS_BASE_ENDPOINT, PROJECTS_BASE_ENDPOINT
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service


@cached(ttl=1800)
async def _fetch_single_container_name(
    container_id: str,
    container_type: str,
    endpoint: str,
) -> tuple[str, str | None]:
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{endpoint}/{container_id}",
            tool_name="container_name_enrichment",
        )
        name = response.get("entity", {}).get("name")
        if name:
            LOGGER.debug("Fetched %s name: %s -> %s", container_type, container_id, name)
        return (container_id, name)
    except Exception as e:
        LOGGER.warning("Failed to fetch %s name for %s: %s", container_type, container_id, str(e))
        return (container_id, None)


async def fetch_container_names(results: List[Any]) -> dict[str, str]:
    """Fetch project and catalog names for all unique container IDs in results.

    Args:
        results: List of search result objects with ``project_id`` / ``catalog_id`` attributes.

    Returns:
        Dictionary mapping container IDs to their display names,
        e.g. ``{"project-123": "My Project"}``. IDs whose fetch failed are omitted.
    """
    project_ids = {r.project_id for r in results if r.project_id}
    catalog_ids = {r.catalog_id for r in results if r.catalog_id}

    if not project_ids and not catalog_ids:
        return {}

    LOGGER.info("Fetching names for %d projects and %d catalogs", len(project_ids), len(catalog_ids))

    tasks = []
    tasks.extend([_fetch_single_container_name(pid, "project", PROJECTS_BASE_ENDPOINT) for pid in project_ids])
    tasks.extend([_fetch_single_container_name(cid, "catalog", CATALOGS_BASE_ENDPOINT) for cid in catalog_ids])

    container_names: dict[str, str] = {}
    for result in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(result, Exception):
            LOGGER.warning("Exception during container name fetch: %s", str(result))
            continue
        container_id, name = result
        if name:
            container_names[container_id] = name

    LOGGER.info("Successfully fetched %d container names", len(container_names))
    return container_names


def enrich_with_container_names(results: List[Any], container_names: dict[str, str]) -> None:
    """Patch project_name / catalog_name on each result in-place.

    Args:
        results: List of search result objects to mutate.
        container_names: Mapping from container ID to display name,
            as returned by :func:`fetch_container_names`.
    """
    for result in results:
        if result.project_id and result.project_id in container_names:
            result.project_name = container_names[result.project_id]
            LOGGER.debug("Enriched project_name for %s: %s", result.project_id, result.project_name)
        if result.catalog_id and result.catalog_id in container_names:
            result.catalog_name = container_names[result.catalog_id]
            LOGGER.debug("Enriched catalog_name for %s: %s", result.catalog_id, result.catalog_name)
