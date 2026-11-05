# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Staleness check models for glossary curation."""

from pydantic import BaseModel


class StalenessDiff(BaseModel):
    """A single field difference for a curated term."""

    artifact_id: str
    term_name: str
    field: str
    before_value: str
    after_value: str
    is_deleted: bool = False


class StalenessCheckResult(BaseModel):
    """Result of a staleness check."""

    is_stale: bool
    diffs: list[StalenessDiff]
    check_error: str | None = None
    message: str | None = None
