# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
"""Tiny importer: resolves a dotted path string to a Python object."""

import importlib


def import_obj(dotted: str):
    module, attr = dotted.rsplit(".", 1)
    mod = importlib.import_module(module)
    return getattr(mod, attr)
