# Lineage Impact Analysis Prompt

## Description
Perform impact analysis using data lineage. This prompt helps analyze the downstream impact of changes to data assets by leveraging data lineage information.

## Prompt Name
`Lineage Impact Analysis prompt`

## Input Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `change` | string | Yes | Describe the change you are about to make | "Merge columns First Name and Last Name into a column Full Name" |
| `assets` | string | Yes | List affected assets | "db1.schemaA.myTable.first_name, db1.schemaA.myTable.last_name" |
| `technology` | string | Yes | In which technology are you making the change? | "PostgreSQL" |
| `datasources` | string | Yes | Within which data sources are the assets you are about to change? | "DWH" |
| `direction` | string | Yes | In which direction do you want to search for the impacts? | "downstream / upstream / both" |
| `depth` | string | Yes | How many lineage hops should be considered? | "immediate dependents only / 3 levels deep / no limit - full lineage" |
| `target_type` | string | No | Do you want to filter results with specific asset type? (optional, leave empty if not needed) | "tables, views, reports" |

## Prompt Template

```
You are a data lineage and metadata analysis assistant. I will describe a change I plan to make to a data asset (e.g., schema, table, column, view, model, or report). Your task is to analyze the downstream impact — specifically, what other assets, data models, dashboards, or reports depend on it.

**My input:**

* Change description: '{change}'

* Changed asset(s): '{assets}'

* Technology: '{technology}'

* System Name: '{datasources}'

* Direction of analysis: '{direction}'

* Lineage depth level (number of hops): '{depth}'

* Target asset types (filter): '{target_type}'  [Only if target_type is provided]

**Perform the following steps:**

1. Find the changed asset(s) meeting the specified criteria in the lineage repository and use them as starting nodes for the lineage analysis

2. Perform lineage analysis in the specified direction, using the provided parameters like number of hops

3. Filter the assets found on lineage to only include those matching the specified filter 

**Provide the following output:**

* A list of found assets - Asset name, type, path (e.g. database name and schema name of a table), and data source definition name to which the asset belongs

* A simplified (ASCII) data flow diagram showing the dependencies between the changed assets and the assets found when performing the impact analysis

* For each impacted asset, explain how is it impacted, and suggest how can the impact be contained
```

## Usage Example

### Example 1: Basic Usage (without target_type)

**Input:**
- change: "Merge columns First Name and Last Name into a column Full Name"
- assets: "db1.schemaA.myTable.first_name, db1.schemaA.myTable.last_name"
- technology: "PostgreSQL"
- datasources: "DWH"
- direction: "downstream"
- depth: "3 levels deep"
- target_type: "" (empty)

**Formatted Prompt:**
```
You are a data lineage and metadata analysis assistant. I will describe a change I plan to make to a data asset (e.g., schema, table, column, view, model, or report). Your task is to analyze the downstream impact — specifically, what other assets, data models, dashboards, or reports depend on it.

**My input:**

* Change description: 'Merge columns First Name and Last Name into a column Full Name'

* Changed asset(s): 'db1.schemaA.myTable.first_name, db1.schemaA.myTable.last_name'

* Technology: 'PostgreSQL'

* System Name: 'DWH'

* Direction of analysis: 'downstream'

* Lineage depth level (number of hops): '3 levels deep'

**Perform the following steps:**

1. Find the changed asset(s) meeting the specified criteria in the lineage repository and use them as starting nodes for the lineage analysis

2. Perform lineage analysis in the specified direction, using the provided parameters like number of hops

3. Filter the assets found on lineage to only include those matching the specified filter 

**Provide the following output:**

* A list of found assets - Asset name, type, path (e.g. database name and schema name of a table), and data source definition name to which the asset belongs

* A simplified (ASCII) data flow diagram showing the dependencies between the changed assets and the assets found when performing the impact analysis

* For each impacted asset, explain how is it impacted, and suggest how can the impact be contained
```

### Example 2: With target_type Filter

**Input:**
- change: "Add new column 'status' to customer table"
- assets: "db1.schemaA.customer"
- technology: "PostgreSQL"
- datasources: "DWH"
- direction: "downstream"
- depth: "2 levels"
- target_type: "tables, views"

**Formatted Prompt:**
```
You are a data lineage and metadata analysis assistant. I will describe a change I plan to make to a data asset (e.g., schema, table, column, view, model, or report). Your task is to analyze the downstream impact — specifically, what other assets, data models, dashboards, or reports depend on it.

**My input:**

* Change description: 'Add new column 'status' to customer table'

* Changed asset(s): 'db1.schemaA.customer'

* Technology: 'PostgreSQL'

* System Name: 'DWH'

* Direction of analysis: 'downstream'

* Lineage depth level (number of hops): '2 levels'

* Target asset types (filter): 'tables, views'

**Perform the following steps:**

1. Find the changed asset(s) meeting the specified criteria in the lineage repository and use them as starting nodes for the lineage analysis

2. Perform lineage analysis in the specified direction, using the provided parameters like number of hops

3. Filter the assets found on lineage to only include those matching the specified filter 

**Provide the following output:**

* A list of found assets - Asset name, type, path (e.g. database name and schema name of a table), and data source definition name to which the asset belongs

* A simplified (ASCII) data flow diagram showing the dependencies between the changed assets and the assets found when performing the impact analysis

* For each impacted asset, explain how is it impacted, and suggest how can the impact be contained
```

## Notes for MCP Clients

For MCP clients that don't support prompt registration, you can:
1. Use this template directly in your application
2. Replace the placeholders `{change}`, `{assets}`, `{technology}`, `{datasources}`, `{direction}`, `{depth}`, and optionally `{target_type}` with actual values
3. If `target_type` is empty or not provided, omit the "Target asset types (filter)" line from the prompt

