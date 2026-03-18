# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Models for glossary service."""

from app.services.glossary.models.glossary_artifact import (
    GlossaryArtifact,
    ExplainGlossaryArtifactRequest,
    GlossaryArtifactDescription,
    GetGlossaryArtifactsForAssetRequest,
)

from app.services.glossary.models.csv_import import (
    CSVRowError,
    GlossaryTermCSVRow,
    CategoryCSVRow,
    CSVImportRequest,
    CSVImportResult,
    CSVSchemaInfo,
)

__all__ = [
    # Glossary artifact models
    "GlossaryArtifact",
    "ExplainGlossaryArtifactRequest",
    "GlossaryArtifactDescription",
    "GetGlossaryArtifactsForAssetRequest",
    # CSV import models
    "CSVRowError",
    "GlossaryTermCSVRow",
    "CategoryCSVRow",
    "CSVImportRequest",
    "CSVImportResult",
    "CSVSchemaInfo",
]