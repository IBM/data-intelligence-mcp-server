# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Shared enums and config model for glossary curation."""

from enum import Enum  # noqa: I001 # Baseline
from typing import Optional
from pydantic import BaseModel, Field


class CurationMode(str, Enum):  # noqa: UP042 # Baseline
    translation = "translation"
    classification = "classification"
    definition = "definition"


class DefinitionScope(str, Enum):  # noqa: UP042 # Baseline
    all = "all"
    blanks_only = "blanks_only"


class RunType(str, Enum):  # noqa: UP042 # Baseline
    preview = "preview"
    full = "full"


class CurationConfig(BaseModel):
    chunk_size: int = Field(default=50, ge=1)
    target_language: Optional[str] = None  # noqa: UP045 # Baseline
    definition_scope: DefinitionScope = Field(default=DefinitionScope.all)
    definition_prompt: Optional[str] = None  # noqa: UP045 # Baseline
    classification_prompt: Optional[str] = None  # noqa: UP045 # Baseline
    translation_prompt: Optional[str] = None  # noqa: UP045 # Baseline
    artifact_ids: Optional[list[str]] = None  # noqa: UP045 # Baseline


class StartSessionParams(BaseModel):
    """Groups all start_session-specific parameters to keep the tool signature compact.

    category_identifier must be supplied with either a category UUID or category name —
    names will be resolved to an ID automatically.
    """

    category_identifier: str = Field(
        default="",
        description="UUID or name of the category containing terms to curate.",
    )
    mode: str
    chunk_size: int = Field(default=50, ge=1)
    target_language: Optional[str] = None  # noqa: UP045 # Baseline
    definition_scope: str = "all"
    definition_prompt: Optional[str] = None  # noqa: UP045 # Baseline
    classification_prompt: Optional[str] = None  # noqa: UP045 # Baseline
    translation_prompt: Optional[str] = None  # noqa: UP045 # Baseline
    artifact_ids: Optional[list[str]] = None  # noqa: UP045 # Baseline
    run_type: str = RunType.preview.value


class ClassificationValidation(BaseModel):
    """Summary of invalid classification rows removed during complete_session."""

    invalid_rows_removed: Optional[int] = None  # noqa: UP045 # Baseline
    invalid_rows: Optional[list[dict]] = None  # noqa: UP045 # Baseline
    available_classifications: Optional[set[str]] = None  # noqa: UP045 # Baseline


class CompleteSessionOutcome(BaseModel):
    """Optional response fields for _build_complete_session_response."""

    classification_validation: Optional[ClassificationValidation] = None  # noqa: UP045 # Baseline
    comment_warning: Optional[str] = None  # noqa: UP045 # Baseline
