# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Single MCP tool for parallel sub-agent glossary curation.

One tool — glossary_curator — dispatches across six operations:

  start_session   (orchestrator) extract terms, partition into chunks, return lightweight chunk metadata
  get_chunk_prompt(sub-agent)    fetch the full spawn prompt for a single chunk
  submit_chunk    (sub-agent)    save curated CSV for one chunk
  session_status  (orchestrator) poll progress; returns pending_detail and respawn_instruction
  complete_session(orchestrator) merge all chunks, import into catalog
  list_sessions   (user)         list all sessions with status
"""

from typing import Annotated, Optional  # noqa: I001 # Baseline

from fastmcp import Context
from pydantic import Field

from app.core.registry import service_registry
from app.services.glossary_curation.models.session import StartSessionParams
from app.services.glossary_curation.utils.glossary_curator_utils import (
    handle_complete_session,
    handle_get_chunk_prompt,
    handle_list_sessions,
    handle_session_status,
    handle_start_session,
    handle_submit_chunk,
)
from app.services.tool_utils import find_project_id
from app.shared.utils.helpers import confirm_uuid
from app.shared.logging import LOGGER, auto_context


@service_registry.tool(
    name="glossary_curator",
    annotations={
        "destructiveHint": True,
        "title": "Curate Large Glossary Term Sets via Parallel Sub-Agents",
    },
    description="""Curate, define, enrich, translate, and classify IKC glossary terms at scale via parallel sub-agents.

Use this tool when a user wants to:
- generate or improve IKC glossary term definitions
- translate glossary term names and definitions into another language
- classify glossary terms by a data privacy regulation (e.g. GDPR, CCPA)
- check the status of an ongoing curation session
- complete or finalise a curation session

IMPORTANT: If no curate-glossary skill is active, this description is the complete guide — do not look for, read, or recreate a SKILL file. A missing or deleted SKILL file is expected on this path. If a curate-glossary skill IS active, follow the skill instructions instead of this description.

## Run sequence — one question per turn, wait for the answer before asking the next
1. Ask: "Which category would you like to curate?" Call list_glossary_categories. Resolve to category_identifier. Confirm with user. STOP — wait for answer.
2. Ask: "Which project?" Call list_containers. Resolve to project_identifier. Confirm with user. NEVER skip this step even if the user provided a category — project_identifier is always required. STOP — wait for answer.
3. Ask: "Which mode: definition, translation, or classification?" STOP — wait for answer.
4. Ask each mode param as a separate question (see Mode params below). Ask one param at a time. STOP after each question — wait for the answer before asking the next. Do not call start_session until every required mode param is collected.
5. Recommended: call start_session run_type='preview'. Show chunk 0 result. Ask user to confirm before full run.
6. Call start_session run_type='full'. Poll session_status until status=ready_for_review.
7. Call complete_session. DESTRUCTIVE — imports directly into the catalog.

One tool, six operations — set 'operation' to select:

**start_session** — extract terms from a category and partition into chunks.
  Required: project_identifier (ALWAYS ask the user for the project name if not already known — never assume or skip),
            start.category_identifier (UUID or category name),
            start.mode ('translation' | 'classification' | 'definition'),
            start.<mode>_prompt — the curation instruction for the subagents (see Mode params below for the required field name and preset text per mode)
  Optional: start.run_type ('preview'|'full', default 'preview') — preview: chunk 0 sample only; full: all chunks + enables complete_session
  After a preview completes: display the curated content returned in the response to the user before asking whether to proceed with a full run.

**get_chunk_prompt** — (sub-agent) fetch the full prompt for one chunk.
  Required: project_identifier, session_id, chunk_index

**submit_chunk** — (sub-agent) save curated CSV. Idempotent.
  Required: project_identifier, session_id, chunk_index, sub_agent_id, curated_terms_csv

**session_status** — poll progress; returns completed_chunks and pending_chunks.
  Required: project_identifier, session_id
  Optional: chunk_index — returns diagnostic detail for that chunk (pre_curated_rows, post_curated_rows, respawns)
  Note: when all chunks complete on a full run, status transitions to ready_for_review and a review CSV is produced.

**complete_session** — import curated terms. Full sessions only (ready_for_review required).
  Required: project_identifier, session_id

**list_sessions** — list all sessions with status and progress.
  Required: project_identifier
  Optional: status_filter ('all'|'in_progress'|'completed'|'import_failed'|'completed_with_blocked_chunks'|'stale_session', default 'all')
            run_type_filter ('all'|'preview'|'full', default 'all')

## Mode params — assemble before calling start_session

**definition**
  start.definition_scope (required) — ALWAYS ask the user explicitly: "Should I write definitions for all terms, or only terms with blank descriptions?" Set to 'all' or 'blanks_only' based on their answer. Do not assume or default — wait for the user's answer.
  start.definition_prompt (required) — set to:
  "Write a new Description for each row based solely on the term Name and Part Of Terms when populated.
  Ignore any existing content in the Description column entirely.
  Do not begin a definition with the term name or a verb — open with a noun phrase.
  Write exactly 1 sentence per term. State the core meaning directly — no use cases, no qualifications unless essential to distinguish the term from something similar.
  Keep all other columns unchanged."

**translation**
  start.target_language (required) — ask the user which language to translate into.
  start.translation_prompt (required) — set to (replace {target_language}):
  "Translate the Name and Description columns of each row into {target_language}.
  Detect the source language of each row independently — the glossary may contain a mix of languages.
  If a row is already written in {target_language}, leave it unchanged.
  Every translated field must be written ENTIRELY in {target_language} — no bilingual output.
  If the Description field is empty in the source row, leave it empty — do not generate or invent a description.
  Translate the full meaning; do not shorten, summarize, or omit sentences.
  Preserve technical terms and proper nouns unchanged.
  Keep Artifact Type, Category, and all other columns unchanged."

**classification**
  Step 1: Ask: "Which regulation would you like to classify under? (e.g. GDPR, CCPA)" STOP — wait for answer.
  Step 2: Ask: "Which IKC label names should be used? The defaults are: Personal Information, Sensitive Personal Information, Unclassified. Please confirm these or provide your own." STOP — wait for the user to explicitly confirm or provide custom labels before proceeding.
  Step 3: Assemble start.classification_prompt using the confirmed {regulation} and {label_list}:
  "Classify each term under {regulation} by updating its Classifications column.
  Use the term Name, Description, and Part Of Terms together.
  Choose the best-fit label from: {label_list}.
  Use ONLY the exact label strings listed. Leave Classifications empty if no label fits.
  Keep all other columns unchanged."
  After the session, display: AI-generated classifications — validate with compliance/legal before use.""",
    tags={"metadata_management_and_governance"},
)
@auto_context
async def glossary_curator(  # noqa: PLR0911, PLR0913 # Baseline
    operation: Annotated[
        str,
        Field(
            description="One of: start_session, get_chunk_prompt, submit_chunk, session_status, complete_session, list_sessions"
        ),
    ],
    project_identifier: Annotated[
        str, Field(description="UUID or name of the project used for session storage.")
    ] = "",
    start: Annotated[
        Optional[StartSessionParams],  # noqa: UP045 # Baseline
        Field(
            description="Groups all start_session-specific parameters to keep the tool signature compact.\n\ncategory_identifier must be supplied with either a category UUID or category name — names will be resolved to an ID automatically."
        ),
    ] = None,
    session_id: Annotated[
        Optional[str],  # noqa: UP045 # Baseline
        Field(
            description="Session ID returned by start_session. Required for get_chunk_prompt, submit_chunk, session_status, and complete_session operations."
        ),
    ] = None,
    chunk_index: Annotated[
        Optional[int],  # noqa: UP045 # Baseline
        Field(
            description="Zero-based index of the chunk to operate on. Required for get_chunk_prompt and submit_chunk operations."
        ),
    ] = None,
    sub_agent_id: Annotated[
        Optional[str],  # noqa: UP045 # Baseline
        Field(
            description="Identifier of the sub-agent submitting the chunk. Required for submit_chunk."
        ),
    ] = None,
    curated_terms_csv: Annotated[
        Optional[str],  # noqa: UP045 # Baseline
        Field(
            description="CSV content produced by the sub-agent for one chunk. Required for submit_chunk."
        ),
    ] = None,
    status_filter: Annotated[
        str,
        Field(
            description="Filter for list_sessions. One of: 'all' (default), 'in_progress', 'completed', 'import_failed', 'completed_with_blocked_chunks', 'stale_session'."
        ),
    ] = "all",
    run_type_filter: Annotated[
        str,
        Field(
            description="Filter for list_sessions by run type. One of: 'all' (default), 'preview', 'full'."
        ),
    ] = "all",
    ctx: Optional[Context] = None,  # noqa: UP045 # Baseline
) -> dict:
    LOGGER.info(f"glossary_curator: operation={operation}")

    project_id = await confirm_uuid(project_identifier, find_project_id)

    if operation == "start_session":
        return await handle_start_session(start, project_id)
    if operation == "submit_chunk":
        return await handle_submit_chunk(
            session_id, chunk_index, sub_agent_id, curated_terms_csv, project_id
        )
    if operation == "session_status":
        return await handle_session_status(
            session_id, project_id, chunk_index=chunk_index
        )
    if operation == "get_chunk_prompt":
        return await handle_get_chunk_prompt(session_id, chunk_index, project_id)
    if operation == "complete_session":
        return await handle_complete_session(session_id, project_id)
    if operation == "list_sessions":
        return await handle_list_sessions(status_filter, project_id, run_type_filter)

    return {
        "status": "error",
        "error_type": "unknown_operation",
        "message": (
            f"Unknown operation '{operation}'. Valid: start_session, get_chunk_prompt, "
            f"submit_chunk, session_status, complete_session, list_sessions"
        ),
    }
