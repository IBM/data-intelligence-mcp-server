# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from collections import Counter  # noqa: I001 # Baseline
from typing import Any, Callable, Dict, List, Optional, Sequence, TypeVar  # noqa: UP035 # Baseline

T = TypeVar("T")


def build_filter_hint(active_filters: Dict[str, Any]) -> str:  # noqa: UP006 # Baseline
    """
    Renders applied filters inline into a human-readable hint string.

    Args:
        active_filters: Dictionary of filter keys and values (None/empty values will be ignored).

    Returns:
        Formatted filter hint string, e.g. " (Filtered by: urgency='overdue', sort='priority')",
        or empty string if no active filters.
    """
    if not active_filters:
        return ""

    non_empty_parts: List[str] = []  # noqa: UP006 # Baseline
    for k, v in active_filters.items():
        if v is not None and v != "" and v != "all":  # noqa: PLR1714 # Baseline
            if isinstance(v, str):
                non_empty_parts.append(f"{k}='{v}'")
            else:
                non_empty_parts.append(f"{k}={v}")

    if not non_empty_parts:
        return ""

    return f" (Filtered by: {', '.join(non_empty_parts)})"


def build_semantic_summary(  # noqa: PLR0913 # Baseline
    items: Sequence[T],
    total_count: int,
    page_offset: int = 0,
    page_limit: int = 10,
    item_categorizer: Optional[Callable[[T], Optional[str]]] = None,  # noqa: UP045 # Baseline
    active_filters: Optional[Dict[str, Any]] = None,  # noqa: UP006, UP045 # Baseline
) -> str:
    """
    Builds a human-readable semantic summary for a list/page of items (Strategy C).

    Args:
        items: Sequence of items on the current page.
        total_count: Total count of items available across all pages.
        page_offset: 0-based offset of the current page.
        page_limit: Limit/page size of the current page.
        item_categorizer: Optional callable mapping an item to a category name (or None).
        active_filters: Optional dictionary of active filters applied.

    Returns:
        Human-readable summary string.
    """
    del page_limit
    filter_hint = build_filter_hint(active_filters or {})

    if total_count == 0 or len(items) == 0:
        if total_count == 0:
            return f"Found 0 total items{filter_hint}."
        # total_count > 0 but items on this offset is empty
        return f"Found {total_count} total items{filter_hint}. Showing items 0-0. Use prev_page_token to navigate back."

    # Categorize items if categorizer provided
    category_summary_parts: List[str] = []  # noqa: UP006 # Baseline
    if item_categorizer is not None:
        categories = [item_categorizer(item) for item in items]
        category_counts = Counter(c for c in categories if c is not None)
        for cat_name, count in category_counts.items():
            category_summary_parts.append(f"{count} are {cat_name}")

    category_str = ""
    if category_summary_parts:
        category_str = f" {', '.join(category_summary_parts)}."

    start_idx = page_offset + 1
    end_idx = page_offset + len(items)
    paging_str = f" Showing items {start_idx}-{end_idx}."

    nav_hint = ""
    if end_idx < total_count:
        nav_hint = " Use next_page_token to fetch more."

    return f"Found {total_count} total items{filter_hint}.{category_str}{paging_str}{nav_hint}"
