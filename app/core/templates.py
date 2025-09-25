# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Jinja environment helper (cached per base directory)."""

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _key(base_dir: str) -> str:
    return str(Path(base_dir).resolve())


@lru_cache(maxsize=8)
def _env(base_dir_key: str) -> Environment:
    return Environment(
        loader=FileSystemLoader(base_dir_key),
        autoescape=select_autoescape(enabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(base_dir: str, rel_path: str, **vars) -> str:
    base = _key(base_dir)
    env = _env(base)
    return env.get_template(rel_path).render(**vars)
