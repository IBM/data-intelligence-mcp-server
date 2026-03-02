# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Optional


def add_custom_message(data: dict) -> None:
    pass    # default implementation used by mcp which does nothing

def get_ui_context() -> Optional[str]:
    return None   # default implementation used by mcp which doesn't have a UI context