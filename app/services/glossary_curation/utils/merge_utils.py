# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Merge and transform helpers for glossary curation complete_session."""

from app.services.glossary_curation.models.session import CurationMode
from app.services.glossary_curation.utils.curation_utils import _ARTIFACT_KEY_COL


def _apply_curated_fields(
    row: dict, curated_term: dict | None, curated_fieldnames: list[str]
) -> dict:
    merged = dict(row)
    if curated_term:
        for field in curated_fieldnames:
            if field in curated_term:
                merged[field] = curated_term[field]
    return merged


def process_mode_response(
    original_rows: list[dict],
    curated_terms: list[dict],
    mode: str,
    curated_fieldnames: list[str],
) -> tuple[list[dict], list[dict]]:
    """Merge curated field values back into original rows and apply mode-specific transforms.

    Returns (final_terms, final_rows) where final_terms contains only rows with an
    artifact key, and final_rows is the full set suitable for CSV import.
    """
    original_terms = [row for row in original_rows if row.get(_ARTIFACT_KEY_COL, "")]
    original_terms_map = {t[_ARTIFACT_KEY_COL]: t for t in original_terms}

    if "Name" in curated_fieldnames:
        curated_terms = _ensure_unique_names_per_category(
            curated_terms, original_terms_map
        )

    curated_terms_map = {t[_ARTIFACT_KEY_COL]: t for t in curated_terms}
    final_terms = []
    final_rows = []
    is_classification = mode == CurationMode.classification.value

    for row in original_rows:
        key = row.get(_ARTIFACT_KEY_COL, "")
        if key:
            curated_term = curated_terms_map.get(key)
            if curated_term is None:
                # Term was not curated (e.g. chunk was blocked) — exclude to prevent creating draft terms
                continue
            merged = _apply_curated_fields(row, curated_term, curated_fieldnames)
            if is_classification and not (merged.get("Classifications") or "").strip():
                continue
            final_terms.append(merged)
            final_rows.append(merged)
        elif not is_classification:
            # Blank-key continuation rows carry multi-value relationship fields but no
            # Name/Description to curate — exclude them from definition/translation imports
            continue
        else:
            # Blank-key continuation rows carry extra multi-value relationship fields
            # (Part Of Terms, Type Of Terms, Related Terms, Tags, etc.).  Always
            # include them in final_rows so those values survive into the import CSV.
            # They must never go into final_terms (the classification result list).
            final_rows.append(row)

    return final_terms, final_rows


def _ensure_unique_names_per_category(
    curated_terms: list[dict],
    original_terms_map: dict[str, dict],
) -> list[dict]:
    """Disambiguate curated terms whose ``Name`` values collide within the same category.

    A collision is defined as two or more terms in the **same category** sharing
    the same normalised (case-folded, stripped) new name.  The same name appearing
    in different categories is not a collision and is left untouched.

    When a collision is detected every affected term has its original name appended
    in parentheses so the data steward can distinguish them.

    Args:
        curated_terms: Terms produced by the curation step, each containing
            ``_ARTIFACT_KEY_COL`` and ``"Name"``.
        original_terms_map: Mapping of artifact_id → original full row, used to
            read the pre-curation name and the ``"Category"`` the term belongs to.

    Returns:
        The same list with intra-category duplicate names suffixed with the
        original term name in parentheses.  All other terms are returned unchanged.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for term in curated_terms:
        category = original_terms_map.get(term[_ARTIFACT_KEY_COL], {}).get(
            "Category", ""
        )
        key = (category.strip(), term["Name"].lower().strip())
        groups.setdefault(key, []).append(term)

    if all(len(group) == 1 for group in groups.values()):
        return curated_terms

    result = []
    for group in groups.values():
        if len(group) > 1:
            for term in group:
                original_name = original_terms_map[term[_ARTIFACT_KEY_COL]]["Name"]
                result.append({**term, "Name": f"{term['Name']} ({original_name})"})
        else:
            result += group

    return result
