# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
UI Message Context Module

This module implements the Strategy design pattern for handling UI messages in the application.
It provides a flexible way to switch between different UI message strategies at runtime.
"""

from typing import Dict, List, Optional
from app.shared.ui_message.noop_ui_message_strategy import NoopUIMessageStrategy
from app.shared.ui_message.ui_agentic_utils import CardComponent
from app.shared.ui_message.ui_message_strategy import UIMessageStrategy


class UIMessageContext:
    """
    Context class for managing UI message strategies using the Strategy pattern.
    
    This class acts as a context that delegates UI message operations to a concrete
    strategy implementation. It allows switching between different strategies at runtime,
    enabling flexible UI message handling based on the application's needs.
    
    Attributes:
        _strategy (UIMessageStrategy): The current strategy being used for UI messages.
    
    Available Strategies:
        - AgenticUIMessageStrategy: Sends UI messages directly to the UI (active mode)
        - NoopUIMessageStrategy: No-operation strategy that does nothing (passive mode)
    
    Example:
        >>> # Initialize with a no-op strategy (default)
        >>> context = UIMessageContext(NoopUIMessageStrategy())
        >>>
        >>> # Switch to agentic strategy when needed
        >>> context.set_strategy(AgenticUIMessageStrategy())
        >>>
        >>> # Add a table UI message
        >>> data = [{"name": "Asset1", "type": "Table"}, {"name": "Asset2", "type": "View"}]
        >>> context.add_table_ui_message("search_tool", data, "Search Results")
        >>>
        >>> # Add a card UI message
        >>> card = CardComponent(title="Data Product", description="Product details")
        >>> context.add_card_ui_message("product_tool", card)
        >>>
        >>> # Add a carousel UI message
        >>> cards = [card1, card2, card3]
        >>> context.add_carousel_ui_message("carousel_tool", cards)
    """
    
    def __init__(self, strategy: UIMessageStrategy):
        """
        Initialize the UIMessageContext with a specific strategy.
        
        Args:
            strategy (UIMessageStrategy): The initial strategy to use for UI messages.
                Can be AgenticUIMessageStrategy or NoopUIMessageStrategy.
        """
        self._strategy = strategy

    def set_strategy(self, strategy: UIMessageStrategy) -> None:
        """
        Change the current UI message strategy at runtime.
        
        This method allows dynamic switching between different strategies,
        enabling the application to adapt its UI message behavior based on
        context or configuration.
        
        Args:
            strategy (UIMessageStrategy): The new strategy to use for UI messages.
        
        Example:
            >>> context = UIMessageContext(NoopUIMessageStrategy())
            >>> # Later, switch to active messaging
            >>> context.set_strategy(AgenticUIMessageStrategy())
        """
        self._strategy = strategy

    def add_table_ui_message(self, tool_name: str, formatted_data: List[Dict], title: str) -> None:
        """
        Add a table UI message using the current strategy.
        
        Delegates the table message creation to the active strategy. The strategy
        determines whether the message is actually sent to the UI or ignored.
        
        Args:
            tool_name (str): The name of the tool generating the message.
            formatted_data (List[Dict]): A list of dictionaries containing the table data.
                Each dictionary represents a row with column names as keys.
            title (str): The title to display for the table.
        
        Example:
            >>> data = [
            ...     {"id": "1", "name": "Asset A", "type": "Table"},
            ...     {"id": "2", "name": "Asset B", "type": "View"}
            ... ]
            >>> context.add_table_ui_message("search_assets", data, "Found Assets")
        """
        self._strategy.add_table_ui_message(tool_name, formatted_data, title)

    def add_card_ui_message(self, tool_name: str, card_component: 'CardComponent') -> None:
        """
        Add a card UI message using the current strategy.
        
        Delegates the card message creation to the active strategy. Cards are typically
        used to display structured information in a visually appealing format.
        
        Args:
            tool_name (str): The name of the tool generating the message.
            card_component (CardComponent): A CardComponent object containing the card data,
                including title, description, and other card properties.
        
        Example:
            >>> from app.shared.ui_message.ui_agentic_utils import CardComponent
            >>> card = CardComponent(
            ...     title="Data Product",
            ...     description="A comprehensive data product",
            ...     metadata={"version": "1.0", "owner": "Data Team"}
            ... )
            >>> context.add_card_ui_message("data_product_tool", card)
        """
        self._strategy.add_card_ui_message(tool_name, card_component)

    def add_carousel_ui_message(self, tool_name: str, card_components: List['CardComponent']) -> None:
        """
        Add a carousel UI message using the current strategy.
        
        Delegates the carousel message creation to the active strategy. Carousels display
        multiple cards in a scrollable format, useful for showing collections of related items.
        
        Args:
            tool_name (str): The name of the tool generating the message.
            card_components (List[CardComponent]): A list of CardComponent objects to display
                in the carousel. Each card represents an item in the collection.
        
        Example:
            >>> cards = [
            ...     CardComponent(title="Product 1", description="First product"),
            ...     CardComponent(title="Product 2", description="Second product"),
            ...     CardComponent(title="Product 3", description="Third product")
            ... ]
            >>> context.add_carousel_ui_message("product_catalog", cards)
        """
        self._strategy.add_carousel_ui_message(tool_name, card_components)


    def add_text_ui_message(self, tool_name: str, text: str) -> None:
        """
        Add a text UI message using the current strategy.
        
        Delegates the text message creation to the active strategy. Text messages
        are simple string-based messages sent directly to the UI.
        
        Args:
            tool_name (str): The name of the tool generating the message.
            text (str): The text content to be displayed in the UI message.
        
        Example:
            >>> context.add_text_ui_message("validation_tool", "Validation completed successfully")
        """
        self._strategy.add_text_ui_message(tool_name, text)

    def add_text_message_as_error_msg(self, code: str, tool_name: str) -> None:
        """
        Add a text message as an error/debug message using the current strategy.
        
        Delegates the error message creation to the active strategy. This is typically
        used for sending debug information or error messages to the UI with special
        formatting or handling.
        
        Args:
            code (str): The text content to be sent as an error/debug message.
                Despite the parameter name, this can be any text content, not just code.
            tool_name (str): The name of the tool generating the error message.
        
        Example:
            >>> context.add_text_message_as_error_msg("Error: Connection failed", "connection_tool")
        """
        self._strategy.add_text_message_as_error_msg(code, tool_name)
    
    def extend_url_with_context(self, url: str) -> str:
        """
        Extend a URL with UI context parameters using the current strategy.
        
        Delegates URL extension to the active strategy. This typically adds context
        query parameters to URLs to maintain UI state across navigation.
        
        Args:
            url (str): The URL to extend with context parameters.
        
        Returns:
            str: The URL with context parameters added if applicable.
        
        Example:
            >>> original_url = "https://example.com/asset/123"
            >>> extended_url = context.extend_url_with_context(original_url)
            >>> # Returns: "https://example.com/asset/123?context=df"
        """
        return self._strategy.extend_url_with_context(url)

    def create_markdown_code_snippet(self, code: str, language: str) -> str:
        """
        Create a markdown-formatted code snippet using the current strategy.
        
        Delegates markdown code snippet creation to the active strategy. This formats
        code with proper markdown syntax highlighting for the specified language.
        
        Args:
            code (str): The code content to be formatted.
            language (str): The programming language for syntax highlighting (e.g., 'python', 'sql', 'json').
        
        Returns:
            str: A markdown-formatted code snippet with language-specific syntax highlighting.
        
        Example:
            >>> code = "SELECT * FROM users WHERE id = 1"
            >>> snippet = context.create_markdown_code_snippet(code, "sql")
            >>> # Returns: "```sql\\nSELECT * FROM users WHERE id = 1\\n```"
        """
        return self._strategy.create_markdown_code_snippet(code, language)

    def create_markdown_link(self, url: str, text: Optional[str] = None) -> str:
        """
        Create a markdown-formatted link using the current strategy.
        
        Delegates markdown link creation to the active strategy. This creates a properly
        formatted markdown link with optional display text and context parameters.
        
        Args:
            url (str): The URL for the link.
            text (Optional[str]): The text to display for the link. If None, uses the URL as text.
        
        Returns:
            str: A markdown-formatted link in the format [text](url).
        
        Example:
            >>> link = context.create_markdown_link("https://example.com/asset/123", "View Asset")
            >>> # Returns: "[View Asset](https://example.com/asset/123?context=df)"
        """
        return self._strategy.create_markdown_link(url, text)

    def create_markdown_table(self, data: list) -> str | None:
        """
        Create a markdown-formatted table using the current strategy.
        
        Delegates markdown table creation to the active strategy. This converts a list
        of dictionaries into a properly formatted markdown table.
        
        Args:
            data (list): A list of dictionaries containing the table data.
                Each dictionary represents a row with column names as keys.
        
        Returns:
            str | None: A markdown-formatted table string if data is provided, otherwise None.
        
        Example:
            >>> data = [
            ...     {"name": "Asset1", "type": "Table", "size": "100MB"},
            ...     {"name": "Asset2", "type": "View", "size": "50MB"}
            ... ]
            >>> table = context.create_markdown_table(data)
            >>> # Returns a markdown table with headers and rows
        """
        return self._strategy.create_markdown_table(data)

    def send_table_selector_msg(self, tool_name: str, data: list, formatted_data: list, title: str, description: str | None = None, unique_keys=None) -> list | None:
        """
        Adds a table UI message to the graph along with options to select

        This function sends message with table directly to the UI along with options to make selection from the table

        Args:
            tool_name (str): The name of the tool.
            data (list): orginal data
            formatted_data (list): A list of formatted data to be displayed in the table.
            title (str): The title of the table
            description(str):  The description of the table
            unique_keys:  Unique keys are used in formatting interrupt message.  It's good practice to specify some columns in the formatted data which will uniquely identify
                        a row.  Otherwise all the row elements will be passed to the interrupt message

        Returns:
            list | None: A list of selected items from the original data, or None if formatted_data is empty.
        """
        return self._strategy.send_table_selector_msg(tool_name, data, formatted_data, title, description, unique_keys)
        
# Create the context with the selected strategy
ui_message_context = UIMessageContext(NoopUIMessageStrategy())


