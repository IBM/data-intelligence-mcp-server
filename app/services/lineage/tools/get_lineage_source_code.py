# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import re
from typing import Annotated, Any

from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import JSON_CONTENT_TYPE, LINEAGE_BASE_ENDPOINT
from app.services.lineage.constants import (
    SERVICE_UNAVAILABLE_FLAG,
    SERVICE_UNAVAILABLE_MESSAGE,
)
from app.services.lineage.models.get_lineage_source_code import (
    GetLineageSourceCodeRequest,
    GetLineageSourceCodeResponse,
    SourceCodeSnippet,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import are_lineage_ids
from app.shared.utils.tool_helper_service import (
    create_default_headers,
    tool_helper_service,
)

TEXT_CONTENT_TYPE = "text/plain"
TRANSFORMATION_DESC_ATTRIBUTE = "TRANSFORMATION_DESC"

# 404 = nothing stored for this ID; 406 = asset type not supported
_NOT_FOUND = re.compile(r"status: (404|406)\b")
# The lineage service failed (500) or sits behind a gateway that did (502/503/504)
_SERVICE_FAILURE = re.compile(r"status: (500|502|503|504)\b")
# The connection was closed without an answer. This carries no status code, so the HTTP helper
# reports it as "Unknown Error". A pooled connection can go stale, so one more try usually works.
_DROPPED_CONNECTION = re.compile(r"call failed: unknown error")
_DROPPED_CONNECTION_FLAG = "dropped_connection"
_DROPPED_CONNECTION_RETRIES = 1
# Any line break style found in stored source code
_LINE_BREAK = re.compile(r"\r\n|\r")


async def _fetch_lineage_endpoint_once(path: str, accept_type: str) -> dict[str, Any] | None:
    """One GET {LINEAGE_BASE_ENDPOINT}{path}, with errors turned into results.

    Returns the parsed response, None if the resource does not exist (404/406),
    {SERVICE_UNAVAILABLE_FLAG: True} on a 500/502/503/504, or {_DROPPED_CONNECTION_FLAG: True}
    when the connection was closed without an answer. Other errors are re-raised.
    """
    try:
        return await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.base_url) + LINEAGE_BASE_ENDPOINT + path,
            headers=create_default_headers(accept_type=accept_type),
        )
    except (ExternalAPIError, ServiceError) as e:
        message = str(e.message).lower()
        if _NOT_FOUND.search(message):
            return None
        if _DROPPED_CONNECTION.search(message):
            return {_DROPPED_CONNECTION_FLAG: True}
        if _SERVICE_FAILURE.search(message):
            return {SERVICE_UNAVAILABLE_FLAG: True}
        raise


def _is_dropped(response: dict[str, Any] | None) -> bool:
    return bool(response and response.get(_DROPPED_CONNECTION_FLAG))


async def _fetch_lineage_endpoint(path: str, accept_type: str = JSON_CONTENT_TYPE) -> dict[str, Any] | None:
    """GET {LINEAGE_BASE_ENDPOINT}{path}.

    Returns the parsed response, None if the resource does not exist (404/406),
    or {SERVICE_UNAVAILABLE_FLAG: True} on a 500/502/503/504 or a dropped connection that
    is still dropped after one retry. Other errors are re-raised.
    """
    response = await _fetch_lineage_endpoint_once(path, accept_type)
    retries = 0
    while _is_dropped(response) and retries < _DROPPED_CONNECTION_RETRIES:
        retries += 1
        LOGGER.warning("Connection dropped for %s, retrying", path)
        response = await _fetch_lineage_endpoint_once(path, accept_type)
    if _is_dropped(response):
        return {SERVICE_UNAVAILABLE_FLAG: True}
    return response


def _extract_text(response: dict[str, Any]) -> str | None:
    """Source code endpoints answer with text/plain, which the HTTP client wraps as {"content": bytes}.

    Line breaks are normalised to "\\n": the stored text mixes "\\r\\n", "\\r\\r\\n" and bare "\\n".
    """
    content = response.get("content") or response.get("source_code") or response.get("text")
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    if isinstance(content, str):
        return _LINE_BREAK.sub("\n", content)
    return content


async def _call_source_code_snippet(snippet_id: str) -> dict[str, Any] | None:
    """Call /gov_lineage/v2/source_code_snippets/{id} (text/plain only, JSON gets a 406)."""
    return await _fetch_lineage_endpoint(f"/source_code_snippets/{snippet_id}", accept_type=TEXT_CONTENT_TYPE)


async def _call_source_code(source_code_id: str) -> dict[str, Any] | None:
    """Call /gov_lineage/v2/source_codes/{id} (text/plain only, JSON gets a 406)."""
    return await _fetch_lineage_endpoint(f"/source_codes/{source_code_id}", accept_type=TEXT_CONTENT_TYPE)


async def _call_lineage_asset(lineage_id: str) -> dict[str, Any] | None:
    """Call /gov_lineage/v2/lineage_assets/{id}."""
    return await _fetch_lineage_endpoint(f"/lineage_assets/{lineage_id}")


def _attributes(asset: dict[str, Any]) -> dict[str, str | None]:
    """All attributes of the asset by name."""
    return {
        attribute["name"]: attribute.get("value")
        for attribute in asset.get("attributes") or []
        if attribute.get("name")
    }


def _unavailable(lineage_id: str) -> GetLineageSourceCodeResponse:
    return GetLineageSourceCodeResponse(
        success=False,
        error=SERVICE_UNAVAILABLE_MESSAGE,
        lineage_id=lineage_id,
    )


async def _read_text(call: Any, resource_id: str) -> tuple[str | None, bool]:
    """Run one content endpoint call. Returns (text, service_failed)."""
    response = await call(resource_id)
    if response is None:
        return None, False
    if response.get(SERVICE_UNAVAILABLE_FLAG):
        return None, True
    return _extract_text(response), False


async def _fetch_snippet(reference: dict[str, Any]) -> tuple[SourceCodeSnippet | None, bool]:
    """Fetch the code of one snippet reference of an asset.

    Tries the targeted snippet first. If that is missing, empty or fails, falls back to the
    full source code of the parent object. Returns (snippet, service_failed): snippet is None
    when no text could be read, and service_failed tells whether that was due to a lineage
    service failure rather than the code simply not being stored.
    """
    snippet_id = reference.get("id")
    if not snippet_id:
        return None, False
    source_code_id = (reference.get("source_code") or {}).get("id")

    text, failed = await _read_text(_call_source_code_snippet, snippet_id)
    is_full_source = False
    if not text and source_code_id:
        text, full_source_failed = await _read_text(_call_source_code, source_code_id)
        failed = failed or full_source_failed
        is_full_source = bool(text)

    if not text:
        return None, failed
    return (
        SourceCodeSnippet(
            id=snippet_id,
            source_code=text,
            source_code_id=source_code_id,
            is_full_source=is_full_source,
            start_position=reference.get("start_position"),
            end_position=reference.get("end_position"),
        ),
        False,
    )


async def _asset_response(lineage_id: str, asset: dict[str, Any]) -> GetLineageSourceCodeResponse:
    """Build the response for a lineage asset: its attributes and the code snippets attached to it."""
    snippets: list[SourceCodeSnippet] = []
    failed_snippet_ids: list[str] = []
    for reference in asset.get("source_code_snippets") or []:
        snippet, service_failed = await _fetch_snippet(reference)
        if snippet is not None:
            snippets.append(snippet)
        elif service_failed:
            failed_snippet_ids.append(reference["id"])

    attributes = _attributes(asset)
    all_failed = bool(failed_snippet_ids) and not snippets
    return GetLineageSourceCodeResponse(
        success=not all_failed,
        error=SERVICE_UNAVAILABLE_MESSAGE if all_failed else None,
        lineage_id=lineage_id,
        asset_name=asset.get("name"),
        asset_type=asset.get("type"),
        snippets=snippets,
        failed_snippet_ids=failed_snippet_ids,
        attributes=attributes,
        transformation_desc=attributes.get(TRANSFORMATION_DESC_ATTRIBUTE),
    )


async def _direct_id_response(lineage_id: str) -> GetLineageSourceCodeResponse:
    """Build the response when the ID is not a lineage asset but may be a snippet or source code ID."""
    snippet, service_failed = await _fetch_snippet(
        {"id": lineage_id, "source_code": {"id": lineage_id}}
    )
    if snippet is not None:
        return GetLineageSourceCodeResponse(lineage_id=lineage_id, source_code=snippet.source_code)
    if service_failed:
        return _unavailable(lineage_id)
    return GetLineageSourceCodeResponse(lineage_id=lineage_id)


async def _get_lineage_source_code(
    request: GetLineageSourceCodeRequest,
) -> GetLineageSourceCodeResponse:
    are_lineage_ids([request.lineage_id])

    LOGGER.info("get_lineage_source_code called with lineage_id=%s", request.lineage_id)

    asset = await _call_lineage_asset(request.lineage_id)
    if asset is None:
        return await _direct_id_response(request.lineage_id)
    if asset.get(SERVICE_UNAVAILABLE_FLAG):
        return _unavailable(request.lineage_id)
    return await _asset_response(request.lineage_id, asset)


@service_registry.tool(
    name="get_lineage_source_code",
    annotations={
        "readOnlyHint": True,
        "title": "Get Source Code or Transformation Logic for a Lineage Asset",
    },
    tags={"lineage"},
    description="""Use this tool to retrieve the SQL/transformation logic of a lineage asset: the source
    code of a stored procedure, view or function, and the transformation expression of a column flow.

    This tool answers questions like:
    - "What does this stored procedure actually do?"
    - "How is this column derived / what is the transformation logic?"
    - "Show me the SQL behind this view"

    Given a lineage ID it works in this order:
    1. Reads the asset (/gov_lineage/v2/lineage_assets/{id}) and returns all its attributes, including
       TRANSFORMATION_DESC (also returned separately as `transformation_desc`).
    2. For every source code snippet attached to the asset, reads the targeted snippet
       (/gov_lineage/v2/source_code_snippets/{id}) first.
    3. If the snippet is missing, empty or cannot be read, falls back to the full source
       (/gov_lineage/v2/source_codes/{id}) and marks it with is_full_source=true.
    An asset can have several snippets (for example a function and the view that calls it), and
    transformation logic and source code are on different assets: column flows carry the
    TRANSFORMATION_DESC attribute, while procedures, functions and the body assets of views and
    procedures (named <name>_BODY, e.g. returnstableintview_BODY) carry the code. A View asset
    itself can come back empty: search for its _BODY asset instead. Assets with neither (plain
    tables and columns) return empty results. The code is returned as a whole; it is not narrowed
    to the lines that produce a single column.

    **CRITICAL REQUIREMENT**: This tool needs a lineage ID (64-character hexadecimal string or UUID).
    Obtain the lineage ID from search_lineage_assets or get_lineage_id first if you don't have it.

    Typical workflow:
        User: "What is the logic that calculates the <column_name> column?"
        1. Call search_lineage_assets(name_query="<column_name>") to find the asset
        2. Extract the lineage ID from the result
        3. Call get_lineage_source_code(lineage_id="<id>") to get the transformation logic
        4. Explain the returned code to the user in plain language

    Returns:
        - lineage_id, asset_name, asset_type: the queried asset
        - attributes: all attributes of the asset by name
        - transformation_desc: the TRANSFORMATION_DESC attribute, when the asset has one
        - snippets: source code snippets attached to the asset (check snippets[].source_code).
          start_position/end_position show where the snippet sits in the full source when known.
        - failed_snippet_ids: snippets that could not be read because the lineage service failed.
          success is false only when every snippet failed.
        - source_code: full source code, only when the given ID is a snippet or source code ID
    """,
)
@auto_context
async def get_lineage_source_code(
    lineage_id: Annotated[
        str,
        Field(
            description="Lineage ID (64-character hexadecimal string or UUID) of the asset "
                        "(stored procedure, view, function, etc.) whose source code to retrieve. "
                        "Must be obtained from search_lineage_assets or get_lineage_id."
        ),
    ],
) -> GetLineageSourceCodeResponse:
    """Retrieve SQL/transformation source code for a lineage asset."""
    request = GetLineageSourceCodeRequest(lineage_id=lineage_id)
    return await _get_lineage_source_code(request)
