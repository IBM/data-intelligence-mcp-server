# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Builds sub-agent spawn prompts for glossary curation sessions.

Each prompt embeds the mode-specific instruction and the slim CSV slice for
that chunk, so the sub-agent is fully self-contained.
"""

from app.services.glossary_curation.models.session import CurationMode, CurationConfig  # noqa: I001 # Baseline

_ARTIFACT_ID_GUARD = (
    "CRITICAL: Never modify the 'Artifact ID' column — it links each row back to the "
    "original term in the catalog and is required for correct updates."
)


def mode_instruction(mode: CurationMode, config: CurationConfig) -> str:  # noqa: RET503 # Baseline
    if mode == CurationMode.translation:
        # The assembled prompt comes from SKILL.md via config.translation_prompt.
        # Append the artifact ID guard unconditionally — it is tool-owned, not skill-owned.
        return f"{config.translation_prompt}\n{_ARTIFACT_ID_GUARD}"
    if mode == CurationMode.classification:
        # The assembled prompt comes from SKILL.md via config.classification_prompt.
        # Append the artifact ID guard unconditionally — it is tool-owned, not skill-owned.
        return f"{config.classification_prompt}\n{_ARTIFACT_ID_GUARD}"
    if mode == CurationMode.definition:
        # The assembled prompt comes from SKILL.md via config.definition_prompt.
        # Append the artifact ID guard unconditionally — it is tool-owned, not skill-owned.
        return f"{config.definition_prompt}\n{_ARTIFACT_ID_GUARD}"


def build_spawn_prompt(  # noqa: PLR0913 # Baseline
    session_id: str,
    chunk_index: int,
    mode: CurationMode,
    config: CurationConfig,
    terms_csv: str,
    terms_count: int,
) -> str:
    """Build a self-contained sub-agent spawn prompt.

    ``terms_csv`` must be the mode-specific slim CSV (Artifact ID + mode columns only).
    The full original columns are not sent to sub-agents; ``_complete_session``
    re-attaches them from before.csv via the merge-reattach pattern.
    """
    instruction = mode_instruction(mode, config)

    return (
        f"You are a {mode.value} sub-agent for glossary curation session '{session_id}'.\n\n"
        f"Your task:\n"
        f"{instruction}\n\n"
        f"Here are the {terms_count} terms (CSV):\n"
        f"{terms_csv}\n\n"
        f"Return the full curated CSV (keep the header row).\n"
        f"CSV FORMATTING RULES (mandatory — non-compliance causes data loss):\n"
        f"- Any field value that contains a comma or a newline MUST be enclosed in "
        f"double-quote characters per RFC 4180.\n"
        f'  Correct:   id,Term Name,"Represents the core amount, before fees."\n'
        f"  Incorrect: id,Term Name,Represents the core amount, before fees.\n"
        f'- To include a literal double-quote inside a quoted value, double it: ""\n'
        f"- Every row must have exactly as many fields as the header row.\n\n"
        f"If any `Part Of Terms` value is a UUID, do not use the `Part Of Terms` column to inform your curation for that row.\n"
        f"Then call glossary_curator with:\n"
        f'  operation: "submit_chunk"\n'
        f'  session_id: "{session_id}"\n'
        f"  chunk_index: {chunk_index}\n"
        f'  sub_agent_id: "sub-agent-chunk-{chunk_index:02d}"\n'
        f"  curated_terms_csv: [your curated CSV]\n\n"
        f"IMPORTANT: After submit_chunk succeeds, TERMINATE IMMEDIATELY.\n"
        f"Do NOT call complete_session. Do NOT suggest any review step or new task.\n"
        f"Do NOT produce any handoff message. The orchestrator handles everything after this."
    )
