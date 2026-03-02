# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Tools for glossary service."""

from app.services.glossary.tools.explain_glossary_artifact import (
    explain_glossary_artifact,
    wxo_explain_glossary_artifact,
)
from app.services.glossary.tools.get_glossary_artifacts_for_asset import (
    get_glossary_artifacts_for_asset,
    wxo_get_glossary_artifacts_for_asset,
)

__all__ = [
    "explain_glossary_artifact",
    "wxo_explain_glossary_artifact",
    "get_glossary_artifacts_for_asset",
    "wxo_get_glossary_artifacts_for_asset",
]