# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Dynamic skill loading utilities.

Provides helpers for loading SKILL.md instruction files from the installed
``skills`` package.  Works in both editable (``pip install -e .``) and
production (``pip install``) environments because the ``skills`` directory is
declared as a package with ``**/*`` data in ``pyproject.toml`` and is therefore
resolved via ``importlib.resources``.

Key Components:
    - load_skill_text: Load a skill's SKILL.md file by name.
    - log_skill_injected: Emit a log entry when skill text is added to LLM context.
    - BUSINESS_TERM_SKILL_TEXT: Cached text for the ``business-term-evaluation`` skill.
    - DATA_CLASS_SKILL_TEXT: Cached text for the ``data-class-evaluation`` skill.
"""

import importlib.resources as _resources
from pathlib import Path
from typing import Optional

from app.shared.logging import LOGGER


def _skill_file_path(skill_name: str) -> Path:
    """Return the resolved :class:`Path` to ``skills/<skill_name>/SKILL.md``.

    Uses ``importlib.resources`` so the location is correct whether the package
    is installed normally, in editable mode, or run directly from source.
    """
    traversable = _resources.files("skills").joinpath(skill_name).joinpath("SKILL.md")
    # ``as_file`` materialises zip-packaged resources to a real path when needed.
    # For directory installs the context manager is a no-op and returns the path directly.
    with _resources.as_file(traversable) as path:
        return Path(path)


def load_skill_text(skill_name: str) -> Optional[str]:
    """Load a skill's SKILL.md text from the installed ``skills`` package.

    Args:
        skill_name: Directory name of the skill under the ``skills/`` package
            (e.g. ``"business-term-evaluation"``).

    Returns:
        The full text content of the skill file, or ``None`` if the file is
        missing or cannot be read.
    """
    try:
        skill_path = _skill_file_path(skill_name)
    except Exception as exc:
        LOGGER.warning("Could not resolve skill path for '%s': %s", skill_name, exc)
        return None

    LOGGER.info("Loading skill '%s' from resolved path: %s", skill_name, skill_path)
    try:
        text = skill_path.read_text(encoding="utf-8")
        LOGGER.info("Skill '%s' loaded successfully (%d chars)", skill_name, len(text))
        return text
    except FileNotFoundError:
        LOGGER.warning("Skill file not found: %s", skill_path)
        return None
    except OSError as exc:
        LOGGER.warning("Could not read skill file %s: %s", skill_path, exc)
        return None


def log_skill_injected(skill_name: str) -> None:
    """Log that a skill has been injected into the LLM context.

    Args:
        skill_name: Directory name of the skill (e.g. ``"business-term-evaluation"``).
    """
    try:
        skill_path = _skill_file_path(skill_name)
    except Exception:
        skill_path = Path("<unresolved>")

    LOGGER.info(
        "Skill injected into LLM context: name='%s' path='%s'",
        skill_name,
        skill_path,
    )


# ---------------------------------------------------------------------------
# Module-level cache — loaded once at import time so callers pay zero
# disk I/O on every request.
# ---------------------------------------------------------------------------

BUSINESS_TERM_SKILL_TEXT: Optional[str] = load_skill_text("business-term-evaluation")
DATA_CLASS_SKILL_TEXT: Optional[str] = load_skill_text("data-class-evaluation")
