# AI-First Large List Handling & Pagination Guide

This guide establishes the architectural principles and implementation patterns for handling large collections and list tools in the Data Intelligence MCP Server. It condenses the design strategy that led to [`app/shared/models/pagination.py`](app/shared/models/pagination.py:1) and [`app/shared/utils/list_strategies.py`](app/shared/utils/list_strategies.py:1), currently used in workflow inbox and list tools (e.g. [`app/services/workflow/tools/get_workflow_tasks_from_my_inbox.py`](app/services/workflow/tools/get_workflow_tasks_from_my_inbox.py:1)).

---

## 1. Core Problem: Context Window Pollution & Token Costs

When designing Model Context Protocol (MCP) tools, the primary constraint is **LLM context window pollution and compounding token costs**.
Dumping dozens or hundreds of rich JSON items into a tool response forces the LLM to ingest and retain all that text on every subsequent conversation turn.

An AI-first list tool must balance:
- Human readability vs. LLM meta-awareness.
- Predictable token budgets per turn.
- Seamless multi-turn pagination without fragile client-side offset guesswork.
- Intent-based filtering before data hits LLM context.

---

## 2. Architectural Strategies for MCP List Tools

### Strategy 1: Interactive UI Widgets ("Zero-Token" Rendering)
* **Concept**: Return structured payloads (`structuredContent` / widget JSON) targeted at clients supporting rich UI rendering (such as Claude Desktop artifacts or custom web frontends).
* **Benefit**: The client renders an interactive, scrollable data table directly to the user. The data never enters the LLM context window, keeping chat sessions lean and inexpensive.
* **Fallback**: When the client lacks rich UI / HTML capabilities (detected via [`supports_rich_text_format`](app/shared/utils/client_detection.py:1)), fallback to structured JSON or compact text.

### Strategy 2: Semantic Summarization & Smart Aggregation (Strategy C)
* **Concept**: Shift from raw tabular dumps to intent-based meta-summaries alongside a small item page (default 5–10 items).
* **Pattern**: Return a concise header summarizing totals, category breakdowns, and active filters.
  * *Example*: `"Found 142 total tasks (Filtered by: urgency='overdue'). 12 are overdue, 45 are high-urgency. Showing items 1-10. Use next_page_token to fetch more."`
* **Benefit**: Gives the LLM meta-awareness to autonomously triage and prompt the user (e.g., *"You have 12 overdue tasks. Would you like me to prioritize those?"*) rather than dumb offset scrolling.
* **Helper**: Implemented in [`app/shared/utils/list_strategies.py:build_semantic_summary()`](app/shared/utils/list_strategies.py:39) and [`build_filter_hint()`](app/shared/utils/list_strategies.py:11).

### Strategy 3: Server-Managed Cursor Pagination
* **Concept**: Opaque base64 tokens representing pagination state (`PageCursor`) instead of exposing raw database offset calculations to the LLM.
* **Pattern**: Tools accept `page_token: Optional[str]` and `page_size: int = 10`. The response includes `next_page_token`, `prev_page_token`, `has_more`, and `total_count`.
* **Benefit**: Prevents LLMs from hallucinating invalid offset numbers. Enables clean linear browsing across tool invocations.
* **Models**: Implemented in [`app/shared/models/pagination.py:PageCursor`](app/shared/models/pagination.py:15) and [`PaginatedResponse`](app/shared/models/pagination.py:60).

### Strategy 4: Dual-Layer Filtering Architecture
* **Native API Filtering (Heavy Lifting)**: Push coarse-grained filters (urgency, status, date ranges `due_before`/`due_after`) directly to underlying backend/REST APIs.
* **In-Memory Semantic Filtering (Agility)**: Fetch a bounded batch to server memory and apply precise sorting, regex matching, or categorization before returning to the model.
* **Benefit**: Reduces upstream network latency while exposing clean, intent-driven tool arguments (`urgency`, `sort`, `due_before`, `due_after`).

### Strategy 5: Standardized Autocompletion Capabilities
* Declare MCP completion capabilities (`completion/complete`) for complex filter keys, project tags, or categories to assist LLMs and client UIs in parameter selection.

---

## 3. Comparison of Approaches

| Approach | Context Window Impact | Implementation Complexity | Best Used For |
|---|---|---|---|
| **Truncated Raw Batch (Top 10)** | Low initial, stacks over turns | Very Low | Prototyping / small datasets |
| **structuredContent Widget** | Zero Tokens in LLM Context | High (requires UI support) | Human browsing & high-volume tables |
| **Semantic Summarization** | Medium-Low (~200–500 tokens) | Medium | AI-driven triage, planning & next-step suggestions |
| **Server-Managed Cursor** | Low & constant per turn | Low-Medium | Multi-turn linear scanning & pagination |
| **Dual-Layer Filtering** | Minimal (filtered at source) | Medium | Large backends with intent extraction |

---

## 4. Shared Components & Code Reference

### 4.1. `PageCursor` and `PaginatedResponse`
Located in [`app/shared/models/pagination.py`](app/shared/models/pagination.py:1):

```python
from app.shared.models.pagination import PageCursor, PaginatedResponse

# Encoding cursor to opaque token
cursor = PageCursor(limit=10, offset=20)
token_str = cursor.to_token()

# Decoding cursor from client token
cursor = PageCursor.from_token(token_str)
offset = cursor.offset
limit = cursor.limit
```

### 4.2. `build_semantic_summary`
Located in [`app/shared/utils/list_strategies.py`](app/shared/utils/list_strategies.py:1):

```python
from app.shared.utils.list_strategies import build_semantic_summary

semantic_summary = build_semantic_summary(
    items=tasks,
    total_count=total_count,
    page_offset=offset,
    page_limit=request.page_size,
    item_categorizer=inbox_task_categorizer,  # Optional Callable[[T], Optional[str]]
    active_filters={"urgency": "overdue", "sort": "priority"},
)
```

### 4.3. Standard Tool Implementation Pattern
Reference implementation in [`app/services/workflow/tools/get_workflow_tasks_from_my_inbox.py`](app/services/workflow/tools/get_workflow_tasks_from_my_inbox.py:330):

```python
# 1. Decode cursor token if provided
offset = 0
if request.page_token:
    try:
        cursor = PageCursor.from_token(request.page_token)
        offset = cursor.offset
        if cursor.limit:
            request.page_size = cursor.limit
    except Exception as e:
        offset = 0

# 2. Fetch page and compute total
total_count = await fetch_total_count()
items = await fetch_items(limit=request.page_size, offset=offset)

# 3. Compute pagination tokens
next_page_token = (
    PageCursor(limit=request.page_size, offset=offset + request.page_size).to_token()
    if (offset + request.page_size) < total_count
    else None
)
prev_page_token = (
    PageCursor(limit=request.page_size, offset=max(0, offset - request.page_size)).to_token()
    if offset > 0
    else None
)

# 4. Generate semantic summary
semantic_summary = build_semantic_summary(
    items=items,
    total_count=total_count,
    page_offset=offset,
    page_limit=request.page_size,
    item_categorizer=my_item_categorizer,
    active_filters={"status": request.status},
)
```

---

## 5. Guidelines for Future MCP List Tools (Bob Instructions)

When adding or refactoring list tools in any service (`workflow`, `glossary`, etc.):
1. **Never return unpaginated lists**: Always default `page_size` to `10` (maximum sensible limit `50`).
2. **Support opaque tokens**: Accept `page_token: Optional[str] = None` in the tool request model and return `next_page_token` / `prev_page_token` using [`PageCursor`](app/shared/models/pagination.py:15).
3. **Always supply `semantic_summary`**: Use [`build_semantic_summary`](app/shared/utils/list_strategies.py:39) with a relevant categorizer (e.g. urgency, type, state) to empower the LLM with immediate triage capability.
4. **Push filtering upstream**: Expose intent-based filter parameters in the tool schema and push them to backend APIs before falling back to in-memory filtering.
5. **Format adaptive output**: Check client capabilities via [`supports_rich_text_format`](app/shared/utils/client_detection.py:1) to switch between table format and JSON payloads cleanly.
