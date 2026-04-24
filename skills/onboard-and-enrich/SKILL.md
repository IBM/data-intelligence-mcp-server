---
name : onboard-and-enrich
description : Use this skill to orchestrate a 4-phase data cataloging or metadata onboarching and metadata enrichment workflow i.e. project setup → connection configuration → metadata import → metadata enrichment. The user can choose to start from any phase and the skill will guide them through the remaining phases.
---

# Data Cataloging and Metadata Enrichment Guide

## Overview

Understand the user prompt to identify if the user wants to onboard data, catalog data, enrich data or import new data and use this skill to guide them through the workflow in all those cases. Use this skill any time the user mentions onboarding data, cataloging data, enriching metadata, importing schemas, setting up a data project, or connecting to a data source — even if they don't use those exact words. Depending on the user request, users can start from any phase in the workflow, not necessarily from the beginning. Example user queries: "Catalog our Postgres sales database", "I want to enrich the data I already imported last week", "Set up a new project for the Finance team and import their Oracle data", "Onboard data from DB2 connection".

## Phase 0: Intent Detection

- Always start by determining the user's intent based on their query. Read the user's request and decide which phase to start from.
- If the user provides a project name in their query, use Phase 1 to check if the project exists, and directly proceed to the next phase.
- If the user provides a connection name in their query, use Phase 2 to check if the connection exists in the project provided, and directly proceed to the next phase.
- If the user query extablishes that the project and connection already exist, start from Phase 3 or Phase 4 depending on the user's intent.
- If the user query establishes that the data is already imported, start from Phase 4 to enrich the metadata.

#### Examples of User Queries and Corresponding Phases:

- For user query: "Catalog our Postgres sales database", in this case the user wants to catalog existing data, so start from Phase 1 to find the project where the Postgres connection is already configured, proceed to Phase 2 to find the connection, and proceed to Phase 3 to import the metadata, and then to Phase 4 for metadata enrichment.
- For user query: "I want to enrich the data I already imported last week", in this case the user wants to enrich already imported data, so start at Phase 1 to find the project where the data was imported, proceed to Phase 4 to enrich the metadata.
- For user query: "Set up a new project for the Finance team and import their Oracle data", in this case the user wants to set up a new project and import data, so start at Phase 1 to create a new project, proceed to Phase 2 to configure the Oracle connection, and proceed to Phase 3 to import the metadata, and then to Phase 4 for metadata enrichment.

## Phase 1: Project Setup

<Steps>
<Step>
1. If the user has provided a project name in the intial query, use the `find_container` tool with `container_id_or_name` set to the project name and `container_type` set to project to determine if the project already exists. If the project exists, proceed to Phase 2. If the project does not exist, proceed to Step 2. If the user has not provided a project name, proceed to Step 2.
</Step>
<Step>
2. Use the `list_containers` tool with `container_type` project to find all the existing projects available to the user.
</Step>
<Step>
3. Ask the user if they would like to use one of the projects from the list of existing projects or create a new project.
</Step>
<Step>
4. If the user wants to use an existing project, confirm which project the user would like to use and use the details of that project for the next phase. 
</Step>
<Step>
5. If the user wants to create a new project, use the `create_project` tool to create a new project. Assume the user does not know the request parameters for the `create_project` tool. Ask the user for the necessary details including the name and create the project accordingly.
</Step>
<Step>
6. Once the project is created, use the details of the new project for the next phase. 
</Step>
</Steps>

## Phase 2: Connection Configuration

<Steps>
<Step>
1. If the user has provided a connection name in the initial query, use the `search_connection` tool with `container` set to the project name from the first phase and `container_type` set to "project" and `connection_name` set to the provided connection name to determine if the connection already exists in the project. If the connection exists, proceed to Phase 3. If the connection does not exist, proceed to step 2. If the user has not provided a connection name, proceed to step 2.
</Step>
<Step>
2. Use the `search_connection` tool with `container` set to the project name from the first phase and `container_type` set to "project" to find all the existing connections available to the user.
</Step>
<Step>
3. Ask the user if they would like to use one of the connections from the list of existing connections or reference a connection from the platform assets catalog.
</Step>
<Step>
4. If the user wants to use an existing connection, confirm which connection the user would like to use and use the details of that connection for the next phase. 
</Step>
<Step>
5. If the user wants to reference a connection from the platform assets catalog:
- first use the `search_connection` tool with `container_type` set to "catalog" and all other request parameters set to None to find all the connections in the platform assets catalog
- ask the user which connection they would like to use 
- once the user confirms their selection, use the `copy_connection` tool with `connection_name` set to the name of the connection they selected `source_catalog` set to None, `target_container` set to the project name from the first phase, and `target_container_type` set to "project"
- after the connection is successfully copied, use the `search_connection` tool with `container` set to the project name from the first phase,`container_type` set to "project" and `connection_name` set to the name of the copied connection to display the details of the new connection; use this connection for the next phase
</Step>
<Step>
6. If the user does not want to use a connection that exists either in the chosen project or in the platform assets catalog, end the conversation by informing the user that a tool for creating a new connection does not exist currently and asking the user to create a new connection through the UI.
</Step>
</Steps>

## Phase 3: Metadata Import

<Steps>
<Step>
1. If the user has provided scope (schemas or tables) to import in the intial query, call the `list_connection_paths` tool with `project_name` set to the project name from the first phase and `connection_name` set to the name of the connection from the second phase to check if the user provided scope is valid. If the scope is invalid, move to step 2, DO NOT default to importing all paths in the connection by default. If the scope is valid, move to step 4. If the user did not provide scope, move to step 2.
</Step>
<Step>
2. Call the `list_connection_paths` tool with `project_name` set to the project name from the first phase and `connection_name` set to the name of the connection from the second phase, and display the schemas and tables available for the user through that connection
</Step>
<Step>
3. Ask the user to define the scope of the metadata import by specifying the schemas and tables they want to import from the list of schemas and tables displayed in the previous step.
</Step>
<Step>
4. Call the `create_metadata_import` tool with `project_name` set to the project name from the first phase, `connection_name` set to the name of the connection from the second phase, and `scope` set to the list of schemas or tables specified by the user in the previous step:
- Use ['/'] for scope if the user wants to import all schemas
- Use ['schema1', 'schema2'] for scope if the user wants to import specific schemas
- Use ["/path/table", "/path/to/table"] for scope if the user wants to import specific tables
<Step>
5. Display the results of the `create_metadata_import` tool call to the user to confirm if the details of the metadata import, specifically the scope, are correct
</Step>
<Step>
6. If the user says the details are incorrect, go back to the step 2 and ask the user to specify the scope again or make any other changes they want to make to the metadata import
</Step>
<Step>
7. If the user says the details are correct, call the `execute_metadata_import` tool with `project_name` set to the project name from the first phase and `metadata_import_name` set to the name of the metadata import from the previous step
</Step>
<Step>
8. Display the results of the `execute_metadata_import` tool to show that the job is running
</Step>
<Step>
9. Confirm with the user if the import job is complete or not, offer the user to get the status of the metadata import job using the `monitor_job_status` tool with `job_id` set to the job ID returned from the `execute_metadata_import` tool and `project` set to the project name from the first phase or ask the user to check on the UI with the job link. Only if the user confirms or `monitor_job_status` tool confirms that the job is complete, proceed to the next phase.
</Step>
</Steps>

## Phase 4: Metadata Enrichment

<Steps>
<Step>
1. If the user has provided enrichment objectives in the intial query, closest match the user's request to the available enrichment objectives (listed in step 2) and skip steps 2 and 3. If the user has provided categories in the intial query, closest match the user's request to the available categories (using `search_categories` tool) and skip step 4. If the user has provided dataset names in their initial query to perform metadata enrichment on, still execute step 5 to make sure their provided dataset names exist in the project.
</Step>
<Step>
2. Explain available enrichment objectives to the user in plain language and confirm their selections. Here is the list of enrichment objectives avaialble for the user:
- profile : Computes column-level statistics (nulls, cardinality, min/max, distributions)
- assign_terms : Auto-assigns business glossary terms to columns using AI
- analyze_quality : Scores data quality across completeness, validity, and consistency dimensions
- analyze_relationships : Discovers primary key and foreign key relationships across tables
- semantic_expansion : Enriches column descriptions and semantic names using AI
- dq_gen_constraints : Generates data quality rules from observed data patterns
- dq_sla_assessment : Assesses data against predefined SLA thresholds
</Step>
<Step>
3. Ask the user which enrichment objectives they want to apply to the metadata. If they want to apply all objectives, ask them to confirm.
</Step>
<Step>
4. Call the `search_categories` tool to get a list of categories available for the user to select from. Confirm with the user which category(s) they want to use for the enrichment.
</Step>
<Step>
5. For dataset_names, confirm with the user if they want to use the names of the assets that were imported in Phase 3, or if they want to specify different names. DO NOT skip this step, always ask the user for datasets to use.
</Step>
<Step>
6. Call the `create_or_update_metadata_enrichment_asset` tool with the selected objectives, categories and datasets. Make sure dataset parameter is NOT NULL.
</Step>
<Step>
7. Call the `execute_metadata_enrichment_asset` tool with the `project_name` from Phase 1 and `metadata_enrichment_name` from the previous step.
</Step>
<Step>
8. Provide the user with the details of the metadata enrichment job. End conversation here.
</Step>
</Steps>

---

[//]: # (Copyright [2026] [IBM])
[//]: # (Licensed under the Apache License, Version 2.0 \(http://www.apache.org/licenses/LICENSE-2.0\))
[//]: # (See the LICENSE file in the project root for license information.)
