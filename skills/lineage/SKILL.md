---
name : lineage
description : Use this skill to explore upstream/downstream data lineage and historical lineage changes through a guided 3-phase workflow - asset identification → lineage graph traversal → historical version comparison. Handles both direct lineage search and catalog-first lookup with ID conversion. Triggers when user asks about data relationships, sources, or consumers using phrases like - "what feeds", "what feeds into", "what feeds in", "where does X come from", "what sources", "what produces", "upstream", "downstream", "lineage", "impact analysis", "data pipeline", "trace this data", "what depends on", "what consumes", "what changed", "data flow", "source to target", "pipeline history", "lineage changes", "show lineage for", "get lineage of", "what is impacted"

---

# Data Lineage Guide

## Overview

Use this skill any time the user wants to understand data flow, trace data origins, identify downstream impacts, or analyze how data pipelines have changed over time. This skill guides users through exploring data lineage relationships in a structured way, ensuring they understand the scope and depth of lineage traversal before executing queries.

## Phase 0: Intent Detection and Entry Path Selection

Always start by understanding what the user wants to accomplish and which entry path is most appropriate:

### Entry Path A: Direct Lineage Search (Lineage-First)
Use when the user mentions an asset name but doesn't specify a catalog/project context, or when they want to search across all lineage assets.
- **Tool**: `lineage_search_lineage_assets`
- **Best for**: "Find the lineage for CUSTOMER_360", "What feeds into the sales table?"
- **Supports**: Optional filters for technology type and asset type

### Entry Path B: Catalog Asset Lookup (Catalog-First)
Use when the user references a known catalog or project asset, or provides specific container context.
- **Tools**: `search_asset` → `lineage_convert_to_lineage_id`
- **Best for**: "Show lineage for the ORDERS table in the sales catalog", "Trace the customer_data asset in AgentTest project"
- **Requires**: Container context (catalog or project name)

**Decision Logic**:
- If user mentions "catalog" or "project" name → Use Path B (Catalog-First)
- If user only provides asset name without container → Use Path A (Lineage-First)
- If uncertain → Ask user to clarify or default to Path A

## Phase 1: Asset Identification

Locate the starting asset(s) in the lineage graph using the appropriate entry path.

### Path A: Direct Lineage Search

<Steps>
<Step>
1. Call `lineage_search_lineage_assets` with the asset name provided by the user. Include optional filters if the user specifies:
   - `technology_name`: Only if user mentions specific technology (e.g., "PostgreSQL", "Azure SQL")
   - `asset_type`: Only if user mentions specific type (e.g., "Table", "Column", "View")
   - `tag`: If user mentions tagged assets
   - `business_term` or `business_classification`: If user mentions governance metadata
   - `data_quality_operator` and `data_quality_value`: If user mentions quality thresholds
</Step>
<Step>
2. The tool returns a list of matching lineage assets with their 64-character hexadecimal lineage IDs, names, types, and hierarchical paths.
</Step>
<Step>
3. Present the matched assets to the user in a clear format showing:
   - Asset name
   - Asset type
   - Full hierarchical path (identity_key)
   - Parent asset information if available
</Step>
<Step>
4. If multiple assets match, ask the user to confirm which asset(s) they want to explore. If only one asset matches, confirm it's the correct one before proceeding.
</Step>
<Step>
5. Extract and save the lineage ID(s) from the confirmed asset(s) for Phase 2.
</Step>
</Steps>

### Path B: Catalog Asset Lookup

<Steps>
<Step>
1. Call `search_asset` with:
   - `search_prompt`: The user's asset description
   - `container_type`: "catalog" or "project" based on user's context
</Step>
<Step>
2. Present the search results to the user, showing asset names, IDs, and container information.
</Step>
<Step>
3. Ask the user to confirm which asset they want to explore.
</Step>
<Step>
4. Once confirmed, call `lineage_convert_to_lineage_id` with:
   - `container_id`: The catalog or project ID from the search result
   - `asset_id`: The asset ID from the search result
</Step>
<Step>
5. The tool returns the 64-character hexadecimal lineage ID required for lineage graph queries.
</Step>
<Step>
6. Save the lineage ID for Phase 2.
</Step>
</Steps>

**Important Validation**:
- Lineage IDs must be exactly 64 hexadecimal characters
- If you receive a shorter ID or UUID, you MUST use `lineage_convert_to_lineage_id` to convert it
- Never proceed to Phase 2 without a valid 64-character lineage ID

## Phase 2: Lineage Graph Traversal

Retrieve and present the upstream and downstream lineage relationships.

### Critical: Inform User About Traversal Depth

**BEFORE calling `lineage_get_lineage_graph`, you MUST**:

<Steps>
<Step>
1. Explain to the user that the default lineage traversal depth is **3 hops** in each direction (upstream and downstream). This means:
   - **3 hops upstream**: Shows 3 levels of data sources feeding into the asset
   - **3 hops downstream**: Shows 3 levels of consumers using the asset's data
   - **Limitation**: For complex or deeply nested pipelines, 3 hops may not capture the complete data flow
</Step>
<Step>
2. Present the user with traversal depth options:
   - **Immediate lineage (1-2 hops)**: Direct producers and consumers only
   - **Standard lineage (3 hops - default)**: Broader pipeline context, good for most use cases
   - **Full lineage (deep traversal - 50 hops)**: Complete path to ultimate sources and targets
     - Note: If the returned terminal asset ID matches the query asset ID, that asset IS the ultimate source/target
</Step>
<Step>
3. Ask the user which depth they prefer, or confirm if they want to proceed with the default 3 hops.
</Step>
</Steps>

### Executing Lineage Graph Query

<Steps>
<Step>
4. Based on the user's depth preference, call `lineage_get_lineage_graph` with:
   - `lineage_ids`: The 64-character lineage ID(s) from Phase 1 (can be a single ID or list of IDs)
   - `hop_up`: Number of upstream levels
     - "1" for immediate upstream
     - "3" for standard (default)
     - "50" for full upstream traversal
     - "0" if user only wants downstream
   - `hop_down`: Number of downstream levels
     - "1" for immediate downstream
     - "3" for standard (default)
     - "50" for full downstream traversal
     - "0" if user only wants upstream
   - `ultimate`: Optional parameter for ultimate source/target queries
     - "source" for ultimate source only
     - "target" for ultimate target only
     - "both" for both ultimate source and target
     - "" (empty string) when finding path between two assets
     - None for standard hop-based traversal
</Step>
<Step>
5. The tool returns:
   - `lineage_assets`: Complete list of assets in the lineage graph with metadata (name, type, tags, identity_key, parent info)
   - `edges_in_view`: Connections showing data flow (format: "edge from: AssetA, to: AssetB, relation: RelationType")
   - `url`: Direct link to visualize the lineage graph in the UI
</Step>
</Steps>

### Presenting Lineage Results

<Steps>
<Step>
6. Present the lineage graph results in a structured format:
   - **Upstream Sources**: List assets that feed data into the queried asset, organized by hop level if possible
   - **Downstream Consumers**: List assets that consume data from the queried asset, organized by hop level if possible
   - **Transformation Steps**: Highlight any transformation or processing assets in the pipeline
   - **Data Flow Connections**: Summarize key relationships from the edges_in_view
</Step>
<Step>
7. **ALWAYS include the UI visualization URL** in your response so users can explore the interactive lineage graph.
</Step>
<Step>
8. If the user requested ultimate source/target and the returned asset ID matches the query asset ID, explicitly state: "This asset IS the ultimate [source/target] - there are no further [upstream/downstream] dependencies."
</Step>
</Steps>

### Special Cases

**Finding Path Between Two Assets**:
- If user asks "trace from Asset A to Asset B" or "path between X and Y":
  1. Get lineage IDs for both assets (Phase 1)
  2. Call `lineage_get_lineage_graph` with:
     - `lineage_ids`: [lineage_id_A, lineage_id_B]
     - `hop_up`: "50"
     - `hop_down`: "50"
     - `ultimate`: "" (empty string)
  3. Search the returned graph for the path connecting the two assets

**Impact Analysis**:
- If user asks "what would break if we changed X?":
  1. Focus on downstream traversal
  2. Set `hop_down` to "50" for complete impact view
  3. Highlight all dependent tables, reports, and data products

**Source Tracing**:
- If user asks "where does this data come from originally?":
  1. Focus on upstream traversal
  2. Set `hop_up` to "50" or use `ultimate`: "source"
  3. Identify the terminal source asset(s)

## Phase 3: Historical Lineage Comparison (Optional)

**Note**: This phase depends on the `lineage_get_lineage_versions` tool which provides version timestamps for historical comparison.

Use this phase when the user wants to understand how the data pipeline has changed over time.

<Steps>
<Step>
1. Determine if the user wants historical comparison by looking for phrases like:
   - "what changed in the pipeline"
   - "has anything changed since [date]"
   - "compare lineage from [date] to [date]"
   - "pipeline changes over time"
   - "what's new in the data flow"
</Step>
<Step>
2. If historical comparison is requested, convert any natural language dates to ISO 8601 format, then call `lineage_get_lineage_versions` with:
   - `since`: Start date in ISO 8601 format (e.g., "2025-01-01T00:00:00Z" or "2025Z" for year)
   - `until`: End date in ISO 8601 format (e.g., "2025-12-31T23:59:59Z" or "2025Z" for year)
   
   **Natural Language Date Conversion**:
   - "since Friday" → Calculate the date of the most recent Friday and convert to ISO 8601
   - "since last week" → Calculate 7 days ago from current date
   - "since last month" → Calculate 30 days ago or first day of previous month
   - "in the last 3 days" → Calculate 3 days ago from current date
   - "this year" → Use current year start (e.g., "2026-01-01T00:00:00Z")
   - Use the current time to calculate relative dates accurately
</Step>
<Step>
3. The tool returns a list of available lineage version timestamps between the specified dates.
</Step>
<Step>
4. Select two versions to compare (typically first and last, or user-specified dates).
</Step>
<Step>
5. If user wants version comparison done for assets, call `lineage_search_lineage_assets` with `dates` parameter. Otherwise, if user wants comparison to be done for graph, use `lineage_get_lineage_graph` with the `dates` parameter:
   - Call with `dates` parameter containing the two version timestamps
   - This retrieves the lineage graph as it existed at those two points in time
</Step>
<Step>
6. Compare the two lineage graphs and identify changes:
   
   **If user is comparing assets:**
   - Call `lineage_get_lineage_comparison` with:
     - `compared_lineage_assets`: Asset IDs to compare
     - `base_version`: Later date (more recent version)
     - `compared_version`: Earlier date (older version)
   
   **If user is comparing graphs:**
   - Call `lineage_get_lineage_comparison` with:
     - `initial_lineage_assets`: Asset IDs that were passed to `lineage_get_lineage_graph` as `lineage_ids`
     - `compared_lineage_assets`: All asset IDs returned by `lineage_get_lineage_graph`
     - `base_version`: Later date (more recent version)
     - `compared_version`: Earlier date (older version)
</Step>
<Step>
7. Present a clear summary of changes:
   - List new assets with their types and roles
   - List removed assets and their previous roles
   - Highlight significant changes in data flow patterns
   - Note any changes in data quality or governance metadata
</Step>
</Steps>

### Historical Comparison Example Workflow

User: "Has anything changed in the pipeline for our revenue dashboard in the last month?"

1. Find the revenue dashboard asset (Phase 1)
2. Call `lineage_get_lineage_versions` with since="2025-11-01Z" and until="2025-12-01Z"
3. Get version timestamps (e.g., ["2025-11-01T00:00:00Z", "2025-11-15T00:00:00Z", "2025-12-01T00:00:00Z"])
4. Call `lineage_get_lineage_graph` with dates=["2025-11-01T00:00:00Z", "2025-12-01T00:00:00Z"]
5. Call `lineage_get_lineage_comparison` with:
   - `initial_lineage_assets`: Same asset IDs used as `lineage_ids` in `lineage_get_lineage_graph`
   - `compared_lineage_assets`: All asset IDs returned by `lineage_get_lineage_graph`
   - `base_version`: "2025-12-01T00:00:00Z" (later date)
   - `compared_version`: "2025-11-01T00:00:00Z" (earlier date)

## Important Guidelines

### Lineage ID Validation
- **CRITICAL**: `lineage_get_lineage_graph` ONLY accepts 64-character hexadecimal lineage IDs
- Before calling `lineage_get_lineage_graph`, verify each lineage_id:
  - Length is exactly 64 characters
  - Contains only hexadecimal characters (0-9, a-f)
- If validation fails, use `lineage_convert_to_lineage_id` or `lineage_search_lineage_assets` to get valid IDs

### Hop Depth Best Practices
- **Always inform the user** about the 3-hop default limitation before executing
- **Always confirm** the user's preferred traversal depth
- Use hop values strategically:
  - "1": Immediate neighbors only
  - "3": Standard view (default)
  - "50": Deep traversal for complete pipeline view
  - "0": Exclude that direction entirely

### Response Completeness
- **Always return complete results** - never truncate lineage assets or edges
- **Always include the UI visualization URL** in your response
- **Always explain** what the lineage graph shows in business terms, not just technical details

### Error Handling
- If no assets found in Phase 1, suggest alternative search terms or filters
- If lineage graph is empty, explain possible reasons (asset not yet scanned, no relationships, etc.)
- If historical versions not available, explain that lineage versioning may not be enabled

### Multi-Asset Queries
- When user provides multiple asset names, get lineage IDs for all of them
- Pass all lineage IDs together to `lineage_get_lineage_graph` to see relationships between them
- Use hop_up="50" and hop_down="50" for multi-asset queries to capture connections

## Skill Completion

After completing the lineage exploration workflow:
1. Summarize what was discovered (sources, consumers, changes)
2. Provide the UI visualization link for further exploration
3. Offer to explore related aspects (e.g., "Would you like to see the data quality metrics for these assets?")
4. If historical comparison was performed, highlight the most significant changes

---

[//]: # (Copyright [2026] [IBM])
[//]: # (Licensed under the Apache License, Version 2.0 \(http://www.apache.org/licenses/LICENSE-2.0\))
[//]: # (See the LICENSE file in the project root for license information.)