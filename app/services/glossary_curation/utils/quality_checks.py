# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Row-level quality checks for curated glossary CSV chunks."""


def _definition_issues(name: str, description: str) -> list[dict]:
    """Return quality issues for a single row in definition mode."""
    if not description:
        return [{"name": name, "problem": "Description is empty"}]
    if description.lower() == name.lower():
        return [{"name": name, "problem": "Description just repeats the term name"}]
    if len(description.split()) < 3:  # noqa: PLR2004 # Baseline
        return [{"name": name, "problem": f"Description too short: '{description}'"}]
    return []


def _translation_issues(name: str) -> list[dict]:
    """Return quality issues for a single row in translation mode."""
    issues = []
    if not name:
        issues.append({"name": name, "problem": "Name is empty after translation"})
    return issues


def quality_issues(rows: list[dict], mode: str) -> list[dict]:
    """Return row-level quality problems. Empty list means the CSV passed."""
    issues = []
    for row in rows:
        name = (row.get("Name") or "").strip()
        description = (row.get("Description") or "").strip()
        if mode == "definition":
            issues.extend(_definition_issues(name, description))
        elif mode == "translation":
            issues.extend(_translation_issues(name))
    return issues
