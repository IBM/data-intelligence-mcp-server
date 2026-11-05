# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import base64  # noqa: I001 # Baseline
import json
from typing import Any, Dict, Generic, List, Optional, TypeVar  # noqa: UP035 # Baseline
from pydantic import BaseModel, Field

from app.shared.models.base_response import BaseResponseModel

T = TypeVar("T")


class PageCursor(BaseModel):
    """
    Pagination cursor holding limit and offset.
    Supports serialization to and deserialization from base64 opaque token strings.
    """

    limit: int = Field(..., description="Number of items to fetch", ge=1)
    offset: int = Field(0, description="Zero-based index offset", ge=0)

    def to_token(self) -> str:
        """Serialize cursor to a base64 opaque token string."""
        data = {"limit": self.limit, "offset": self.offset}
        json_bytes = json.dumps(data).encode("utf-8")
        return base64.urlsafe_b64encode(json_bytes).decode("utf-8")

    def to_dict(self) -> Dict[str, Any]:  # noqa: UP006 # Baseline
        """Convert cursor to plain dictionary representation."""
        return {"limit": self.limit, "offset": self.offset}

    @classmethod
    def from_token(cls, token: str) -> "PageCursor":
        """
        Deserialize cursor from a base64 opaque token string.

        Args:
            token: Base64 encoded JSON string representing the cursor.

        Returns:
            PageCursor instance.

        Raises:
            ValueError: If token cannot be decoded or parsed.
        """
        try:
            json_bytes = base64.urlsafe_b64decode(token.encode("utf-8"))
            data = json.loads(json_bytes.decode("utf-8"))
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Invalid page token: {e}") from e

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageCursor":  # noqa: UP006 # Baseline
        """Create cursor from plain dictionary representation."""
        return cls(**data)


class PaginatedResponse(BaseResponseModel, Generic[T]):
    """
    Generic wrapper response model for paginated lists.
    """

    items: List[T] = Field(default_factory=list, description="Page of items")  # noqa: UP006 # Baseline
    total_count: int = Field(0, description="Total count of items available")
    returned_count: int = Field(0, description="Count of items in this page")
    next_page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="Opaque token for next page"
    )
    prev_page_token: Optional[str] = Field(  # noqa: UP045 # Baseline
        None, description="Opaque token for previous page"
    )
    has_more: bool = Field(
        False, description="Whether more items exist beyond this page"
    )
