# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from app.shared.ui_message.ui_agentic_utils import CardComponent

# Strategy interface
class UIMessageStrategy(ABC):
    @abstractmethod
    def add_table_ui_message(self, tool_name: str, formatted_data: List[Dict], title: str) -> None:
        pass
    
    @abstractmethod
    def add_card_ui_message(self, tool_name: str, card_component: 'CardComponent') -> None:
        pass
    
    @abstractmethod
    def add_carousel_ui_message(self, tool_name: str, card_components: List['CardComponent']) -> None:
        pass

    @abstractmethod
    def add_text_ui_message(self, tool_name: str, text: str) -> None:
        pass

    @abstractmethod
    def add_text_message_as_error_msg(self, code: str, tool_name: str) -> None:
        pass

    @abstractmethod
    def extend_url_with_context(self, url: str) -> str:
        pass

    @abstractmethod
    def create_markdown_code_snippet(self, code: str, language: str) -> str:
        pass

    @abstractmethod
    def create_markdown_link(self, url: str, text: Optional[str] = None) -> str:
        pass

    @abstractmethod
    def create_markdown_table(self, data: list) -> str | None:
        pass

    @abstractmethod
    def send_table_selector_msg(self, tool_name: str, data: list, formatted_data: list, title: str, description: str | None = None, unique_keys=None) -> list | None:
        pass