# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Any, Dict, Optional
from urllib.parse import parse_qs, quote, urlencode, urlparse

from pydantic import BaseModel

from app.shared.agent_constants import MARKDOWN_CODE_TEMPLATE
from app.shared.constants import AGENT_ERROR_MSG_TYPE, AGENT_UI_MSG_TYPE
import app.shared.ui_message.utils as ui_message_utils


BULK_SELECTION_DESCRIPTION = "You can ask me to perform bulk actions on a subset of these results using the row numbers.  You can use a range (1-3) or a list (1, 3, 5)"

class UIMetadata(BaseModel):
    """
    Metadata for UI messages sent through the graph.

    Attributes:
        tool_name: The name of the tool that generated this message
    """

    tool_name: str = ""


class CardBodyExternalComponent(BaseModel):
    """
    Represents a component with external resource in the body of a card in the UI.

    Attributes:
        source: The url for rendering an external resource
    """

    source: str


class CardBodyTextComponent(BaseModel):
    """
    Represents a component with text in the body of a card in the UI.

    Attributes:
        text: The text to display in the card
    """

    text: str


class ButtonComponent(BaseModel):
    """
    Represents a button component in the UI message structure.

    Attributes:
        label: The label for the button
        url: The url to navigate to when the button is clicked
    """

    label: str
    url: str


class CardComponent(BaseModel):
    """
    Represents a card component in the UI message structure.

    Attributes:
        title: The title of the card
        body: The list of body components of the card
        footer: The list of button components in footer of the card
    """

    title: str
    body: list[CardBodyTextComponent | CardBodyExternalComponent]
    footer: list[ButtonComponent]


class MessageResponseComponent(BaseModel):
    """
    Represents a message response component in the UI message structure.

    Attributes:
        version: The version of the component
        message_response: The message response content
    """

    version: str = "1.0"
    message_response: Dict[str, Any]

    @classmethod
    def create_text_response(
        cls, text: Optional[str] = None
    ) -> "MessageResponseComponent":
        """
        Create a text response component.

        Args:
            text: The text content to display

        Returns:
            A MessageResponseComponent instance configured for text display
        """
        return cls(message_response={"response_type": "text", "text": text})

    @classmethod
    def create_option_response(
        cls,
        options: list[Dict[str, Any]],
        title: str,
        description: str,
        preference: str = "button",
    ) -> "MessageResponseComponent":
        """
        Create an option response component.

        Args:
            options: List of option objects, each with label and value
            title: Title for the option selector
            description: Description for the option selector
            preference: Display preference (default: "button")

        Returns:
            A MessageResponseComponent instance configured for option selection
        """
        return cls(
            message_response={
                "response_type": "option",
                "title": title,
                "description": description,
                "preference": preference,
                "options": options,
            }
        )

    @classmethod
    def create_card_response(
        cls,
        card_component: CardComponent,
    ) -> "MessageResponseComponent":
        """
        Create a card response component.

        Args:
            card_component: CardComponent to be displayed in the response

        Returns:
            A MessageResponseComponent instance configured for displaying card
        """
        return cls(
            message_response={"response_type": "card", **card_component.model_dump()}
        )

    @classmethod
    def create_carousel_response(
        cls, card_components: list[CardComponent]
    ) -> "MessageResponseComponent":
        """
        Create a carousel response component.

        Args:
            card_components: List of card elements

        Returns:
            A MessageResponseComponent instance configured for displaying carousel
        """
        return cls(
            message_response={
                "response_type": "carousel",
                "items": [
                    {"response_type": "card", **card.model_dump()}
                    for card in card_components
                ],
            }
        )


class UIContent(BaseModel):
    """
    Represents the content structure of a UI message.

    Attributes:
        version: The version of the content structure
        components: List of components in the message
    """

    version: str = "1.0"
    components: list[MessageResponseComponent]

    @classmethod
    def create_with_components(
        cls, components: list[MessageResponseComponent]
    ) -> "UIContent":
        """
        Create a UI content with the given components.

        Args:
            components: List of message response components

        Returns:
            A UIContent instance with the specified components
        """
        return cls(components=components)

    @classmethod
    def create_with_text(cls, text: Optional[str] = None) -> "UIContent":
        """
        Create a UI content with a single text component.

        Args:
            text: The text to display

        Returns:
            A UIContent instance with a single text component
        """
        component = MessageResponseComponent.create_text_response(text)
        return cls(components=[component])



