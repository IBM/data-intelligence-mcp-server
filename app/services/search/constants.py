# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Constants for search service tools."""

RELATED_ITEMS_GUIDE = """
**RELATED ITEMS - THREE TYPES:**

1. **Related Assets** - Link to other data assets (tables, files, etc.)
2. **Related Artifacts** - Link to governance items (business terms, classifications)
3. **Related Columns** - Link to specific columns in other assets

**WORKFLOW:**
All names (assets, containers, artifacts) are resolved to IDs internally by the tool. You can provide names OR IDs directly!

**CRITICAL REQUIREMENTS BY TYPE:**

**For ASSETS (item_type="asset"):**
- target_id_or_name: Asset name or UUID (REQUIRED)
- target_container_id_or_name: Target's container name or UUID (REQUIRED)
  * Container TYPE (catalog/project) is inherited from source asset's container_type
  * Container ID/NAME MUST be DIFFERENT from source container (never use source container)
  * If missing, use dynamic_query_search to find target and ask user to select
- relationship_name: Default "accesses" (optional)

**For ARTIFACTS (item_type="artifact"):**
- target_id_or_name: Artifact name or global_id (REQUIRED)
- artifact_type: "glossary_term" or "classification" (optional)
  * If not provided, tries glossary_term first, then classification
- relationship_name: Default "accesses" (optional)
- target_container_id_or_name: NOT needed (artifacts are global)

**For COLUMNS (item_type="column"):**
- target_id_or_name: Column name (REQUIRED)
- target_asset_id_or_name: Asset name or UUID containing the column (REQUIRED)
- target_container_id_or_name: Target's container name or UUID (REQUIRED)
  * Container TYPE (catalog/project) is inherited from source asset's container_type
  * Container ID/NAME MUST be DIFFERENT from source container (never use source container)
  * If missing, use dynamic_query_search to find target and ask user to select
- relationship_name: Default "accesses" (optional)

**SIMPLIFIED AGENT WORKFLOW:**

**Example 1: "For asset claims in catalog 'ExampleTest' add artifact 'Home Affordable Refinance Program Flag' business term"** (no relationship specified → omit relationship_name, defaults to "accesses")
```
update_asset_metadata(
    asset_id_or_name="claims",
    container_id_or_name="ExampleTest",
    container_type="catalog",
    related_items=[{
        "item_type": "artifact",
        "target_id_or_name": "Home Affordable Refinance Program Flag"
    }]
)
```

**Example 1b: "For asset claims in catalog 'ExampleTest' add artifact 'Home Affordable Refinance Program Flag' business term with relationship consists_of"** (user explicitly names the relationship)
```
update_asset_metadata(
    asset_id_or_name="claims",
    container_id_or_name="ExampleTest",
    container_type="catalog",
    related_items=[{
        "item_type": "artifact",
        "target_id_or_name": "Home Affordable Refinance Program Flag",
        "relationship_name": "consists_of"
    }]
)
```

**Example 2: "For asset claims in catalog 'ExampleTest' add column account_id from asset account in AgentsTest catalog"**
```
update_asset_metadata(
    asset_id_or_name="claims",
    container_id_or_name="ExampleTest",
    container_type="catalog",
    related_items=[{
        "item_type": "column",
        "target_id_or_name": "account_id",
        "target_asset_id_or_name": "account",
        "target_container_id_or_name": "AgentsTest"
    }]
)
```

**Example 2b: "For asset claims in catalog 'ExampleTest' add column account_id from asset account" (container NOT specified)**
**CRITICAL**: When target container is NOT specified, you MUST use dynamic_query_search to find the target asset:
```
# Step 1: Search for the target asset
dynamic_query_search(
    query="column account_id from asset account",
    container_type="catalog"  # Same type as source
)
# Step 2: User selects from results, e.g., "account_id" is in "AgentsTest" catalog
# Step 3: Now call update with the correct container
update_asset_metadata(
    asset_id_or_name="claims",
    container_id_or_name="ExampleTest",
    container_type="catalog",
    related_items=[{
        "item_type": "column",
        "target_id_or_name": "account_id",
        "target_asset_id_or_name": "account",
        "target_container_id_or_name": "AgentsTest"  # From search results
    }]
)
```

**Example 3: "For asset claims in catalog 'ExampleTest' add related asset ACCOUNT_HOLDERS.csv from catalog AgentsTest"**
```
update_asset_metadata(
    asset_id_or_name="claims",
    container_id_or_name="ExampleTest",
    container_type="catalog",
    related_items=[{
        "item_type": "asset",
        "target_id_or_name": "ACCOUNT_HOLDERS.csv",
        "target_container_id_or_name": "AgentsTest",
        "relationship_name": "accesses"
    }]
)
```

**KEY RULES:**
1. Provide names OR UUIDs directly - tool resolves them internally
2. Target container TYPE (catalog/project) is inherited from source asset's container_type
3. Target container ID/NAME MUST be DIFFERENT from source container (e.g., source in "Catalog A", target in "Catalog B")
4. For ARTIFACTS: Provide artifact name or global_id (no container needed)
5. For ASSETS/COLUMNS: Provide target_container_id_or_name (target's container name or UUID)
6. **CRITICAL**: If user doesn't specify target container, you MUST use dynamic_query_search to find it - DO NOT assume it's in the same container as source
7. **NEVER use source container_id_or_name as target_container_id_or_name** - they are always different
"""

# Made with Bob
