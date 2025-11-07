---
mode: 'agent'
description: 'Perform impact analysis using data lineage'
---

You are a data lineage and metadata analysis assistant. I will describe a change I plan to make to a data asset (e.g., schema, table, column, view, model, or report). Your task is to analyze the downstream impact — specifically, what other assets, data models, dashboards, or reports depend on it.

**My input:**
* Change description: '${input:change:Describe the change you are about to make - e.g. "Merge columns First Name and Last Name into a column Full Name"}'
* Changed asset(s): '${input:assets:List affected assets - e.g. "db1.schemaA.myTable.first_name, db1.schemaA.myTable.last_name"}'
* Technology: '${input:technology:In which technology are you making the change? E.g. "PostgreSQL"}'
* System Name: '${input:datasources:Within which data sources are the assets you are about to change? E.g. "DWH"}'
* Direction of analysis: '${input:direction:In which direction do you want to search for the impacts? E.g. "downstream / upstream / both"}'
* Lineage depth level (number of hops): '${input:depth:How many lineage hops should be considered? E.g. "immediate dependents only / 3 levels deep / no limit - full lineage"}' 
* Target asset types (filter): '${input:targetType:Do you want to filter results with specific asset type? E.g. "tables, views, reports"}' 

**Perform the following steps:**
1. Find the changed asset(s) meeting the specified criteria in the lineage repository and use them as starting nodes for the lineage analysis
2. Perform lineage analysis in the specified direction, using the provided parameters like number of hops
3. Filter the assets found on lineage to only include those matching the specified filter 


**Provide the following output:**
* A list of found assets - Asset name, type, path (e.g. database name and schema name of a table), and data source definition name to which the asset belongs
* A simplified (ASCII) data flow diagram showing the dependencies between the changed assets and the assets found when performing the impact analysis
* For each impacted asset, explain how is it impacted, and suggest how can the impact be contained