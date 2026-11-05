# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""CSV and data-processing helpers for glossary curation."""

import csv
import io
import uuid
from datetime import UTC, datetime

from app.shared.utils.helpers import is_uuid_bool

_ARTIFACT_TYPE_COL = "Artifact Type"
_ARTIFACT_KEY_COL = "Artifact ID"
_NAME_COL = "Name"
_CATEGORY_COL = "Category"
_PART_OF_TERMS_COL = "Part Of Terms"

# Identity columns required by IKC to locate and match existing terms on import.
_IMPORT_IDENTITY_COLS = [
    _ARTIFACT_KEY_COL,
    _ARTIFACT_TYPE_COL,
    _NAME_COL,
    _CATEGORY_COL,
]

TRANSLATION_MODE_PAYLOAD_COLS = [
    _ARTIFACT_KEY_COL,
    "Name",
    "Description",
    _PART_OF_TERMS_COL,
]
DEFINITION_MODE_PAYLOAD_COLS = [
    _ARTIFACT_KEY_COL,
    "Name",
    "Description",
    _PART_OF_TERMS_COL,
]
CLASSIFICATION_MODE_PAYLOAD_COLS = [
    _ARTIFACT_KEY_COL,
    "Name",
    "Description",
    "Tags",
    "Classifications",
    _PART_OF_TERMS_COL,
]

TRANSLATION_MODE_CURATION_COLS = ["Name", "Description"]
DEFINITION_MODE_CURATION_COLS = ["Description"]
CLASSIFICATION_MODE_CURATION_COLS = ["Classifications"]

# This prevents duplicate columns for Name
TRANSLATION_MODE_IMPORT_COLS = _IMPORT_IDENTITY_COLS + [
    c for c in TRANSLATION_MODE_CURATION_COLS if c not in _IMPORT_IDENTITY_COLS
]
DEFINITION_MODE_IMPORT_COLS = _IMPORT_IDENTITY_COLS + DEFINITION_MODE_CURATION_COLS
CLASSIFICATION_MODE_IMPORT_COLS = (
    _IMPORT_IDENTITY_COLS + CLASSIFICATION_MODE_CURATION_COLS
)

# curation_pre_* snapshot column names — exact IKC column name with prefix.
CURATION_PRE_NAME = "curation_pre_Name"
CURATION_PRE_DESCRIPTION = "curation_pre_Description"
CURATION_PRE_PART_OF_TERMS = "curation_pre_Part Of Terms"
CURATION_PRE_CLASSIFICATIONS = "curation_pre_Classifications"
CURATION_PRE_TAGS = "curation_pre_Tags"

# Per-mode review fieldnames: import cols first, then curation_pre_* snapshot cols.
TRANSLATION_MODE_REVIEW_COLS = TRANSLATION_MODE_IMPORT_COLS + [  # noqa: RUF005 # Baseline
    CURATION_PRE_NAME,
    CURATION_PRE_DESCRIPTION,
    CURATION_PRE_PART_OF_TERMS,
]
DEFINITION_MODE_REVIEW_COLS = DEFINITION_MODE_IMPORT_COLS + [  # noqa: RUF005 # Baseline
    CURATION_PRE_DESCRIPTION,
    CURATION_PRE_PART_OF_TERMS,
]
CLASSIFICATION_MODE_REVIEW_COLS = CLASSIFICATION_MODE_IMPORT_COLS + [  # noqa: RUF005 # Baseline
    CURATION_PRE_CLASSIFICATIONS,
    CURATION_PRE_PART_OF_TERMS,
    CURATION_PRE_TAGS,
]


def _row_key(row: dict) -> str:
    """Return the best available unique key for a term row.

    IKC exports always include 'Name' but may omit 'Artifact ID' depending on
    the export API version or instance configuration. Fall back to Name when
    Artifact ID is absent or empty so all merge/grouping logic works correctly.
    """
    artifact_id = (row.get(_ARTIFACT_KEY_COL) or "").strip()
    return artifact_id if artifact_id else (row.get(_NAME_COL) or "").strip()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


_MODE_DISPLAY_NAMES: dict[str, str] = {
    "definition": "definitions",
    "translation": "translations",
    "classification": "classifications",
}


def _new_session_id(mode: str) -> str:
    date = datetime.now(UTC).strftime("%Y%m%d")
    display = _MODE_DISPLAY_NAMES.get(mode, mode)
    return f"{date}-{uuid.uuid4().hex[:8]}-curate-term-{display}"


def _new_preview_session_id(mode: str) -> str:
    date = datetime.now(UTC).strftime("%Y%m%d")
    display = _MODE_DISPLAY_NAMES.get(mode, mode)
    return f"preview-{date}-{uuid.uuid4().hex[:8]}-curate-term-{display}"


_OVERFLOW_KEY = "__overflow__"


def _parse_csv(content: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(content), restkey=_OVERFLOW_KEY)
    fieldnames = list(reader.fieldnames or [])
    rows: list[dict] = []
    for row in reader:
        overflow = row.pop(_OVERFLOW_KEY, None)
        if overflow and fieldnames:
            last_field = fieldnames[-1]
            if last_field == _PART_OF_TERMS_COL and "Description" in fieldnames:
                desc_idx = fieldnames.index("Description")
                trailing_cols = fieldnames[desc_idx + 1 :]
                all_tokens = (
                    [row.get("Description", "")]
                    + [row.pop(col, "") for col in trailing_cols]
                    + list(overflow)
                )
                for col in reversed(trailing_cols):
                    row[col] = all_tokens.pop()
                row["Description"] = ",".join(all_tokens)
            else:
                row[last_field] = row.get(last_field, "") + "," + ",".join(overflow)
        rows.append(row)
    return fieldnames, rows


def _to_csv(fieldnames: list[str], rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
        quoting=csv.QUOTE_ALL,
    )
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _progress(done: int, total: int) -> str:
    pct = int(done / total * 100) if total else 0
    return f"{done}/{total} chunks ({pct}%)"


def get_mode_payload_fieldnames(mode: str) -> list[str]:
    mode_dict = {
        "translation": TRANSLATION_MODE_PAYLOAD_COLS,
        "classification": CLASSIFICATION_MODE_PAYLOAD_COLS,
        "definition": DEFINITION_MODE_PAYLOAD_COLS,
    }
    return mode_dict.get(mode, [])


def get_mode_curation_fieldnames(mode: str) -> list[str]:
    mode_dict = {
        "translation": TRANSLATION_MODE_CURATION_COLS,
        "classification": CLASSIFICATION_MODE_CURATION_COLS,
        "definition": DEFINITION_MODE_CURATION_COLS,
    }
    return mode_dict.get(mode, [])


def get_mode_import_fieldnames(mode: str) -> list[str]:
    """Return the minimal column set for the import CSV for the given mode.

    Only identity columns and the fields the curation tool intentionally writes
    are included. Relationship columns (Part Of Terms, Type Of Terms, Related
    Terms, etc.) are deliberately omitted so IKC leaves them untouched under
    merge_option="specified".
    """
    mode_dict = {
        "translation": TRANSLATION_MODE_IMPORT_COLS,
        "definition": DEFINITION_MODE_IMPORT_COLS,
        "classification": CLASSIFICATION_MODE_IMPORT_COLS,
    }
    return mode_dict.get(mode, [])


def get_mode_review_fieldnames(mode: str) -> list[str]:
    """Return the full review column set for the after CSV for the given mode.

    Includes import columns plus ``curation_pre_*`` snapshot columns so
    reviewers can compare pre- and post-curation values in one CSV.
    Falls back to import fieldnames when no review set is defined for a mode.
    """
    mode_dict = {
        "translation": TRANSLATION_MODE_REVIEW_COLS,
        "definition": DEFINITION_MODE_REVIEW_COLS,
        "classification": CLASSIFICATION_MODE_REVIEW_COLS,
    }
    return mode_dict.get(mode, get_mode_import_fieldnames(mode))


def create_payload_terms(
    all_rows: list[dict], mode: str
) -> tuple[list[dict], list[str]]:
    mode_fieldnames = get_mode_payload_fieldnames(mode)
    id_part_of_name_map = get_part_of_terms_map(all_rows)

    payload_term_rows = []
    for row in all_rows:
        # Use _row_key so terms without an Artifact ID (name-only) are not silently dropped.
        row_key = _row_key(row)

        if row_key in id_part_of_name_map:
            payload_term = {
                fieldname: row.get(fieldname, "") for fieldname in mode_fieldnames
            }
            payload_term[_PART_OF_TERMS_COL] = " | ".join(id_part_of_name_map[row_key])
            payload_term_rows.append(payload_term)

    return payload_term_rows, mode_fieldnames


def _build_raw_part_of_map(all_rows: list[dict]) -> dict[str, list[str]]:
    """Collect Part Of Terms name-path values keyed by each term's row key.

    IKC exports relationship columns (Part Of Terms, Type Of Terms, Related
    Terms) as ``CategoryName >> TermName`` name-path strings, not artifact IDs.
    Multi-value terms are encoded as continuation rows (blank Artifact ID / Name)
    with the additional value on each continuation row.  This function handles
    both the main row and any following continuation rows.
    """
    part_of_map: dict[str, list[str]] = {}
    current_row_key: str | None = None

    for row in all_rows:
        row_key = _row_key(row)
        part_of_terms = row.get(_PART_OF_TERMS_COL, "")

        if not row_key and (not current_row_key or not part_of_terms):
            continue
        if row_key:
            current_row_key = row_key
            part_of_map[current_row_key] = []
        if part_of_terms and current_row_key is not None:
            part_of_map[current_row_key].append(part_of_terms)

    return part_of_map


def get_part_of_terms_map(all_rows: list[dict]) -> dict[str, list[str]]:
    return _build_raw_part_of_map(all_rows)


def _resolve_token(token: str, term_name_map: dict[str, str]) -> tuple[str, bool]:
    """Return (resolved_value, was_unresolved) for a single pipe-delimited token.

    A token that is not a UUID is returned as-is with was_unresolved=False.
    A UUID token resolved via term_name_map is returned by name with was_unresolved=False.
    A UUID token absent from term_name_map is returned as-is with was_unresolved=True.
    """
    if not is_uuid_bool(token):
        return token, False
    name = term_name_map.get(token)
    if name is None:
        return token, True
    return name, False


def _build_term_name_map(all_rows: list[dict]) -> dict[str, str]:
    return {
        row[_ARTIFACT_KEY_COL]: row[_NAME_COL]
        for row in all_rows
        if row.get(_ARTIFACT_KEY_COL) and row.get(_NAME_COL)
    }


def resolve_ids_in_rows(all_rows: list[dict]) -> tuple[list[dict], set[str]]:
    """Return a copy of *all_rows* with UUID values resolved to human-readable names.

    Resolves ``Part Of Terms``: UUID → term name, using *all_rows* itself as the lookup.
    Values that are not UUIDs or cannot be resolved are left unchanged.

    Args:
        all_rows: Glossary term rows from the IKC export CSV.

    Returns:
        Tuple of (resolved_rows, unresolved_uuids) where unresolved_uuids contains
        every UUID token that was looked up but not found in the term name map.
    """
    term_name_map = _build_term_name_map(all_rows)

    resolved_rows: list[dict] = []
    unresolved_uuids: set[str] = set()
    for row in all_rows:
        new_row = dict(row)

        part_of_val = (new_row.get(_PART_OF_TERMS_COL) or "").strip()
        if part_of_val:
            tokens = [t.strip() for t in part_of_val.split(" | ")]
            resolved_tokens = []
            for t in tokens:
                resolved_token, was_unresolved = _resolve_token(t, term_name_map)
                if was_unresolved:
                    unresolved_uuids.add(t)
                resolved_tokens.append(resolved_token)
            new_row[_PART_OF_TERMS_COL] = " | ".join(resolved_tokens)

        resolved_rows.append(new_row)
    return resolved_rows, unresolved_uuids
