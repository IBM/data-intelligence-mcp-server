# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Business-logic helpers for the glossary_curator MCP tool."""

import asyncio  # noqa: I001 # Baseline
from datetime import datetime, timezone, UTC  # noqa: F401 # Baseline
from typing import Any, Optional

from app.services.tool_utils import find_category_id, find_project_name
from app.shared.utils.helpers import (
    confirm_uuid,
    construct_glossary_category_url,
    construct_project_url,
)
from app.services.glossary_curation.models.session import (
    ClassificationValidation,
    CompleteSessionOutcome,
    CurationConfig,
    CurationMode,
    DefinitionScope,
    RunType,
    StartSessionParams,
)
from app.services.glossary_curation.models.staleness import (
    StalenessCheckResult,
    StalenessDiff,
)
from app.services.glossary_curation.utils import prompt_builder
from app.services.glossary_curation.utils.abstract_session_store import (
    AbstractSessionStore,
    get_session_store,
)
from app.services.glossary_curation.utils.curation_utils import (
    _ARTIFACT_KEY_COL,
    CLASSIFICATION_MODE_CURATION_COLS,
    _chunk,
    _new_preview_session_id,
    _new_session_id,
    _now_iso,
    _parse_csv,
    _progress,
    _row_key,
    _to_csv,
    get_mode_curation_fieldnames,
    get_mode_import_fieldnames,
    get_mode_review_fieldnames,
    get_mode_payload_fieldnames,
    create_payload_terms,
    resolve_ids_in_rows,
)
from app.services.glossary_curation.utils.ikc_api import (
    export_csv,
    fetch_published_classifications,
    get_category_name,
    get_draft_term_count,
    get_task_url,
    write_workflow_comment,
)
from app.services.glossary_curation.utils.import_utils import import_csv_file
from app.services.glossary_curation.utils.merge_utils import process_mode_response
from app.services.glossary_curation.utils.quality_checks import quality_issues
from app.shared.logging import LOGGER


_STALENESS_DIFF_THRESHOLD = 10


def _build_artifact_value_map(
    rows: list[dict], columns: list[str]
) -> dict[str, dict[str, set[str]]]:
    """Build a map of artifact_id -> {column -> set of values from all continuation rows}.

    Handles IKC continuation rows (blank Artifact ID) by accumulating values for
    each column across the main row and its continuation rows.
    """
    artifact_map: dict[str, dict[str, set[str]]] = {}
    current_artifact_id: str | None = None

    for row in rows:
        artifact_id = (row.get(_ARTIFACT_KEY_COL) or "").strip()

        if artifact_id:
            # New main row
            current_artifact_id = artifact_id
            if current_artifact_id not in artifact_map:
                artifact_map[current_artifact_id] = {col: set() for col in columns}

        if current_artifact_id is None:
            # Continuation row before any main row - skip
            continue

        for col in columns:
            value = row.get(col, "")
            if value:
                artifact_map[current_artifact_id][col].add(value)

    return artifact_map


def _get_term_name_from_before(rows: list[dict], artifact_id: str) -> str:
    """Get the term name from before.csv for a given artifact_id."""
    for row in rows:
        if (row.get(_ARTIFACT_KEY_COL) or "").strip() == artifact_id:
            return (row.get("Name") or "").strip()
    return artifact_id  # fallback


def _format_diff_line(diff: StalenessDiff) -> str:
    """Return a single bullet line describing one diff entry."""
    if diff.is_deleted:
        return f"- {diff.term_name} — term no longer exists in the live glossary"
    if diff.field in ("Classifications", "Tags", "Part Of Terms"):
        return f"- {diff.term_name} — {diff.field} changed (IDs not shown)"
    return f"- {diff.term_name} — {diff.field}: '{diff.before_value}' → '{diff.after_value}'"


def _format_staleness_detailed(diffs: list[StalenessDiff], created_at: str) -> str:
    """Detailed per-term staleness message (≤ threshold diffs)."""
    header = (
        f"The following terms have changed in the live glossary since this curation "
        f"started at {created_at}. This curation session is no longer valid — please "
        f"start a new session.\n\nChanged terms:"
    )
    lines = [header] + [_format_diff_line(d) for d in diffs]
    return "\n".join(lines)


def _format_staleness_aggregate(diffs: list[StalenessDiff], created_at: str) -> str:
    """Aggregate field-count staleness message (> threshold diffs)."""
    field_counts: dict[str, int] = {}
    for diff in diffs:
        key = "term deleted" if diff.is_deleted else diff.field
        field_counts[key] = field_counts.get(key, 0) + 1

    field_parts = [
        f"{count} term(s) deleted"
        if field == "term deleted"
        else f"{field} ({count} change{'s' if count > 1 else ''})"
        for field, count in sorted(field_counts.items())
    ]
    return (
        f"The following fields have since changed in the live glossary since this curation "
        f"started at {created_at}. This curation session is no longer valid — please "
        f"start a new session.\n\n"
        f"Field-level change counts: {', '.join(field_parts)}."
    )


def _format_staleness_message(diffs: list[StalenessDiff], created_at: str) -> str:
    """Format the human-readable staleness message based on diff count."""
    if not diffs:
        return ""
    if len(diffs) <= _STALENESS_DIFF_THRESHOLD:
        return _format_staleness_detailed(diffs, created_at)
    return _format_staleness_aggregate(diffs, created_at)


def _deleted_term_diff(artifact_id: str, term_name: str) -> StalenessDiff:
    """Return a StalenessDiff representing a term that no longer exists in IKC."""
    return StalenessDiff(
        artifact_id=artifact_id,
        term_name=term_name,
        field="",
        before_value="",
        after_value="",
        is_deleted=True,
    )


def _column_diffs_for_artifact(
    artifact_id: str,
    term_name: str,
    before_cols: dict[str, set[str]],
    verification_cols: dict[str, set[str]],
    columns_to_check: list[str],
) -> list[StalenessDiff]:
    """Return a diff for each column whose values changed between before and verification."""
    diffs = []
    for col in columns_to_check:
        before_values = before_cols.get(col, set())
        verification_values = verification_cols.get(col, set())
        if before_values != verification_values:
            diffs.append(
                StalenessDiff(
                    artifact_id=artifact_id,
                    term_name=term_name,
                    field=col,
                    before_value=", ".join(sorted(before_values))
                    if before_values
                    else "",
                    after_value=", ".join(sorted(verification_values))
                    if verification_values
                    else "",
                    is_deleted=False,
                )
            )
    return diffs


def _collect_staleness_diffs(
    curated_artifact_ids: set[str],
    before_rows: list[dict],
    before_map: dict[str, dict[str, set[str]]],
    verification_map: dict[str, dict[str, set[str]]],
    columns_to_check: list[str],
) -> list[StalenessDiff]:
    """Compare each curated artifact against the fresh export and return diffs."""
    diffs: list[StalenessDiff] = []
    for artifact_id in curated_artifact_ids:
        term_name = _get_term_name_from_before(before_rows, artifact_id)
        if artifact_id not in verification_map:
            diffs.append(_deleted_term_diff(artifact_id, term_name))
            continue
        diffs.extend(
            _column_diffs_for_artifact(
                artifact_id,
                term_name,
                before_map.get(artifact_id, {}),
                verification_map.get(artifact_id, {}),
                columns_to_check,
            )
        )
    return diffs


async def check_session_staleness(
    session_id: str,
    manifest: dict,
    store: AbstractSessionStore,
) -> StalenessCheckResult:
    """Check if curated terms have been modified in IKC since session start.

    Compares the original before.csv (stored at session start) against a fresh
    export from IKC (verification.csv), for only the terms that were sent to
    sub-agents for curation.

    Returns a StalenessCheckResult with is_stale, diffs, check_error, and message.
    """
    category_id = manifest.get("category_id")
    mode = manifest.get("mode")
    created_at = manifest.get("created_at", "")

    if not category_id or not mode:
        return StalenessCheckResult(
            is_stale=False,
            diffs=[],
            check_error="Missing category_id or mode in manifest",
            message="Internal error: session manifest incomplete",
        )

    # 1. Export fresh verification.csv from IKC
    try:
        verification_csv, _ = await export_csv(category_id)
    except Exception as e:
        LOGGER.error(f"[{session_id}] Staleness check export failed: {e}")
        return StalenessCheckResult(
            is_stale=False,
            diffs=[],
            check_error=f"Failed to export fresh glossary data from IKC: {e}",
            message="Unable to verify glossary currency — the export from IKC failed. Please retry the operation.",
        )

    # 2. Read before.csv from store
    before_csv = await store.read_pre_csv(session_id)
    if not before_csv:
        return StalenessCheckResult(
            is_stale=False,
            diffs=[],
            check_error="before.csv not found in session store",
            message="Internal error: original glossary snapshot not found.",
        )

    # 3. Parse both CSVs (handles continuation rows).
    # verification_rows must go through resolve_ids_in_rows so that relationship
    # columns (e.g. Part Of Terms) are in the same name-path form as before.csv,
    # which was already resolved at session-start time.  Without this, UUID values
    # from the fresh IKC export are compared against resolved names from before.csv,
    # producing false-positive stale diffs even when nothing has changed.
    _, before_rows = _parse_csv(before_csv)
    _, verification_rows_raw = _parse_csv(verification_csv)
    verification_rows, _ = resolve_ids_in_rows(verification_rows_raw)

    # 4. Get curated artifact IDs from spawn_prompts
    curated_artifact_ids: set[str] = set()
    for prompt in manifest.get("spawn_prompts", []):
        for row in prompt.get("pre_curated_rows", []):
            aid = (row.get(_ARTIFACT_KEY_COL) or "").strip()
            if aid:
                curated_artifact_ids.add(aid)

    if not curated_artifact_ids:
        return StalenessCheckResult(is_stale=False, diffs=[])

    # 5. Determine columns to check: PAYLOAD_COLS[mode] minus "Artifact ID"
    payload_cols = get_mode_payload_fieldnames(mode)
    columns_to_check = [c for c in payload_cols if c != _ARTIFACT_KEY_COL]

    # 6. Build artifact -> {col -> set(values)} maps for both CSVs
    before_map = _build_artifact_value_map(before_rows, columns_to_check)
    verification_map = _build_artifact_value_map(verification_rows, columns_to_check)

    # 7. Compare curated artifact IDs
    diffs = _collect_staleness_diffs(
        curated_artifact_ids,
        before_rows,
        before_map,
        verification_map,
        columns_to_check,
    )

    if not diffs:
        return StalenessCheckResult(is_stale=False, diffs=[])

    # 8. Format message
    message = _format_staleness_message(diffs, created_at)
    return StalenessCheckResult(is_stale=True, diffs=diffs, message=message)


_chunk_submit_locks: dict[tuple[str, int], asyncio.Lock] = {}
_chunk_submit_locks_guard = asyncio.Lock()


async def _get_chunk_lock(session_id: str, chunk_index: int) -> asyncio.Lock:
    """Return (and lazily create) the asyncio.Lock for a specific chunk slot."""
    key = (session_id, chunk_index)
    async with _chunk_submit_locks_guard:
        if key not in _chunk_submit_locks:
            _chunk_submit_locks[key] = asyncio.Lock()
        return _chunk_submit_locks[key]


async def check_draft_terms(category_ids: list[str]) -> list[dict] | None:
    """Return non-zero draft-term counts per category, or None on API failure.

    Batches calls to get_draft_term_count in groups of 3 to avoid rate limits.
    """
    chunk_size = 3

    counts: list[int] = []
    for i in range(0, len(category_ids), chunk_size):
        batch = category_ids[i : i + chunk_size]
        results = await asyncio.gather(
            *[get_draft_term_count(cat_id) for cat_id in batch],
            return_exceptions=True,
        )
        for cat_id, result in zip(batch, results):  # noqa: B905 # Baseline
            if isinstance(result, BaseException):
                LOGGER.error(
                    f"[curator] draft term check failed for category {cat_id}: {result}"
                )
                return None
            counts.append(result)
    return [
        {"category_id": cat_id, "draft_count": count}
        for cat_id, count in zip(category_ids, counts)  # noqa: B905 # Baseline
        if count > 0
    ]


async def _check_draft_terms_from_rows(rows: list[dict]) -> dict | None:
    """Return an error dict if rows contain categories with draft terms, else None."""
    LOGGER.info(f"Checking draft terms for {len(rows)} rows")

    category_ids = list(
        {
            r[key]
            for r in rows
            if (
                key := (
                    "Category"
                    if r.get("Artifact Type") == "glossary_term"
                    else "Artifact ID"
                )
            )
            and r.get(key)
        }
    )

    blocking = await check_draft_terms(category_ids)
    if blocking is None:
        return {
            "status": "error",
            "error_type": "draft_check_failed",
            "message": "Curation blocked: could not verify draft term status for one or more categories.",
            "instruction": "Check server logs for details, then retry start_session.",
        }
    if blocking:
        return {
            "status": "error",
            "error_type": "draft_terms_present",
            "message": "Curation blocked: one or more categories and subcategories have unpublished draft terms.",
            "blocking_categories": blocking,
            "instruction": "Publish or discard the draft terms listed above, then retry start_session.",
            "output_format": {"blocking_categories": "table"},
        }
    return None


async def _prepare_session_terms(
    category_id: str, mode: CurationMode, config: CurationConfig
) -> dict:
    """Export, filter, and apply scope to produce the term rows ready for chunking.

    Returns a result dict with keys: category_name, full_fieldnames, all_rows,
    payload_term_rows, mode_fieldnames, scope_skipped_count.
    Returns an error dict (containing 'status') if the operation should be aborted.
    """
    raw_csv, categories_csv = await export_csv(category_id)
    category_name = await get_category_name(category_id)

    _, category_rows = _parse_csv(categories_csv)
    if draft_error := await _check_draft_terms_from_rows(category_rows):
        return draft_error

    full_fieldnames, all_rows = _parse_csv(raw_csv)
    all_rows, unresolved_uuids = resolve_ids_in_rows(all_rows)
    unfiltered_rows = all_rows  # preserve full export for before.csv audit trail

    if config.artifact_ids:
        artifact_id_set = set(config.artifact_ids)
        all_rows = [
            r
            for r in all_rows
            if (r.get(_ARTIFACT_KEY_COL) or "").strip() in artifact_id_set
        ]
        LOGGER.info(
            f"artifact_ids filter applied: {len(all_rows)} row(s) matched "
            f"from {len(artifact_id_set)} requested IDs"
        )

    payload_term_rows, mode_fieldnames = create_payload_terms(all_rows, mode.value)

    scope_skipped_count = 0
    if (
        mode == CurationMode.definition
        and config.definition_scope == DefinitionScope.blanks_only
    ):
        before = len(payload_term_rows)
        payload_term_rows = [
            r for r in payload_term_rows if not (r.get("Description") or "").strip()
        ]
        scope_skipped_count = before - len(payload_term_rows)
        if scope_skipped_count:
            LOGGER.info(
                f"definition_scope='blanks_only': {scope_skipped_count} term(s) with existing "
                f"descriptions excluded; {len(payload_term_rows)} blank term(s) queued for generation"
            )

    elif mode == CurationMode.classification:
        before = len(payload_term_rows)
        payload_term_rows = [
            r for r in payload_term_rows if not (r.get("Classifications") or "").strip()
        ]
        scope_skipped_count = before - len(payload_term_rows)
        if scope_skipped_count:
            LOGGER.info(
                f"classification mode: {scope_skipped_count} term(s) with existing "
                f"classifications excluded; {len(payload_term_rows)} blank term(s) queued for classification"
            )

    if not payload_term_rows:
        return {
            "status": "error",
            "error_type": "no_eligible_terms",
            "category_id": category_id,
            "category_name": category_name,
            "message": (
                "No eligible terms found to curate. "
                "The category may be empty, all terms were excluded by definition_scope='blanks_only', "
                "or all terms already have classifications."
            ),
        }

    return {
        "category_name": category_name,
        "full_fieldnames": full_fieldnames,
        "all_rows": unfiltered_rows,
        "payload_term_rows": payload_term_rows,
        "mode_fieldnames": mode_fieldnames,
        "scope_skipped_count": scope_skipped_count,
        "unresolved_part_of_term_uuids": unresolved_uuids,
    }


def _scope_skipped_note(mode: CurationMode, count: int) -> str:
    if mode == CurationMode.classification:
        return f"{count} term(s) already had classifications and were excluded."
    return (
        f"{count} term(s) already had descriptions and were excluded "
        f"because definition_scope='blanks_only'."
    )


async def _start_session(  # noqa: PLR0913 # Baseline
    category_id: str,
    mode: CurationMode,
    chunk_size: int,
    target_language: Optional[str],  # noqa: UP045 # Baseline
    store: AbstractSessionStore,
    definition_prompt: Optional[str] = None,  # noqa: UP045 # Baseline
    classification_prompt: Optional[str] = None,  # noqa: UP045 # Baseline
    translation_prompt: Optional[str] = None,  # noqa: UP045 # Baseline
    definition_scope: DefinitionScope = DefinitionScope.all,
    project_id: str = "",
    project_name: str = "",
    artifact_ids: Optional[list[str]] = None,  # noqa: UP045 # Baseline
) -> dict:
    config = CurationConfig(
        chunk_size=chunk_size,
        target_language=target_language,
        definition_scope=definition_scope,
        definition_prompt=definition_prompt,
        classification_prompt=classification_prompt,
        translation_prompt=translation_prompt,
        artifact_ids=artifact_ids,
    )

    prepared = await _prepare_session_terms(category_id, mode, config)
    if "status" in prepared:
        return prepared

    category_name = prepared["category_name"]
    full_fieldnames = prepared["full_fieldnames"]
    all_rows = prepared["all_rows"]
    payload_term_rows = prepared["payload_term_rows"]
    mode_fieldnames = prepared["mode_fieldnames"]
    scope_skipped_count = prepared["scope_skipped_count"]
    unresolved_part_of_term_uuids: set[str] = prepared["unresolved_part_of_term_uuids"]

    session_id = _new_session_id(mode.value)
    # Use all_rows (pre-scope-filter) so before.csv retains all IKC columns (e.g. Artifact Type).
    pre_csv_content = _to_csv(full_fieldnames, all_rows)
    pre_csv_ref = await store.write_pre_csv(session_id, pre_csv_content)
    LOGGER.info(f"Pre-curation CSV written: {pre_csv_ref}")

    chunks = _chunk(payload_term_rows, chunk_size)
    spawn_prompts = []
    for idx, rows in enumerate(chunks):
        terms_csv = _to_csv(mode_fieldnames, rows)
        spawn_prompts.append(
            {
                "chunk_index": idx,
                "terms_count": len(rows),
                "pre_curated_rows": rows,
                "spawn_prompt": prompt_builder.build_spawn_prompt(
                    session_id,
                    idx,
                    mode,
                    config,
                    terms_csv,
                    len(rows),
                ),
            }
        )

    manifest = {
        "session_id": session_id,
        "run_type": RunType.full.value,
        "project_id": project_id,
        "project_name": project_name,
        "category_id": category_id,
        "category_name": category_name,
        "mode": mode.value,
        "status": "in_progress",
        "created_at": _now_iso(),
        "config": config.model_dump(),
        "mode_fieldnames": mode_fieldnames,
        "full_fieldnames": full_fieldnames,
        "total_terms": len(payload_term_rows),
        "total_chunks": len(chunks),
        "spawn_prompts": spawn_prompts,
        "pre_csv_ref": pre_csv_ref,
    }

    session_file = await store.write_session_manifest(manifest)
    LOGGER.info(
        f"Session {session_id}: {len(payload_term_rows)} terms in {len(chunks)} chunks"
    )

    # Omit spawn_prompts from the response — they embed full term CSVs and would exceed MCP output limits.
    chunk_metadata = [
        {"chunk_index": p["chunk_index"], "terms_count": p["terms_count"]}
        for p in spawn_prompts
    ]

    response: dict = {
        "session_id": session_id,
        "run_type": RunType.full.value,
        "category_id": category_id,
        "category_name": category_name,
        "total_terms": len(payload_term_rows),
        "total_chunks": len(chunks),
        "session_file": session_file,
        "chunks": chunk_metadata,
        "orchestrator_instruction": (
            f"Spawn ALL {len(chunks)} sub-agents in a SINGLE parallel batch now. "
            f"Each sub-agent receives only session_id='{session_id}' and its chunk_index (0 to {len(chunks) - 1}). "
            f"Each sub-agent must: "
            f"(1) call glossary_curator operation='get_chunk_prompt' to fetch its terms and instructions, "
            f"(2) curate the terms as instructed, "
            f"(3) call glossary_curator operation='submit_chunk' with the curated CSV, then TERMINATE. "
            f"After all sub-agents finish, YOU (the orchestrator) call session_status (no chunk_index) to confirm "
            f"all chunks are complete. When session_status returns status='ready_for_review', present the "
            f"after_csv_ref to the user and ask for their explicit approval. "
            f"Only call complete_session after the user approves."
        ),
    }
    if scope_skipped_count:
        response["scope_skipped_count"] = scope_skipped_count
        response["scope_skipped_note"] = _scope_skipped_note(mode, scope_skipped_count)
    if unresolved_part_of_term_uuids:
        response["part_of_terms_warning"] = (
            "Some Part Of Terms could not be resolved from artifact IDs to names "
            "and will appear as UUIDs in sub-agent prompts. This is a warning, the sub-agents will ignore this and the curation can continue."
        )
    return response


async def _start_preview_session(  # noqa: PLR0913 # Baseline
    category_id: str,
    mode: CurationMode,
    chunk_size: int,
    target_language: Optional[str],  # noqa: UP045 # Baseline
    store: AbstractSessionStore,
    definition_prompt: Optional[str] = None,  # noqa: UP045 # Baseline
    classification_prompt: Optional[str] = None,  # noqa: UP045 # Baseline
    translation_prompt: Optional[str] = None,  # noqa: UP045 # Baseline
    definition_scope: DefinitionScope = DefinitionScope.all,
    project_id: str = "",
    project_name: str = "",
    artifact_ids: Optional[list[str]] = None,  # noqa: UP045 # Baseline
) -> dict:
    """Start a preview session: sample chunk 0 only, no import possible.

    Exports and filters terms identically to a full session so the user sees
    accurate total_terms and total_chunks counts. Only chunk 0 prompt data is
    stored in the manifest; the remaining chunks are discarded after the count
    is calculated.
    """
    config = CurationConfig(
        chunk_size=chunk_size,
        target_language=target_language,
        definition_scope=definition_scope,
        definition_prompt=definition_prompt,
        classification_prompt=classification_prompt,
        translation_prompt=translation_prompt,
        artifact_ids=artifact_ids,
    )

    prepared = await _prepare_session_terms(category_id, mode, config)
    if "status" in prepared:
        return prepared

    category_name = prepared["category_name"]
    full_fieldnames = prepared["full_fieldnames"]
    all_rows = prepared["all_rows"]
    payload_term_rows = prepared["payload_term_rows"]
    mode_fieldnames = prepared["mode_fieldnames"]
    scope_skipped_count = prepared["scope_skipped_count"]
    unresolved_part_of_term_uuids: set[str] = prepared["unresolved_part_of_term_uuids"]

    # Partition all terms to get an accurate chunk count, but only retain chunk 0.
    all_chunks = _chunk(payload_term_rows, chunk_size)
    total_chunks = len(all_chunks)
    preview_rows = all_chunks[0]

    session_id = _new_preview_session_id(mode.value)
    # Use all_rows (pre-scope-filter) so before.csv retains all IKC columns (e.g. Artifact Type).
    pre_csv_content = _to_csv(full_fieldnames, all_rows)
    pre_csv_ref = await store.write_pre_csv(session_id, pre_csv_content)
    LOGGER.info(f"Preview pre-curation CSV written: {pre_csv_ref}")

    terms_csv = _to_csv(mode_fieldnames, preview_rows)
    preview_spawn_prompt = {
        "chunk_index": 0,
        "terms_count": len(preview_rows),
        "pre_curated_rows": preview_rows,
        "spawn_prompt": prompt_builder.build_spawn_prompt(
            session_id,
            0,
            mode,
            config,
            terms_csv,
            len(preview_rows),
        ),
    }

    manifest = {
        "session_id": session_id,
        "run_type": RunType.preview.value,
        "project_id": project_id,
        "project_name": project_name,
        "category_id": category_id,
        "category_name": category_name,
        "mode": mode.value,
        "status": "in_progress",
        "created_at": _now_iso(),
        "config": config.model_dump(),
        "mode_fieldnames": mode_fieldnames,
        "full_fieldnames": full_fieldnames,
        "total_terms": len(payload_term_rows),
        "total_chunks": total_chunks,
        "chunk_size": chunk_size,
        "spawn_prompts": [preview_spawn_prompt],
        "pre_csv_ref": pre_csv_ref,
    }

    session_file = await store.write_session_manifest(manifest)
    LOGGER.info(
        f"Preview session {session_id}: {len(preview_rows)} terms in chunk 0 "
        f"of {total_chunks} total chunks"
    )

    response: dict = {
        "session_id": session_id,
        "run_type": RunType.preview.value,
        "category_id": category_id,
        "category_name": category_name,
        "total_terms": len(payload_term_rows),
        "total_chunks": total_chunks,
        "session_file": session_file,
        "chunks": [{"chunk_index": 0, "terms_count": len(preview_rows)}],
        "orchestrator_instruction": (
            f"This is a PREVIEW session — chunk 0 of {total_chunks} total chunks. "
            f"Spawn ONE sub-agent for chunk_index=0 only. "
            f"The sub-agent must: "
            f"(1) call glossary_curator operation='get_chunk_prompt' with session_id='{session_id}' and chunk_index=0, "
            f"(2) curate the returned terms as instructed, "
            f"(3) call glossary_curator operation='submit_chunk' with the curated CSV, then TERMINATE. "
            f"After the sub-agent terminates, call session_status with session_id='{session_id}' (no chunk_index) "
            f"to confirm the preview is complete and retrieve the summary. "
            f"Do NOT call complete_session — preview sessions cannot be completed or imported."
        ),
    }
    if scope_skipped_count:
        response["scope_skipped_count"] = scope_skipped_count
        response["scope_skipped_note"] = _scope_skipped_note(mode, scope_skipped_count)
    if unresolved_part_of_term_uuids:
        response["part_of_terms_warning"] = (
            "Some Part Of Terms could not be resolved from artifact IDs to names "
            "and will appear as UUIDs in sub-agent prompts. This is a warning, the sub-agents will ignore this and the curation can continue."
        )
    return response


def _get_number_of_expected_chunks_in_preview(manifest: dict) -> int:
    """Return the number of chunks expected for a preview session.

    A preview stores only chunk 0, so the expected count is the number of
    spawn_prompts entries (always 1) rather than total_chunks (the full-run count).
    """
    return len(manifest.get("spawn_prompts", []))


def _preview_submit_completion_response(response: dict) -> dict:
    """Return an updated submit_chunk response signalling preview completion.

    Replaces the full-session all_chunks_complete signal with a preview-specific
    one that directs the orchestrator to call session_status, not complete_session.
    """
    return {
        **response,
        "preview_complete": True,
        "next_action": "terminate",
        "next_action_detail": (
            "Preview chunk 0 is saved. Terminate immediately. "
            "The orchestrator will call session_status to inspect the curated results. "
            "Do NOT call complete_session — preview sessions cannot be imported."
        ),
    }


def _retry_message_for_mode(mode: str) -> str:
    """Return the retry instruction string appropriate for the curation mode."""
    if mode == "classification":
        return (
            "Fix the reported issues and resubmit the full CSV. "
            "The 'Classifications' column must contain a valid classification name or be left empty."
        )
    return (
        "Fix the reported issues and resubmit the full CSV. "
        "Definitions must be 3+ words, not empty, and not just repeat the term name."
    )


async def _persist_needs_revision_outcome(
    session_id: str,
    chunk_index: int,
    issues: list,
    store: AbstractSessionStore,
) -> None:
    """Write 'needs_revision' outcome onto the last open respawn entry, if present."""
    existing_marker = await store.read_inflight_marker(session_id, chunk_index) or {}
    respawns = existing_marker.get("respawns", [])
    if respawns and respawns[-1].get("outcome") is None:
        respawns[-1]["outcome"] = "needs_revision"
        respawns[-1]["issues"] = [i["problem"] for i in issues[:10]]
        existing_marker["respawns"] = respawns
        await store.overwrite_inflight_marker(session_id, chunk_index, existing_marker)


async def _persist_chunk_error_outcome(
    session_id: str,
    chunk_index: int,
    outcome: str,
    store: AbstractSessionStore,
) -> None:
    """Write a named error outcome onto the last open respawn entry, if present.

    Used for non-quality errors (e.g. row_count_mismatch) that should immediately
    surface the chunk as stalled so the orchestrator respawns it without waiting
    for the 600-second stall timeout.
    """
    existing_marker = await store.read_inflight_marker(session_id, chunk_index) or {}
    respawns = existing_marker.get("respawns", [])
    if respawns and respawns[-1].get("outcome") is None:
        respawns[-1]["outcome"] = outcome
        existing_marker["respawns"] = respawns
        await store.overwrite_inflight_marker(session_id, chunk_index, existing_marker)


def _decorate_all_done(response: dict, total: int) -> None:
    """Add all-chunks-complete fields to *response* in-place."""
    response["all_chunks_complete"] = True
    response["next_action"] = "terminate"
    response["next_action_detail"] = (
        f"All {total} chunks are saved. Terminate immediately. "
        f"The orchestrator will call complete_session — do NOT call it yourself."
    )


async def _submit_chunk(  # noqa: PLR0911 # Baseline
    session_id: str,
    chunk_index: int,
    sub_agent_id: str,
    curated_terms_csv: str,
    store: AbstractSessionStore,
) -> dict:
    manifest = await store.read_session_manifest(session_id)
    if not manifest:
        return {
            "status": "error",
            "error_type": "session_not_found",
            "chunk_index": chunk_index,
            "message": f"Session {session_id} not found.",
        }

    total = manifest["total_chunks"]
    if chunk_index < 0 or chunk_index >= total:
        return {
            "status": "error",
            "error_type": "invalid_chunk_index",
            "chunk_index": chunk_index,
            "total_chunks": total,
            "message": f"chunk_index must be between 0 and {total - 1}.",
        }

    try:
        fieldnames, rows = _parse_csv(curated_terms_csv)
    except Exception as e:
        return {
            "status": "error",
            "error_type": "invalid_csv",
            "chunk_index": chunk_index,
            "message": f"CSV parsing failed: {e}",
            "retry_instructions": "Return valid CSV with a header row.",
        }

    mode = manifest["mode"]
    if mode not in [m.value for m in CurationMode]:
        return {
            "status": "error",
            "error_type": "invalid_mode",
            "chunk_index": chunk_index,
            "message": f"Invalid or missing curation mode: {mode}",
        }

    missing_cols = [
        c for c in get_mode_curation_fieldnames(mode) if c not in fieldnames
    ]
    if missing_cols:
        return {
            "status": "error",
            "error_type": "invalid_csv",
            "chunk_index": chunk_index,
            "message": f"Missing required columns: {', '.join(missing_cols)}",
            "retry_instructions": f"CSV must include: {', '.join(missing_cols)}",
        }

    spawn_prompts = manifest.get("spawn_prompts", [])
    expected_rows = next(
        (sp["terms_count"] for sp in spawn_prompts if sp["chunk_index"] == chunk_index),
        None,
    )
    if expected_rows is not None and len(rows) != expected_rows:
        await _persist_chunk_error_outcome(
            session_id, chunk_index, "row_count_mismatch", store
        )
        LOGGER.warning(
            f"[curator] row_count_mismatch session={session_id} chunk={chunk_index} "
            f"expected={expected_rows} actual={len(rows)} — "
            f"likely unescaped commas or quotes in Description field; chunk will be respawned."
        )
        return {
            "status": "error",
            "error_type": "row_count_mismatch",
            "chunk_index": chunk_index,
            "expected_rows": expected_rows,
            "actual_rows": len(rows),
            "message": (
                f"CSV row count mismatch for chunk {chunk_index}: "
                f"expected {expected_rows} rows but parsed {len(rows)}. "
                f"This usually means a Description field contains unescaped commas or quotes."
            ),
            "retry_instructions": (
                f"Re-submit chunk {chunk_index} with a corrected CSV. "
                f"Wrap every field value in double quotes. "
                f'Escape any double-quote characters inside a value as "". '
                f"The output must contain exactly {expected_rows} data rows (excluding the header)."
            ),
        }

    issues = quality_issues(rows, mode)
    if issues:
        await _persist_needs_revision_outcome(session_id, chunk_index, issues, store)
        return {
            "status": "needs_revision",
            "chunk_index": chunk_index,
            "session_id": session_id,
            "issue_count": len(issues),
            "issues": issues[:10],
            "retry_instructions": _retry_message_for_mode(mode),
        }

    chunk_lock = await _get_chunk_lock(session_id, chunk_index)
    async with chunk_lock:
        if await store.chunk_result_exists(session_id, chunk_index):
            return {
                "status": "chunk_already_exists",
                "error_type": "chunk_already_exists",
                "chunk_index": chunk_index,
                "message": f"Chunk {chunk_index} already submitted for session {session_id}.",
                "retry_instructions": "No action needed — this chunk is already saved.",
            }

        chunk_file = await store.write_chunk_result(
            session_id,
            chunk_index,
            {
                "chunk_index": chunk_index,
                "session_id": session_id,
                "sub_agent_id": sub_agent_id,
                "submitted_at": _now_iso(),
                "terms_count": len(rows),
                "fieldnames": fieldnames,
                "curated_rows": rows,
            },
        )

    # Evict the lock once the chunk is durably saved to prevent unbounded growth.
    async with _chunk_submit_locks_guard:
        _chunk_submit_locks.pop((session_id, chunk_index), None)

    # For a preview session only chunk 0 is stored; use spawn_prompts count so
    # all_done fires correctly rather than comparing against the full-run total.
    expected_chunks = (
        _get_number_of_expected_chunks_in_preview(manifest)
        if manifest.get("run_type") == RunType.preview.value
        else total
    )
    completed = await store.list_completed_chunks(session_id, expected_chunks)
    all_done = len(completed) == expected_chunks

    response: dict = {
        "status": "chunk_saved",
        "chunk_index": chunk_index,
        "session_id": session_id,
        "terms_saved": len(rows),
        "chunk_file": chunk_file,
        "progress": _progress(len(completed), expected_chunks),
    }

    if all_done:
        if manifest.get("run_type") == RunType.preview.value:
            updated_manifest = {**manifest, "status": "preview_completed"}
            await store.write_session_manifest(updated_manifest)
            response = _preview_submit_completion_response(response)
        else:
            _decorate_all_done(response, total)

    return response


_STALE_THRESHOLD_SECONDS = 600  # chunk in-flight for > 10 min is considered stalled


async def _chunk_flight_status(
    session_id: str,
    chunk_index: int,
    store: AbstractSessionStore,
    created_at: Optional[str] = None,  # noqa: UP045 # Baseline
) -> tuple[str, Optional[str]]:  # noqa: UP045 # Baseline
    """Return (state, timestamp) where state is 'waiting', 'in_flight', 'stalled', or 'blocked'.

    Blocked check (len(respawns) >= 2) takes precedence over the stall-threshold check.
    A chunk that has been waiting longer than _STALE_THRESHOLD_SECONDS is also treated as 'stalled'.
    """
    marker = await store.read_inflight_marker(session_id, chunk_index)
    if not marker:
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                elapsed = (datetime.now(UTC) - created).total_seconds()
                if elapsed > _STALE_THRESHOLD_SECONDS:
                    return "stalled", created_at
            except Exception as e:  # noqa: BLE001
                LOGGER.debug(
                    f"[curator] Could not parse created_at timestamp {created_at!r}: {e}"
                )
        return "waiting", created_at
    # Blocked check precedes stall-threshold — len(respawns) >= 2 is terminal.
    if len(marker.get("respawns", [])) >= 2:  # noqa: PLR2004 # Baseline
        return "blocked", marker["started_at"]
    started_at = marker["started_at"]
    # If the last respawn recorded a terminal error outcome (e.g. row_count_mismatch)
    # treat the chunk as stalled immediately — no need to wait for the timeout.
    respawns = marker.get("respawns", [])
    if respawns and respawns[-1].get("outcome") not in (None, "needs_revision"):
        return "stalled", started_at
    try:
        started = datetime.fromisoformat(started_at)
        elapsed = (datetime.now(UTC) - started).total_seconds()
        state = "stalled" if elapsed > _STALE_THRESHOLD_SECONDS else "in_flight"
    except Exception as e:  # noqa: BLE001
        LOGGER.debug(
            f"[curator] Could not parse started_at timestamp {started_at!r}: {e}"
        )
        state = "in_flight"
    return state, started_at


_TERMINAL_STATUSES = frozenset(
    {
        "completed",
        "import_failed",
        "completed_with_blocked_chunks",
        "ready_for_review",
        "stale_session",
    }
)


async def _resolve_chunk_state(
    session_id: str,
    chunk_index: int,
    manifest: dict,
    store: AbstractSessionStore,
    is_terminal: bool,
) -> str:
    """Return the state string for a single chunk."""
    if chunk_index in manifest.get("blocked_chunks", []):
        return "blocked"
    result_exists = await store.chunk_result_exists(session_id, chunk_index)
    if result_exists:
        return "completed"
    if is_terminal:
        return "blocked"
    state, _ = await _chunk_flight_status(
        session_id, chunk_index, store, manifest.get("created_at")
    )
    return state


async def _resolve_post_curated_rows(
    session_id: str,
    chunk_index: int,
    is_terminal: bool,
    chunks_map: dict,
    store: AbstractSessionStore,
) -> Optional[list]:  # noqa: UP045 # Baseline
    """Return post-curated rows for a completed chunk, or None."""
    if is_terminal:
        return chunks_map.get(chunk_index, {}).get("post_curated_rows")
    chunk_result = await store.read_chunk_result(session_id, chunk_index)
    return (chunk_result or {}).get("curated_rows")


def _resolve_respawns(
    chunk_index: int,
    marker: Optional[dict],  # noqa: UP045 # Baseline
    is_terminal: bool,
    chunks_map: dict,
) -> Optional[list]:  # noqa: UP045 # Baseline
    """Return the respawn history for a chunk, or None if empty/absent."""
    respawns: Optional[list] = marker.get("respawns") if marker else None  # noqa: UP045 # Baseline
    if respawns is None and is_terminal:
        respawns = chunks_map.get(chunk_index, {}).get("respawns")
    return respawns or None


async def _session_status_chunk_detail(
    session_id: str,
    chunk_index: int,
    manifest: dict,
    store: AbstractSessionStore,
) -> dict:
    """Return deep diagnostic detail for a single chunk."""
    total = manifest["total_chunks"]
    if chunk_index < 0 or chunk_index >= total:
        return {
            "status": "error",
            "error_type": "invalid_chunk_index",
            "chunk_index": chunk_index,
            "total_chunks": total,
            "message": f"chunk_index must be between 0 and {total - 1}.",
        }

    # chunk_files_deleted is True only after _finalise_session has run (complete_session).
    # ready_for_review is a closed session for progress-counting purposes but chunk files
    # still exist at that point — _finalise_session has not yet run.
    chunk_files_deleted = manifest.get("status", "in_progress") in {
        "completed",
        "import_failed",
        "completed_with_blocked_chunks",
    }
    chunks_map = (
        {c["chunk_index"]: c for c in manifest.get("chunks", [])}
        if chunk_files_deleted
        else {}
    )

    state = await _resolve_chunk_state(
        session_id, chunk_index, manifest, store, chunk_files_deleted
    )

    spawn_prompts_map = {p["chunk_index"]: p for p in manifest.get("spawn_prompts", [])}
    pre_curated_rows = spawn_prompts_map.get(chunk_index, {}).get(
        "pre_curated_rows", []
    )

    post_curated_rows: Optional[list] = None  # noqa: UP045 # Baseline
    if state == "completed":
        post_curated_rows = await _resolve_post_curated_rows(
            session_id, chunk_index, chunk_files_deleted, chunks_map, store
        )

    marker = await store.read_inflight_marker(session_id, chunk_index)
    respawns = _resolve_respawns(chunk_index, marker, chunk_files_deleted, chunks_map)

    return {
        "session_id": session_id,
        "chunk_index": chunk_index,
        "state": state,
        "project_url": construct_project_url(manifest["project_id"]),
        "pre_curated_rows": pre_curated_rows,
        "post_curated_rows": post_curated_rows,
        "respawns": respawns,
    }


async def _collect_chunk_counts(  # noqa: PLR0913 # Baseline
    session_id: str,
    total: int,
    manifest: dict,
    store: AbstractSessionStore,
    is_terminal: bool,
    expected_chunks: Optional[int] = None,  # noqa: UP045 # Baseline
) -> tuple[list[int], list[int], int]:
    """Return (completed, pending, curated_count) for the session.

    For terminal sessions the chunk files are gone; synthesise from the manifest.
    For live sessions read from the store.
    expected_chunks overrides total for preview sessions (which only store chunk 0).
    """
    effective = expected_chunks if expected_chunks is not None else total
    blocked_in_manifest: list[int] = manifest.get("blocked_chunks", [])
    if is_terminal:
        completed = [i for i in range(effective) if i not in blocked_in_manifest]
        curated_count = sum(c.get("terms_count", 0) for c in manifest.get("chunks", []))
        return completed, [], curated_count

    completed = await store.list_completed_chunks(session_id, effective)
    pending = [i for i in range(effective) if i not in completed]
    chunk_results = await asyncio.gather(
        *(store.read_chunk_result(session_id, i) for i in completed)
    )
    curated_count = sum((r or {}).get("terms_count", 0) for r in chunk_results)
    return completed, pending, curated_count


async def _build_pending_detail(
    session_id: str,
    store: AbstractSessionStore,
    pending: list[int],
    session_created_at: Optional[str],  # noqa: UP045 # Baseline
    blocked_chunks: list[int],
) -> tuple[list[dict], list[int], list[int]]:
    """Return (pending_detail, stalled_chunks, updated blocked_chunks) for pending chunk indices."""
    pending_detail: list[dict] = []
    stalled_chunks: list[int] = []
    for idx in pending:
        state, started_at = await _chunk_flight_status(
            session_id, idx, store, session_created_at
        )
        entry: dict = {"chunk_index": idx, "state": state}
        if started_at:
            entry["started_at"] = started_at
        pending_detail.append(entry)
        if state == "stalled":
            stalled_chunks.append(idx)
        elif state == "blocked" and idx not in blocked_chunks:
            blocked_chunks.append(idx)
    return pending_detail, stalled_chunks, blocked_chunks


def _respawn_instruction(
    stalled_chunks: list[int], pending: list[int]
) -> Optional[str]:  # noqa: UP045 # Baseline
    """Return a respawn instruction string, or None if nothing needs respawning."""
    if stalled_chunks:
        return (
            f"Chunks {stalled_chunks} are stalled (in-flight > {_STALE_THRESHOLD_SECONDS}s). "
            f"Re-spawn those sub-agents in a SINGLE parallel batch. Each sub-agent: "
            f"(1) call get_chunk_prompt with its chunk_index, "
            f"(2) follow the returned spawn_prompt, "
            f"(3) call submit_chunk."
        )
    if pending:
        return (
            f"Re-spawn ALL {len(pending)} pending sub-agents in a SINGLE parallel batch. "
            f"Each sub-agent: (1) get_chunk_prompt → (2) curate → (3) submit_chunk."
        )
    return None


async def _handle_full_session_completion(
    session_id: str,
    manifest: dict,
    store: AbstractSessionStore,
) -> dict | tuple[dict, str]:
    """Run staleness check then prepare the review CSV for a completed full session.

    Returns an error dict if the session is stale or the check fails, otherwise
    returns (updated_manifest, new_status) so the caller can continue building
    the status response.
    """
    staleness_result = await check_session_staleness(session_id, manifest, store)

    if staleness_result.check_error:
        return {
            "status": "error",
            "error_type": "staleness_check_failed",
            "session_id": session_id,
            "message": staleness_result.message
            or "Staleness check failed due to a transient error. Please retry session_status.",
        }

    if staleness_result.is_stale:
        await store.write_session_manifest({**manifest, "status": "stale_session"})
        return {
            "status": "error",
            "error_type": "session_stale",
            "session_id": session_id,
            "message": staleness_result.message,
        }

    # Not stale — prepare the review CSV and transition to ready_for_review.
    updated_manifest = await _prepare_full_session_review(session_id, manifest, store)
    if updated_manifest.get("status") == "error":
        return updated_manifest
    return updated_manifest, updated_manifest["status"]


async def _session_status(
    session_id: str,
    store: AbstractSessionStore,
    chunk_index: Optional[int] = None,  # noqa: UP045 # Baseline
) -> dict:
    manifest = await store.read_session_manifest(session_id)
    if not manifest:
        return {
            "status": "error",
            "error_type": "session_not_found",
            "session_id": session_id,
        }

    if chunk_index is not None or manifest.get("run_type") == RunType.preview.value:
        return await _session_status_chunk_detail(
            session_id, chunk_index or 0, manifest, store
        )

    total = manifest["total_chunks"]
    status = manifest.get("status", "in_progress")
    # For a preview session only chunk 0 is stored; use spawn_prompts count so
    # pending/completed are calculated against the preview scope, not the full-run total.
    expected_chunks = (
        _get_number_of_expected_chunks_in_preview(manifest)
        if manifest.get("run_type") == RunType.preview.value
        else None
    )
    is_terminal = status in _TERMINAL_STATUSES

    completed, pending, curated_count = await _collect_chunk_counts(
        session_id, total, manifest, store, is_terminal, expected_chunks=expected_chunks
    )

    # For a full session: on the first all-chunks-complete check, run staleness check
    # then build the review CSV and transition the manifest to ready_for_review.
    blocked_in_manifest = set(manifest.get("blocked_chunks", []))
    is_full_session = manifest.get("run_type") != RunType.preview.value
    if (
        is_full_session
        and not (set(pending) - blocked_in_manifest)
        and status == "in_progress"
    ):
        result = await _handle_full_session_completion(session_id, manifest, store)
        if isinstance(result, dict):
            return result  # error response — propagate immediately
        manifest, status = result

    blocked_chunks: list[int] = list(manifest.get("blocked_chunks", []))
    pending_detail, stalled_chunks, blocked_chunks = await _build_pending_detail(
        session_id, store, pending, manifest.get("created_at"), blocked_chunks
    )

    effective = expected_chunks if expected_chunks is not None else total
    response: dict = {
        "session_id": session_id,
        "category_id": manifest["category_id"],
        "category_name": manifest["category_name"],
        "mode": manifest["mode"],
        "status": status,
        "project_url": construct_project_url(manifest["project_id"]),
        "total_terms": manifest["total_terms"],
        "total_chunks": total,
        "completed_chunks": completed,
        "pending_chunks": pending,
        "pending_detail": pending_detail,
        "stalled_chunks": stalled_chunks,
        "curated_terms_count": curated_count,
        "progress": _progress(len(completed), effective),
        "created_at": manifest["created_at"],
    }
    if blocked_chunks:
        response["blocked_chunks"] = blocked_chunks
    actionable_pending = [i for i in pending if i not in blocked_chunks]
    instruction = _respawn_instruction(stalled_chunks, actionable_pending)
    if instruction:
        response["respawn_instruction"] = instruction

    if status == "ready_for_review":
        response["after_csv_ref"] = manifest["after_csv_ref"]
        response["orchestrator_instruction"] = (
            "All chunks are complete. The consolidated after CSV is ready. "
            "Present the after_csv_ref to the user and ask for their approval before proceeding. "
            "Only call complete_session after the user explicitly approves."
        )

    return response


async def _backfill_stalled_outcome(
    session_id: str,
    chunk_index: int,
    existing_marker: dict,
    store: AbstractSessionStore,
) -> None:
    """If the last respawn entry has no outcome, set it to 'stalled' and persist."""
    respawns: list = existing_marker.get("respawns", [])
    if respawns and respawns[-1].get("outcome") is None:
        respawns[-1]["outcome"] = "stalled"
        existing_marker["respawns"] = respawns
        await store.overwrite_inflight_marker(session_id, chunk_index, existing_marker)


async def _handle_respawn_cap(
    session_id: str,
    chunk_index: int,
    existing_marker: Optional[dict],  # noqa: UP045 # Baseline
    manifest: dict,
    store: AbstractSessionStore,
) -> dict:
    """Backfill stalled outcome, block the chunk in the manifest, return a blocked response."""
    if existing_marker:
        await _backfill_stalled_outcome(session_id, chunk_index, existing_marker, store)
    blocked = manifest.get("blocked_chunks", [])
    if chunk_index not in blocked:
        await store.write_session_manifest(
            {**manifest, "blocked_chunks": blocked + [chunk_index]}  # noqa: RUF005 # Baseline
        )
    return {
        "status": "blocked",
        "chunk_index": chunk_index,
        "message": (
            f"Chunk {chunk_index} has exceeded the maximum of 2 respawns and is permanently blocked. "
            f"Call complete_session to proceed with the remaining chunks, or "
            f"session_status(chunk_index={chunk_index}) to inspect the blocked terms."
        ),
    }


async def _record_inflight_entry(
    session_id: str,
    chunk_index: int,
    existing_marker: Optional[dict],  # noqa: UP045 # Baseline
    store: AbstractSessionStore,
) -> None:
    """Write (or append) an inflight marker entry for the current attempt."""
    if existing_marker:
        await _backfill_stalled_outcome(session_id, chunk_index, existing_marker, store)
        new_entry: dict = {
            "started_at": _now_iso(),
            "sub_agent_id": None,
            "outcome": None,
        }
        await store.write_inflight_marker(
            session_id, chunk_index, respawn_entry=new_entry
        )
    else:
        await store.write_inflight_marker(session_id, chunk_index)


async def _get_chunk_prompt(
    session_id: str, chunk_index: int, store: AbstractSessionStore
) -> dict:
    """Return the spawn_prompt for a single chunk — called by sub-agents, not the orchestrator."""
    manifest = await store.read_session_manifest(session_id)
    if not manifest:
        return {
            "status": "error",
            "error_type": "session_not_found",
            "session_id": session_id,
        }

    total = manifest["total_chunks"]
    if chunk_index < 0 or chunk_index >= total:
        return {
            "status": "error",
            "error_type": "invalid_chunk_index",
            "chunk_index": chunk_index,
            "total_chunks": total,
            "message": f"chunk_index must be between 0 and {total - 1}.",
        }

    if await store.chunk_result_exists(session_id, chunk_index):
        return {
            "status": "already_completed",
            "chunk_index": chunk_index,
            "session_id": session_id,
            "message": f"Chunk {chunk_index} has already been submitted — no action needed.",
        }

    all_prompts: list[dict] = manifest.get("spawn_prompts", [])
    prompt_entry = next(
        (p for p in all_prompts if p["chunk_index"] == chunk_index), None
    )
    if not prompt_entry:
        return {
            "status": "error",
            "error_type": "prompt_not_found",
            "chunk_index": chunk_index,
            "message": f"No spawn_prompt found for chunk {chunk_index} in session {session_id}.",
        }

    existing_marker = await store.read_inflight_marker(session_id, chunk_index)
    respawn_count = len(existing_marker.get("respawns", [])) if existing_marker else 0

    if respawn_count >= 2:  # noqa: PLR2004 # Baseline
        return await _handle_respawn_cap(
            session_id, chunk_index, existing_marker, manifest, store
        )

    await _record_inflight_entry(session_id, chunk_index, existing_marker, store)

    return {
        "status": "ok",
        "session_id": session_id,
        "chunk_index": chunk_index,
        "terms_count": prompt_entry["terms_count"],
        "spawn_prompt": prompt_entry["spawn_prompt"],
    }


async def _validate_complete_session(
    session_id: str,
    manifest: dict,
    store: AbstractSessionStore,
) -> tuple[Optional[dict], list[int], list[dict], list[dict], list[dict]]:  # noqa: UP045 # Baseline
    """Validate preconditions for complete_session.

    Returns (error, blocked_chunks, chunk_results, raw_curated_terms, original_rows).
    If error is not None the caller should return it immediately; the other values are empty.
    """
    total_chunks = manifest["total_chunks"]
    mode = manifest.get("mode", "")

    if mode not in [m.value for m in CurationMode]:
        return (
            {
                "status": "error",
                "error_type": "invalid_mode",
                "session_id": session_id,
                "message": f"Invalid or missing curation mode: {mode}",
                "instruction": "Re-run glossary_curator from start_session",
            },
            [],
            [],
            [],
            [],
        )

    completed = await store.list_completed_chunks(session_id, total_chunks)
    missing = [i for i in range(total_chunks) if i not in completed]
    if missing:
        blocked_chunks: list[int] = manifest.get("blocked_chunks", [])
        truly_missing = [i for i in missing if i not in blocked_chunks]
        if truly_missing:
            return (
                {
                    "status": "error",
                    "error_type": "incomplete_session",
                    "session_id": session_id,
                    "missing_chunks": truly_missing,
                    "progress": _progress(len(completed), total_chunks),
                    "instruction": f"Re-spawn sub-agents for chunks {truly_missing}, then retry complete_session.",
                },
                [],
                [],
                [],
                [],
            )
        # All missing chunks are blocked — proceed with partial completion.
    else:
        blocked_chunks = manifest.get("blocked_chunks", [])

    chunk_results, raw_curated_terms = await _aggregate_chunk_results(
        session_id, total_chunks, store, blocked_chunks
    )
    if not raw_curated_terms:
        return (
            {
                "status": "error",
                "error_type": "no_curated_terms",
                "session_id": session_id,
                "instruction": "Re-run glossary_curator from start_session",
            },
            [],
            [],
            [],
            [],
        )

    pre_csv_content = await store.read_pre_csv(session_id)
    if not pre_csv_content:
        return (
            {
                "status": "error",
                "error_type": "pre_csv_missing",
                "session_id": session_id,
                "message": (
                    "before.csv was not found in project storage — it may not have been "
                    "committed yet (storage is eventually consistent) or was deleted by a "
                    "previous complete_session call. Wait a few seconds and retry "
                    "complete_session, or re-run from start_session."
                ),
                "retry_instructions": "Call complete_session again in a few seconds.",
            },
            [],
            [],
            [],
            [],
        )
    _, original_rows = _parse_csv(pre_csv_content)

    if draft_error := await _check_draft_terms_from_rows(original_rows):
        return draft_error, [], [], [], []

    return None, blocked_chunks, chunk_results, raw_curated_terms, original_rows


async def _validate_classification_rows(
    import_csv: str,
) -> tuple[str, list[dict], set[str]]:
    """Filter the import CSV to remove rows with invalid classification values.

    Fetches live published classifications from IKC and strips any row whose
    ``Classifications`` column is non-empty but not in the valid set.  Rows
    with an empty classification are left unchanged (LLM chose not to classify).

    Args:
        import_csv: The assembled import CSV string (may include curation_pre_* columns).

    Returns:
        Tuple of (filtered_csv_str, invalid_row_records, valid_names).  The filtered CSV has
        the same header as the input; invalid_row_records is a list of dicts with
        keys ``artifact_id``, ``name``, and ``invalid_classification``.
    """
    fieldnames, rows = _parse_csv(import_csv)
    if CLASSIFICATION_MODE_CURATION_COLS[0] not in fieldnames:
        return import_csv, [], set()

    valid_names = await fetch_published_classifications()

    valid_rows: list[dict] = []
    invalid_records: list[dict] = []
    for row in rows:
        classification = (row.get(CLASSIFICATION_MODE_CURATION_COLS[0]) or "").strip()
        if classification and classification not in valid_names:
            invalid_records.append(
                {
                    "artifact_id": (row.get(_ARTIFACT_KEY_COL) or "").strip(),
                    "name": (row.get("Name") or "").strip(),
                    "invalid_classification": classification,
                }
            )
        else:
            valid_rows.append(row)

    return _to_csv(fieldnames, valid_rows), invalid_records, valid_names


async def _run_import(
    session_id: str,
    import_csv: str,
    store: AbstractSessionStore,
    existing_after_csv_ref: Optional[str] = None,  # noqa: UP045 # Baseline
) -> tuple[Optional[dict], str, Optional[object]]:  # noqa: UP045 # Baseline
    """Write after.csv (if not already written) and call the import API.

    Pass existing_after_csv_ref when the fast path already persisted after.csv
    during session_status — the write is skipped to avoid a redundant overwrite.

    Returns (error, after_csv_ref, result).
    If error is not None the caller should return it immediately.
    """
    if existing_after_csv_ref:
        after_csv_ref = existing_after_csv_ref
        LOGGER.info(f"After-curation CSV already exists: {after_csv_ref}")
    else:
        after_csv_ref = await store.write_after_csv(session_id, import_csv)
        LOGGER.info(f"After-curation CSV written: {after_csv_ref}")

    try:
        result = await import_csv_file(import_csv, merge_option="specified")
    except Exception as e:
        LOGGER.error(f"Import failed for session {session_id}: {e}", exc_info=True)
        return (
            {
                "status": "error",
                "error_type": "import_failed",
                "session_id": session_id,
                "message": str(e),
                "after_csv_saved_to": after_csv_ref,
                "retry_instructions": "Retry complete_session or import the saved CSV manually.",
            },
            after_csv_ref,
            None,
        )

    if not result.process_id and result.errors:
        error_messages = [
            err.error_message for err in result.errors if err.error_message
        ]
        LOGGER.error(
            f"Import rejected for session {session_id} (no process_id). Errors: {error_messages}"
        )
        return (
            {
                "status": "error",
                "error_type": "import_rejected",
                "session_id": session_id,
                "message": "Import API rejected the request — no process_id returned.",
                "import_errors": error_messages,
                "after_csv_saved_to": after_csv_ref,
                "retry_instructions": (
                    "Check import_errors above. Common causes: missing 'Category' column, "
                    "invalid 'Artifact Type' value, or a malformed CSV header. "
                    "Retry complete_session after fixing, or import the saved CSV manually."
                ),
            },
            after_csv_ref,
            None,
        )

    return None, after_csv_ref, result


async def _finalise_session(  # noqa: PLR0913 # Baseline
    session_id: str,
    manifest: dict,
    store: AbstractSessionStore,
    chunk_results: list[dict],
    blocked_chunks: list[int],
    result: object,
    curated_terms: list[dict],
    after_csv_ref: str,
) -> tuple[str, int, dict, list[dict], list[dict]]:
    """Build chunks_summary, write manifest, delete chunk files.

    Returns (session_status, blocked_term_count, summary, failure_details, chunks_summary).
    """
    total_chunks = manifest["total_chunks"]
    completed_at = _now_iso()
    import_failed = result.status == "FAILED"
    terms_succeeded = result.terms_created + result.terms_updated

    failure_details = [
        {
            "term_name": err.term_name or "(unknown)",
            "reason": err.error_message,
            "code": err.code,
            "line_number": err.line_number,
        }
        for err in result.errors
        if err.error_message
    ]

    total_terms_queued = manifest.get("total_terms", len(curated_terms))
    summary = {
        "imported": terms_succeeded,
        "failed": len(failure_details),
        "skipped": max(0, total_terms_queued - terms_succeeded - len(failure_details)),
        "import_status": result.status,
    }

    spawn_prompts_map = {p["chunk_index"]: p for p in manifest.get("spawn_prompts", [])}

    # On the fast path (ready_for_review), _prepare_full_session_review has already built
    # chunks_summary with pre/post rows and written it into the manifest before deleting the
    # chunk files. Reuse it directly; only fall back to building from chunk_results when the
    # manifest has no chunks yet (slow path: complete_session called before session_status).
    if manifest.get("chunks"):
        chunks_summary: list[dict] = manifest["chunks"]
    else:
        chunks_summary = [
            {
                "chunk_index": cr["chunk_index"],
                "sub_agent_id": cr.get("sub_agent_id"),
                "terms_count": cr.get("terms_count", 0),
                "submitted_at": cr.get("submitted_at"),
                "pre_curated_rows": spawn_prompts_map.get(cr["chunk_index"], {}).get(
                    "pre_curated_rows", []
                ),
                "post_curated_rows": cr.get("curated_rows", []),
            }
            for cr in chunk_results
        ]

    # Persist respawn history for blocked chunks before inflight marker files are deleted.
    for bi in blocked_chunks:
        sp = spawn_prompts_map.get(bi, {})
        blocked_marker = await store.read_inflight_marker(session_id, bi)
        chunks_summary.append(
            {
                "chunk_index": bi,
                "sub_agent_id": None,
                "terms_count": sp.get("terms_count", 0),
                "submitted_at": None,
                "pre_curated_rows": sp.get("pre_curated_rows", []),
                "post_curated_rows": None,
                "respawns": blocked_marker.get("respawns") if blocked_marker else None,
            }
        )

    has_blocked = bool(blocked_chunks)
    if has_blocked:
        session_status = "completed_with_blocked_chunks"
    elif import_failed:
        session_status = "import_failed"
    else:
        session_status = "completed"

    blocked_term_count = sum(
        spawn_prompts_map.get(i, {}).get("terms_count", 0) for i in blocked_chunks
    )

    completed_manifest = {
        **manifest,
        "status": session_status,
        "completed_at": completed_at,
        "process_id": result.process_id,
        "workflow_id": result.workflow_id,
        "import_summary": summary,
        "pre_csv_ref": manifest.get("pre_csv_ref"),
        "after_csv_ref": after_csv_ref,
        "chunks": chunks_summary,
        **(
            {"blocked_chunks": blocked_chunks, "blocked_term_count": blocked_term_count}
            if has_blocked
            else {}
        ),
    }
    await store.write_session_manifest(completed_manifest)
    await store.delete_chunk_files(session_id, total_chunks)

    LOGGER.info(
        f"Session {session_id} complete: {len(curated_terms)} terms, process_id={result.process_id}"
    )
    return (
        session_status,
        blocked_term_count,
        summary,
        failure_details,
        chunks_summary,
        completed_at,
    )


def _validate_complete_session_preconditions(
    session_id: str,
    manifest: Optional[dict],  # noqa: UP045 # Baseline
) -> Optional[dict]:  # noqa: UP045 # Baseline
    """Return an error dict if the session cannot be completed, otherwise None."""
    if not manifest:
        return {
            "status": "error",
            "error_type": "session_not_found",
            "session_id": session_id,
        }

    if manifest.get("run_type") == RunType.preview.value:
        return {
            "status": "error",
            "error_type": "preview_cannot_be_completed",
            "session_id": session_id,
            "message": (
                "Preview sessions cannot be completed or imported. "
                "Start a full session with run_type='full' to curate and import all terms."
            ),
        }

    current_status = manifest.get("status", "in_progress")
    if current_status == "completed":
        return {
            "status": "error",
            "error_type": "session_completed",
            "session_id": session_id,
            "message": f"Session is already '{current_status}' and cannot be completed again.",
        }

    return None


async def _resolve_import_csv(
    session_id: str,
    manifest: dict,
    store: AbstractSessionStore,
    current_status: str,
) -> tuple[Optional[dict], str, list[dict], list[int], list[dict], Optional[str]]:  # noqa: UP045 # Baseline
    """Return (error, import_csv, curated_terms, blocked_chunks, chunk_results, existing_after_csv_ref).

    Tries the fast path first (after.csv already written by session_status), falling back
    to re-aggregating chunk files when the CSV is absent or the session was never reviewed.
    """
    if current_status == "ready_for_review":
        after_csv_ref = manifest.get("after_csv_ref")
        import_csv_content = (
            await store.read_after_csv(session_id) if after_csv_ref else None
        )
        if import_csv_content:
            _, import_rows_parsed = _parse_csv(import_csv_content)
            curated_terms = [r for r in import_rows_parsed if _row_key(r)]
            return (
                None,
                import_csv_content,
                curated_terms,
                manifest.get("blocked_chunks", []),
                [],
                after_csv_ref,
            )
        # Storage race or file deleted — fall through to slow path.
        LOGGER.warning(
            f"Session {session_id}: after CSV not found at {after_csv_ref!r}, re-aggregating."
        )

    (
        error,
        blocked_chunks,
        chunk_results,
        raw_curated_terms,
        original_rows,
    ) = await _validate_complete_session(session_id, manifest, store)
    if error:
        return error, "", [], [], [], None

    all_pre_curated_rows: list[dict] = []
    for sp in manifest.get("spawn_prompts", []):
        all_pre_curated_rows.extend(sp.get("pre_curated_rows", []))

    import_csv = _build_after_csv(
        manifest, original_rows, raw_curated_terms, all_pre_curated_rows
    )
    _, all_import_rows_parsed = _parse_csv(import_csv)
    curated_terms = [r for r in all_import_rows_parsed if _row_key(r)]
    return None, import_csv, curated_terms, blocked_chunks, chunk_results, None


async def _complete_session(session_id: str, store: AbstractSessionStore) -> dict:  # noqa: PLR0911 # Baseline
    manifest = await store.read_session_manifest(session_id)
    if error := _validate_complete_session_preconditions(session_id, manifest):
        return error

    # Idempotency: if already stale_session, return error without re-checking
    current_status = manifest.get("status", "in_progress")
    if current_status == "stale_session":
        return {
            "status": "error",
            "error_type": "session_stale",
            "session_id": session_id,
            "message": "This curation session is stale and cannot be completed. Please start a new session.",
        }

    # Run staleness check before import
    staleness_result = await check_session_staleness(session_id, manifest, store)

    if staleness_result.check_error:
        # Transient export error — stay in ready_for_review, return error
        return {
            "status": "error",
            "error_type": "staleness_check_failed",
            "session_id": session_id,
            "message": staleness_result.message
            or "Staleness check failed due to a transient error. Please retry complete_session.",
        }

    if staleness_result.is_stale:
        # Stale — transition to stale_session, persist, return message
        updated_manifest = {**manifest, "status": "stale_session"}
        await store.write_session_manifest(updated_manifest)
        return {
            "status": "error",
            "error_type": "session_stale",
            "session_id": session_id,
            "message": staleness_result.message,
        }

    (
        error,
        import_csv,
        curated_terms,
        blocked_chunks,
        chunk_results,
        existing_after_csv_ref,
    ) = await _resolve_import_csv(session_id, manifest, store, current_status)
    if error:
        return error

    invalid_classification_rows: list[dict] = []
    valid_classification_names: set[str] = set()
    if manifest.get("mode") == CurationMode.classification.value:
        (
            import_csv,
            invalid_classification_rows,
            valid_classification_names,
        ) = await _validate_classification_rows(import_csv)
        _, data_rows = _parse_csv(import_csv)
        if not any(_row_key(r) for r in data_rows):
            return {
                "status": "error",
                "error_type": "no_valid_classifications",
                "session_id": session_id,
                "message": "All curated classification values were invalid. No rows to import.",
                "classification_validation": {
                    "invalid_rows": invalid_classification_rows,
                    "available_classifications": valid_classification_names,
                    "instruction": (
                        "Fix the classification names in IKC or re-run curation using one of the "
                        "available_classifications listed above, then call complete_session again."
                    ),
                },
            }

    import_error, after_csv_ref, result = await _run_import(
        session_id,
        import_csv,
        store,
        existing_after_csv_ref=existing_after_csv_ref,
    )
    if import_error:
        return import_error

    (
        session_status,
        blocked_term_count,
        summary,
        failure_details,
        _,
        completed_at,
    ) = await _finalise_session(
        session_id,
        manifest,
        store,
        chunk_results,
        blocked_chunks,
        result,
        curated_terms,
        after_csv_ref,
    )

    comment_warning: str | None = None
    if session_status != "import_failed" and result.workflow_id:
        mode_val = manifest.get("mode", "")
        config_val = manifest.get("config", {})
        prompt = (
            config_val.get("definition_prompt")
            or config_val.get("classification_prompt")
            or config_val.get("translation_prompt")
            or ""
        )
        session_id_val = manifest.get("session_id", "")
        project_id_val = manifest.get("project_id", "")
        session_filename = f"gc-{session_id_val}-session.json"
        comment_text = (
            f"Changes made by Glossary Curator MCP Tool:\n"
            f"- Mode: {mode_val.title()}\n"
            f"- Category Name: {manifest.get('category_name', '')}\n"
            f"- Project Name: {manifest.get('project_name', project_id_val)}\n"
            f"- Session Name: {session_filename}\n"
            f"- Prompt: {prompt}"
        )
        comment_warning = await write_workflow_comment(result.workflow_id, comment_text)

    cv = (
        ClassificationValidation(
            invalid_rows_removed=len(invalid_classification_rows),
            invalid_rows=invalid_classification_rows,
            available_classifications=valid_classification_names,
        )
        if invalid_classification_rows
        else None
    )
    outcome = CompleteSessionOutcome(
        classification_validation=cv,
        comment_warning=comment_warning,
    )
    return await _build_complete_session_response(
        session_id=session_id,
        manifest=manifest,
        result=result,
        curated_terms=curated_terms,
        session_status=session_status,
        blocked_term_count=blocked_term_count,
        blocked_chunks=blocked_chunks,
        summary=summary,
        failure_details=failure_details,
        completed_at=completed_at,
        outcome=outcome,
    )


async def _build_complete_session_response(  # noqa: PLR0913 # Baseline
    session_id: str,
    manifest: dict,
    result: Any,
    curated_terms: list[dict],
    session_status: str,
    blocked_term_count: int,
    blocked_chunks: list[int],
    summary: dict,
    failure_details: list[dict],
    completed_at: str,
    outcome: CompleteSessionOutcome | None = None,
) -> dict:
    outcome = outcome or CompleteSessionOutcome()
    sample_artifact_id = (
        (curated_terms[0].get(_ARTIFACT_KEY_COL) or "").strip()
        if curated_terms
        else None
    )
    task_url = await get_task_url(sample_artifact_id) if sample_artifact_id else None

    base_response: dict = {
        "session_id": session_id,
        "total_terms_processed": len(curated_terms),
        "import_summary": summary,
        "failure_details": failure_details,
        "process_id": result.process_id,
        "completed_at": completed_at,
        "category_id": manifest["category_id"],
        "category_url": construct_glossary_category_url(manifest["category_id"]),
        "project_url": construct_project_url(manifest["project_id"]),
        **({"task_url": task_url} if task_url else {}),
        **outcome.model_dump(exclude_none=True),
    }

    if session_status == "completed_with_blocked_chunks":
        return {
            **base_response,
            "status": "completed_with_blocked_chunks",
            "blocked_chunks": blocked_chunks,
            "blocked_term_count": blocked_term_count,
            "orchestrator_instruction": (
                "Import is complete for the successfully curated chunks. "
                "Present the import_summary, category_url and project_url to the user. "
                f"⚠️ {blocked_term_count} term(s) in {len(blocked_chunks)} chunk(s) could not be processed "
                f"after 3 attempts and were skipped (chunks: {blocked_chunks}). "
                f"To inspect the blocked terms, call session_status with chunk_index set to each blocked chunk index. "
                f"Once reviewed, a targeted follow-up session can be started using start_session with artifact_ids. "
                "Do NOT suggest starting a new task, new chat, or handoff. "
                "Offer to inspect blocked chunks or run a follow-up curation pass if the user wishes."
            ),
        }

    return {
        **base_response,
        "status": session_status,
        "orchestrator_instruction": (
            "Import is complete. Present the import_summary, category_url and project_url to the user. "
            "If failure_details is non-empty, show a table listing each failed term name and reason. "
            "Do NOT suggest starting a new task, new chat, or review step. "
            "Do NOT mention 'task2', 'task3', or any handoff. "
            "The workflow ends here — offer to run another curation pass if the user wishes."
        ),
    }


async def _aggregate_chunk_results(
    session_id: str,
    total_chunks: int,
    store: AbstractSessionStore,
    blocked_chunks: Optional[list[int]] = None,  # noqa: UP045 # Baseline
) -> tuple[list[dict], list[dict]]:
    """Return (chunk_results, flat_curated_rows) by reading all chunk files.

    Chunks listed in ``blocked_chunks`` are skipped so that any stale partial
    result written during an earlier failed attempt is not included in the
    after CSV or imported into the glossary.
    """
    blocked: set[int] = set(blocked_chunks or [])
    chunk_results = []
    curated_terms = []
    for idx in range(total_chunks):
        if idx in blocked:
            continue
        chunk_result = await store.read_chunk_result(session_id, idx)
        if chunk_result:
            chunk_results.append(chunk_result)
            curated_terms.extend(chunk_result.get("curated_rows", []))
    return chunk_results, curated_terms


def _build_pre_curated_map(pre_curated_rows: list[dict]) -> dict[str, dict]:
    """Key pre-curated snapshot rows by Artifact ID for fast lookup during merge."""
    return {
        row[_ARTIFACT_KEY_COL]: row
        for row in pre_curated_rows
        if row.get(_ARTIFACT_KEY_COL, "").strip()
    }


def _inject_pre_curated_fields(
    row: dict, pre_map: dict[str, dict], pre_cols: list[str]
) -> dict:
    """Copy snapshot column values into ``row`` with the ``curation_pre_`` prefix.

    ``pre_cols`` is the list of source column names (without prefix).  For each
    source column, the value is taken from the matching pre-curated snapshot row
    (looked up by Artifact ID) and stored as ``curation_pre_<col>``.  Rows with
    no Artifact ID or no matching snapshot are returned unchanged.
    """
    artifact_id = row.get(_ARTIFACT_KEY_COL, "").strip()
    if not artifact_id:
        return row
    snapshot = pre_map.get(artifact_id)
    if not snapshot:
        return row
    result = dict(row)
    for col in pre_cols:
        result[f"curation_pre_{col}"] = snapshot.get(col, "")
    return result


def _build_after_csv(
    manifest: dict,
    original_rows: list[dict],
    raw_curated_terms: list[dict],
    pre_curated_rows: list[dict],
) -> str:
    """Merge curated terms against original rows and return a review-ready CSV string.

    Applies the same mode-specific processing (translation dedup,
    blanks_only scoping) that complete_session uses, so the after CSV is exactly
    what will be imported if the user approves.  ``curation_pre_*`` snapshot
    columns are appended so reviewers can compare original vs curated values.
    """
    mode = manifest["mode"]
    mode_curated_fieldnames = get_mode_curation_fieldnames(mode)

    if (
        manifest.get("config", {}).get("definition_scope")
        == DefinitionScope.blanks_only.value
        or mode == CurationMode.classification.value
    ):
        curated_keys = {_row_key(t) for t in raw_curated_terms}
        original_rows = [r for r in original_rows if _row_key(r) in curated_keys]

    _, all_import_rows = process_mode_response(
        original_rows, raw_curated_terms, mode, mode_curated_fieldnames
    )
    all_import_rows = [r for r in all_import_rows if _row_key(r)]

    review_fieldnames = get_mode_review_fieldnames(mode)
    import_fieldnames = get_mode_import_fieldnames(mode)
    pre_cols = [
        col.removeprefix("curation_pre_")
        for col in review_fieldnames
        if col.startswith("curation_pre_")
    ]
    if pre_cols and pre_curated_rows:
        pre_map = _build_pre_curated_map(pre_curated_rows)
        all_import_rows = [
            _inject_pre_curated_fields(row, pre_map, pre_cols)
            for row in all_import_rows
        ]

    fieldnames = review_fieldnames if pre_cols else import_fieldnames
    return _to_csv(fieldnames, all_import_rows)


async def _prepare_full_session_review(
    session_id: str,
    manifest: dict,
    store: AbstractSessionStore,
) -> dict:
    """Aggregate all chunk results, build the after CSV, persist it, and update the manifest.

    Called by _session_status on the first all-chunks-complete status check for a full
    session. Writes {session_id}-after.csv to project storage, transitions the manifest
    status to 'ready_for_review', and returns the updated manifest.
    Returns an error dict (containing 'status': 'error') if anything fails.
    """
    total_chunks = manifest["total_chunks"]

    blocked_chunks: list[int] = manifest.get("blocked_chunks", [])
    chunk_results, raw_curated_terms = await _aggregate_chunk_results(
        session_id, total_chunks, store, blocked_chunks
    )
    if not raw_curated_terms:
        return {
            "status": "error",
            "error_type": "no_curated_terms",
            "session_id": session_id,
            "instruction": "Re-run glossary_curator from start_session.",
        }

    pre_csv_content = await store.read_pre_csv(session_id)
    if not pre_csv_content:
        return {
            "status": "error",
            "error_type": "pre_csv_missing",
            "session_id": session_id,
            "message": (
                "before.csv was not found in project storage. "
                "Wait a few seconds and call session_status again, or re-run from start_session."
            ),
            "retry_instructions": "Call session_status again in a few seconds.",
        }

    all_pre_curated_rows: list[dict] = []
    for sp in manifest.get("spawn_prompts", []):
        all_pre_curated_rows.extend(sp.get("pre_curated_rows", []))

    _, original_rows = _parse_csv(pre_csv_content)
    after_csv = _build_after_csv(
        manifest, original_rows, raw_curated_terms, all_pre_curated_rows
    )
    after_csv_ref = await store.write_after_csv(session_id, after_csv)
    LOGGER.info(f"Session {session_id}: after CSV written to {after_csv_ref}")

    # Build chunks_summary with pre/post rows while chunk files are still available,
    # then delete them. _finalise_session will reuse this from the manifest on the fast path.
    spawn_prompts_map = {p["chunk_index"]: p for p in manifest.get("spawn_prompts", [])}
    chunks_summary = [
        {
            "chunk_index": cr["chunk_index"],
            "sub_agent_id": cr.get("sub_agent_id"),
            "terms_count": cr.get("terms_count", 0),
            "submitted_at": cr.get("submitted_at"),
            "pre_curated_rows": spawn_prompts_map.get(cr["chunk_index"], {}).get(
                "pre_curated_rows", []
            ),
            "post_curated_rows": cr.get("curated_rows", []),
        }
        for cr in chunk_results
    ]

    updated_manifest = {
        **manifest,
        "status": "ready_for_review",
        "after_csv_ref": after_csv_ref,
        "chunks": chunks_summary,
    }
    await store.write_session_manifest(updated_manifest)

    # Delete transient chunk files now that after.csv and chunks_summary are safely written.
    # _finalise_session will also call delete_chunk_files as a no-op safety net for the slow path.
    await store.delete_chunk_files(session_id, total_chunks)
    LOGGER.info(f"Session {session_id}: chunk files deleted after review CSV written")

    return updated_manifest


_VALID_STATUS_FILTERS = {
    "all",
    "in_progress",
    "completed",
    "import_failed",
    "completed_with_blocked_chunks",
    "stale_session",
}
_VALID_RUN_TYPE_FILTERS = {"all", "preview", "full"}


async def _list_sessions(
    status_filter: str, store: AbstractSessionStore, run_type_filter: str
) -> dict:
    if status_filter not in _VALID_STATUS_FILTERS:
        return {
            "status": "error",
            "error_type": "invalid_status_filter",
            "message": f"Invalid status_filter {status_filter!r}. Valid values: {sorted(_VALID_STATUS_FILTERS)}",
        }

    if run_type_filter not in _VALID_RUN_TYPE_FILTERS:
        return {
            "status": "error",
            "error_type": "invalid_run_type_filter",
            "message": f"Invalid run_type_filter {run_type_filter!r}. Valid values: {sorted(_VALID_RUN_TYPE_FILTERS)}",
        }
    manifests = await store.list_all_session_manifests()
    sessions = []

    for m in manifests:
        sid = m["session_id"]
        total = m["total_chunks"]
        status = m.get("status", "in_progress")
        run_type = m.get("run_type", RunType.full.value)

        if status_filter != "all" and status != status_filter:  # noqa: PLR1714 # Baseline
            continue

        if run_type_filter != "all" and run_type != run_type_filter:  # noqa: PLR1714 # Baseline
            continue

        # Completed/import_failed sessions have no chunk files; progress is 100%.
        if status in ("completed", "import_failed"):
            done_count = total
        else:
            done = await store.list_completed_chunks(sid, total)
            done_count = len(done)

        sessions.append(
            {
                "session_id": sid,
                "run_type": run_type,
                "category_id": m["category_id"],
                "category_name": m["category_name"],
                "mode": m["mode"],
                "status": status,
                "total_terms": m["total_terms"],
                "total_chunks": total,
                "progress": _progress(done_count, total),
                "created_at": m["created_at"],
                "completed_at": m.get("completed_at"),
                "process_id": m.get("process_id"),
            }
        )

    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return {"sessions": sessions}


async def _init_store(project_id: str) -> AbstractSessionStore:
    """Resolve project storage details and return a fresh session store."""
    storage_details: dict = {}
    try:
        from app.shared.storage.project_utils import get_project_storage_details

        storage_details = await get_project_storage_details(project_id)
    except Exception as exc:
        LOGGER.warning(
            f"[_init_store] Could not resolve storage details for project '{project_id}': {exc}"
        )
    return get_session_store(project_id, storage_details)


async def handle_start_session(  # noqa: PLR0911 # Baseline
    start: Optional[StartSessionParams],  # noqa: UP045 # Baseline
    project_id: str,  # noqa: UP045 # Baseline
) -> dict:
    params = start or StartSessionParams(mode="")

    category_id = await confirm_uuid(params.category_identifier, find_category_id)
    try:
        project_name = await find_project_name(project_id)
    except Exception:
        project_name = project_id

    if not params.mode:
        return {"status": "error", "message": "mode is required for start_session"}
    try:
        curation_mode = CurationMode(params.mode)
    except ValueError:
        return {
            "status": "error",
            "message": f"Invalid mode '{params.mode}'. Use: translation, classification, definition",
        }

    if curation_mode == CurationMode.definition and not params.definition_prompt:
        return {
            "status": "error",
            "message": (
                "definition_prompt is required when mode='definition'. "
                "Assemble the prompt from the Definition Mode Prompts section in SKILL.md "
                "and pass it as the definition_prompt parameter."
            ),
        }

    if (
        curation_mode == CurationMode.classification
        and not params.classification_prompt
    ):
        return {
            "status": "error",
            "message": (
                "classification_prompt is required when mode='classification'. "
                "Assemble the prompt from the Classification Mode Prompts section in SKILL.md "
                "and pass it as the classification_prompt parameter."
            ),
        }

    if curation_mode == CurationMode.translation and not params.translation_prompt:
        return {
            "status": "error",
            "message": (
                "translation_prompt is required when mode='translation'. "
                "Assemble the prompt from the Translation Mode Prompts section in SKILL.md "
                "(substitute {source_language} and {target_language}) "
                "and pass it as the translation_prompt parameter."
            ),
        }

    try:
        parsed_scope = DefinitionScope(params.definition_scope)
    except ValueError:
        return {
            "status": "error",
            "message": f"Invalid definition_scope '{params.definition_scope}'. Use: all, blanks_only",
        }

    try:
        parsed_run_type = RunType(params.run_type)
    except ValueError:
        return {
            "status": "error",
            "message": f"Invalid run_type '{params.run_type}'. Use: preview, full",
        }

    store = await _init_store(project_id)

    if parsed_run_type == RunType.preview:
        return await _start_preview_session(
            category_id=category_id,
            mode=curation_mode,
            chunk_size=params.chunk_size,
            target_language=params.target_language,
            definition_scope=parsed_scope,
            definition_prompt=params.definition_prompt,
            classification_prompt=params.classification_prompt,
            translation_prompt=params.translation_prompt,
            project_id=project_id,
            project_name=project_name,
            store=store,
            artifact_ids=params.artifact_ids,
        )
    return await _start_session(
        category_id=category_id,
        mode=curation_mode,
        chunk_size=params.chunk_size,
        target_language=params.target_language,
        definition_scope=parsed_scope,
        definition_prompt=params.definition_prompt,
        classification_prompt=params.classification_prompt,
        translation_prompt=params.translation_prompt,
        project_id=project_id,
        project_name=project_name,
        store=store,
        artifact_ids=params.artifact_ids,
    )


async def handle_submit_chunk(
    session_id: Optional[str],  # noqa: UP045 # Baseline
    chunk_index: Optional[int],  # noqa: UP045 # Baseline
    sub_agent_id: Optional[str],  # noqa: UP045 # Baseline
    curated_terms_csv: Optional[str],  # noqa: UP045 # Baseline
    project_id: str,
) -> dict:
    for field, val in [
        ("session_id", session_id),
        ("chunk_index", chunk_index),
        ("sub_agent_id", sub_agent_id),
        ("curated_terms_csv", curated_terms_csv),
    ]:
        if val is None:
            return {
                "status": "error",
                "message": f"{field} is required for submit_chunk",
            }
    store = await _init_store(project_id)
    return await _submit_chunk(
        session_id, chunk_index, sub_agent_id, curated_terms_csv, store
    )


async def handle_session_status(
    session_id: Optional[str],  # noqa: UP045 # Baseline
    project_id: str,
    chunk_index: Optional[int] = None,  # noqa: UP045 # Baseline
) -> dict:
    if not session_id:
        return {
            "status": "error",
            "message": "session_id is required for session_status",
        }
    store = await _init_store(project_id)
    return await _session_status(session_id, store, chunk_index)


async def handle_get_chunk_prompt(
    session_id: Optional[str],  # noqa: UP045 # Baseline
    chunk_index: Optional[int],  # noqa: UP045 # Baseline
    project_id: str,  # noqa: UP045 # Baseline
) -> dict:
    if not session_id:
        return {
            "status": "error",
            "message": "session_id is required for get_chunk_prompt",
        }
    if chunk_index is None:
        return {
            "status": "error",
            "message": "chunk_index is required for get_chunk_prompt",
        }
    store = await _init_store(project_id)
    return await _get_chunk_prompt(session_id, chunk_index, store)


async def handle_complete_session(session_id: Optional[str], project_id: str) -> dict:  # noqa: UP045 # Baseline
    if not session_id:
        return {
            "status": "error",
            "message": "session_id is required for complete_session",
        }
    store = await _init_store(project_id)
    return await _complete_session(session_id, store)


async def handle_list_sessions(
    status_filter: str, project_id: str, run_type_filter: str = "all"
) -> dict:
    store = await _init_store(project_id)
    return await _list_sessions(status_filter, store, run_type_filter)
