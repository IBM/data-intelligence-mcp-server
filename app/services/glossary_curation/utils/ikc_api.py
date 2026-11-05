# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""IKC HTTP API helpers for the glossary curator.

Thin wrappers around IKC REST endpoints used during session management.
These are infrastructure-layer functions with no dependency on session state
or curation logic.
"""

import zipfile  # noqa: I001 # Baseline
import io
from typing import Optional

from app.core.auth import get_user_identifier
from app.core.settings import settings
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.helpers import construct_task_url


async def export_csv(category_id: str) -> tuple[str, str]:
    """Export terms from IKC using the ZIP-based export API."""
    url = f"{settings.di_service_url}/v3/governance_artifact_types/export"
    params = {
        "artifact_id_mode": "always",
        "artifact_types": "glossary_term,category",
        "category_ids": category_id,
        "include_custom_attribute_definitions": "false",
        "include_development_log": "false",
    }
    resp = await tool_helper_service.execute_get_request(
        url=url, headers={}, params=params, tool_name="glossary_curator"
    )

    # Response is a ZIP archive containing the CSV
    if isinstance(resp, dict) and "content" in resp:
        raw = resp["content"]
        zip_bytes = raw if isinstance(raw, (bytes, bytearray)) else raw.encode("utf-8")
    elif isinstance(resp, (bytes, bytearray)):
        zip_bytes = resp
    else:
        raise ValueError(f"Unexpected response type from export API: {type(resp)}")

    if not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
        raise ValueError(
            f"Export API response is not a valid ZIP archive "
            f"(got {len(zip_bytes)} bytes, content-type may be wrong)"
        )

    # Extract the glossary_term and category CSV from the ZIP
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()

        glossary_csv_name = next(
            (n for n in names if n.startswith("glossary_term/") and n.endswith(".csv")),
            None,
        )
        if not glossary_csv_name:
            raise ValueError(f"No glossary_term CSV found in ZIP. Contents: {names}")

        category_csv_name = next(
            (n for n in names if n.startswith("category/") and n.endswith(".csv")), None
        )
        if not category_csv_name:
            raise ValueError(f"No category CSV found in ZIP. Contents: {names}")

        glossary_csv = zf.read(glossary_csv_name).decode("utf-8")
        category_csv = zf.read(category_csv_name).decode("utf-8")

        return glossary_csv, category_csv


async def get_draft_term_count(category_id: str) -> int:
    """Return the number of draft glossary terms in a single category."""
    try:
        url = f"{settings.di_service_url}/v3/governance_artifact_types/glossary_term"
        resp = await tool_helper_service.execute_get_request(
            url=url,
            headers={},
            params={"parent_category_id": category_id, "limit": 1},
            tool_name="glossary_curator",
        )
        return int(resp.get("count", 0))
    except Exception as exc:
        LOGGER.warning(
            f"[curator] draft term check failed for category {category_id}: {exc}"
        )
        raise


async def get_category_name(category_id: str) -> str:
    try:
        resp = await tool_helper_service.execute_get_request(
            url=f"{settings.di_service_url}/v3/categories/{category_id}",
            headers={},
            params={},
            tool_name="glossary_curator",
        )
        return resp.get("metadata", {}).get("name", category_id)
    except Exception:
        return category_id


async def write_workflow_comment(workflow_id: str, comment: str) -> Optional[str]:  # noqa: UP045 # Baseline
    """Post an attribution comment to the IKC workflow activity log.

    Returns None on success, or the error string on failure (never raises).
    """
    try:
        user_id = await get_user_identifier()
        payload: dict = {"comment": comment}
        if user_id:
            payload["user_id"] = user_id
        url = f"{settings.di_service_url}/v3/workflows/{workflow_id}/logs"
        await tool_helper_service.execute_post_request(
            url=url,
            headers={},
            json=payload,
            tool_name="glossary_curator",
        )
        return None
    except Exception as e:
        LOGGER.warning(
            f"[curator] Failed to post workflow comment for workflow_id={workflow_id}: {e}"
        )
        return str(e)


async def get_task_url(artifact_id: str) -> Optional[str]:  # noqa: UP045 # Baseline
    try:
        url = f"{settings.di_service_url}/v3/workflow_user_tasks"
        resp = await tool_helper_service.execute_get_request(
            url=url,
            headers={},
            params={"artifact_id": artifact_id},
            tool_name="glossary_curator",
        )
        resources = resp.get("resources") or []
        if not resources:
            return None
        task_id = str(resources[0]["metadata"]["task_id"])
        return construct_task_url(task_id)

    except Exception:
        LOGGER.info(f"Failed to fetch task_id from artifact_id={artifact_id}")
        return None


async def fetch_published_classifications() -> set[str]:
    """Fetch all published classification names from IKC.

    Paginates through the full result set and returns a set of classification
    names (case-preserved) for validation against LLM-curated values.

    Returns:
        Set of classification name strings.
    """
    url = f"{settings.di_service_url}/v3/governance_artifact_types/classification"
    limit = 200
    offset = 0
    names: set[str] = set()

    while True:
        resp = await tool_helper_service.execute_get_request(
            url=url,
            headers={},
            params={"workflow_status": "published", "limit": limit, "offset": offset},
            tool_name="glossary_curator",
        )
        resources = resp.get("resources") or []
        for resource in resources:
            name = (resource.get("name") or "").strip()
            if name:
                names.add(name)

        next_page = resp.get("next")
        if not next_page or not resources:
            break
        next_offset = next_page.get("offset")
        if next_offset is None or next_offset <= offset:
            break
        offset = next_offset

    LOGGER.info(f"[curator] fetched {len(names)} published classification(s) from IKC")
    return names
