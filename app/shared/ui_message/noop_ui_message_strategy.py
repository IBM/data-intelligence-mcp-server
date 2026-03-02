# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Dict, Optional
from app.shared.ui_message.ui_agentic_utils import CardComponent
from app.shared.ui_message.ui_message_strategy import UIMessageStrategy

class NoopUIMessageStrategy(UIMessageStrategy):
    def add_table_ui_message(self, tool_name: str, formatted_data: List[Dict], title: str) -> None:
        pass  # No-op, does nothing

    def add_card_ui_message(self, tool_name: str, card_component: 'CardComponent') -> None:
        pass  # No-op, does nothing

    def add_carousel_ui_message(self, tool_name: str, card_components: List['CardComponent']) -> None:
        pass  # No-op, does nothing

    def add_text_ui_message(self, tool_name: str, text: str) -> None:
        pass  # No-op, does nothing

    def add_text_message_as_error_msg(self, code: str, tool_name: str) -> None:
        pass # No-op, does nothing

    def extend_url_with_context(self, url: str) -> str:
        return url  # No-op, returns the URL unchanged

    def create_markdown_code_snippet(self, code: str, language: str) -> str:
        return code  # No-op, returns the code unchanged

    def create_markdown_link(self, url: str, text: Optional[str] = None) -> str:
        return url  # No-op, returns the URL unchanged

    def create_markdown_table(self, data: list) -> str | None:
        return None  # No-op, returns None

    def send_table_selector_msg(self, tool_name: str, data: list, formatted_data: list, title: str, description: str | None = None, unique_keys=None) -> list | None:
        return None  # No-op, returns None
