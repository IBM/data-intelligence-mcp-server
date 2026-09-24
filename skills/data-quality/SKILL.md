---
name: data-quality
description: Use this skill whenever the user wants to run data quality checks, analzye data quality, generate DQ pipelines, score data quality dimensions, or analyze completeness, validity, consistency, or uniqueness on any dataset. Trigger even if the user says things like "check my data", "how good is my data", "run quality analysis", "validate my tables", "set up quality monitoring", "analyze data quality", or "analyze my dataset" — not just when they explicitly say "DQ pipeline". Also trigger for queries like "generate constraints for my data", "run SLA checks", "profile my tables", or "check data quality on our Oracle/Postgres/DB2 schemas". Covers MDE-based pipelines with DQ objectives [dq_gen_constraints, analyze_quality, dq_sla_assessment, and profile].
---

# Generate Data Quality Pipeline Guide

## Overview

Use this skill when the user wants to generate a Data Quality (DQ) pipeline for their datasets.
The pipeline is implemented as a Metadata Enrichment (MDE) job scoped to DQ-specific enrichment objectives.
The skill guides the user through project setup, connection configuration, metadata import, and DQ enrichment execution.
All phases and steps should be presented to the user as a TODO list so they can follow along and understand which phase/step is being run.

Example user queries:
- "Generate a DQ pipeline for my sales data"
- "Run data quality checks on my Postgres tables"
- "Create a DQ pipeline for the Finance project"
- "Analyze quality and generate constraints for my datasets"
- "Check data quality on our Oracle schemas"
- "How good is my data?"
- "Validate my tables and score completeness"
- "Analyze data quality for the tables in my BANK database"

## General Instructions

- If the user must make a choice, always display an options list.
- If multiple choices are possible, display them in a checklist format.
- Always give the user the option to write their own choice.
- Always try not to interrupt the user too much — batch questions where possible.
- When moving from one step to another, inform the user and proceed.
- **Error handling**: If any tool call fails, display the error message to the user and ask whether to retry with adjusted parameters, skip the step, or abort the pipeline.

---

## Phase 0: Intent Detection

Always start by determining the user's intent and what data they want to run DQ on.

- If the user provides a **project name**, carry it into Phase 1.
- If the user provides a **connection name**, carry it into Phase 2.
- If the user states that data is **already imported** into a project, skip to Phase 3 (DQ Enrichment).
- If intent is **ambiguous** (e.g. "check my data quality" with no project or connection mentioned), ask:
  - *"Which project should we run the DQ pipeline in? And do you already have a data connection set up, or do we need to configure one?"*
  - Proceed once the user clarifies.

The goal is always to produce a running MDE job with DQ objectives — keep that end state in mind.

#### Examples:
- "Generate a DQ pipeline for my Postgres sales data" → Phase 1 → Phase 2 → Phase 2.5 → Phase 3
- "Run DQ checks on the data I already imported into the Finance project" → Phase 1 (confirm project) → Phase 3
- "Set up quality checks on our Oracle schemas" → Phase 1 → Phase 2 → Phase 2.5 → Phase 3

---

## Phase 1: Project Setup

**Goal**: Confirm or create the project to use for the DQ pipeline.

### Steps

1. Call `list_containers` to retrieve available projects.
2. If the user already named a project, find it in the list and confirm.
3. If no project is named, display the list and ask the user to select one or provide a name.
4. If the project doesn't exist, ask the user to confirm before calling `create_project` with the given name.
5. Carry the confirmed project name into Phase 2.

---

## Phase 2: Connection Configuration

**Goal**: Confirm or locate the data connection to use.

> Skip this phase if the user has indicated that data is already imported into the project.

### Steps

1. Read and use the `Phase 2: Connection Configuration` from the skill  `onboard-and-enrich/SKILL.md`

---

## Phase 2.5: Metadata Import (Conditional)

> **Skip this phase** if the user has confirmed that data is already imported into the project. Proceed directly to Phase 3.

**Goal**: Import metadata from the selected connection into the project.

### Steps

1. Read and use the `Phase 3: Metadata Import` from the skill  `onboard-and-enrich/SKILL.md`
2. Monitor the import job using `get_metadata_enrichment_job_status` every 2 minutes.
   - If the job status is `Completed`, proceed to Phase 3.
   - If the job status is `Failed`, display the error and ask the user whether to retry or investigate in the UI.
   - If the job has not completed after **10 checks (20 minutes)**, stop monitoring, display the last known status, and ask the user how to proceed.
3. Carry the metadata import name(s) into Phase 3.

---

## Phase 3: DQ Enrichment

**Goal**: Configure and execute the Data Quality enrichment pipeline on the user's datasets.

### Steps

**Step 1 — Introduce the phase**

Inform the user that the next step is to configure and run the DQ enrichment pipeline. Explain that it applies DQ-specific objectives to analyze and score the quality of their data.

---

**Step 2 — Select DQ objectives**

Present the available DQ enrichment objectives and ask the user to confirm or adjust. Pre-select all DQ objectives by default:

- ✅ `analyze_quality` — Scores data quality across completeness, validity, and consistency dimensions
- ✅ `dq_gen_constraints` — Generates data quality rules from observed data patterns
- ✅ `dq_sla_assessment` — Assesses data against predefined SLA thresholds
- ✅ `profile` — Computes column-level statistics (nulls, cardinality, min/max, distributions) — recommended as a foundation for DQ analysis

> If the user wants broader enrichment objectives (e.g. `assign_terms`, `analyze_relationships`, `semantic_expansion`), allow it but clarify these are not strictly DQ objectives.

---

**Step 3 — Select categories**

Call `list_enrichment_categories` to retrieve available categories. Ask the user which category or categories they want to associate with this DQ enrichment run.

---

**Step 4 — Confirm datasets**

Ask the user to confirm which datasets (asset names) to run the DQ pipeline on.

- If data was imported in Phase 2.5, suggest those metadata import names as the default and display them.
- If no metadata imports exist in the project, call `search_asset` to list available assets from the connection and let the user select.
- **Do NOT skip this step** — always confirm dataset or metadata import names with the user before proceeding.

---

**Step 5 — Create the MDE asset**

Call `create_or_update_metadata_enrichment_asset` with:
- `project_name` — from Phase 1
- `objectives` — confirmed in Step 2
- `categories` — confirmed in Step 3
- `dataset_names` OR `metadata_import_names` — confirmed in Step 4 (**must not be null**)

---

**Step 6 — Confirm before executing**

Display the full details of the created MDE asset to the user and ask them to confirm before executing.

---

**Step 7 — Execute the MDE job**

Call `execute_metadata_enrichment_asset` with:
- `project_name` — from Phase 1
- `metadata_enrichment_name` — from Step 5

---

**Step 8 — Monitor the job**

Inform the user that the DQ pipeline is now running. Monitor using `get_metadata_enrichment_job_status` with the job ID returned from Step 7:

- Check every **2 minutes**.
- If status is `Completed`, proceed to Step 9.
- If status is `Failed`, display the error and ask the user whether to retry or investigate in the UI.
- If the job has not completed after **10 checks (20 minutes)**, stop monitoring, display the last known status, and ask the user how to proceed.

---

**Step 9 — Display results**

When the job status is `Completed`:

1. Call `get_data_quality_for_asset` for **all** assets in the pipeline.
2. Display results in a **table** with these columns:

| Asset Name | Overall Score | Completeness | Validity | Consistency | Uniqueness | SLA |UI URL |
|---|---|---|---|---|---|---|---|

3. Use the `data_qualiry_mermaid_chart_guide.md` guide to render a bar chart of the results inline in chat.
4. Do **not** create any files for the results — display everything in the chat.

---

## Expected Final Output Example

```
Asset: sales_transactions
- Overall Score: 87%
- Completeness: 92%
- Validity: 85%
- Consistency: 88%
- Uniqueness: 83%
```

Rendered as both a markdown table and a `mermaid` bar chart.

---

## Phase 3: DQ Monitoring

**Goal**: Monitor the Data Quality (AKA DQ) results meet the defined SLA (Service Level Agreements) rules
> Ask for the user approval to proceed with the monitoring of the DQ results
### Steps
**Setp 1 - User approval** 
Ask for the user approval to proceed with the monitoring of the DQ results

**Step 2 - User preferences**
Ask the user how he want to proceed:
- Using the global SLA rules defined in the system
- Using the SLA assesments defined for the assets
- Create new SLA rules
  **Important**:
    - Ask the user if he want to retrieve the SLA rules for all the assets or for a specific asset
    - Always try to retrieve the SLA rules for all the assets unless the user specify specific assets
    - Do not ignore any asset

**Setp 3 - Retrieve the SLA rules**

- Use the `retrieve_dq_slas` tool to retrieve the SLA rules defined in the system and display it to user.
- If the user want to retrieve the SLA rules for a specific asset, use the `retrieve_sla_assessments_by_assets` tool with the asset name as parameter and display it to user.
- Always ask the user if he wants to create a new SLA rules and use it.

**Step 4 - Create the SLA rules [Optional]**
**Important**: This step is only required if no SLA rules are defined in the system or if the user want to create new SLA rules.

- Use the tool `create_data_quality_sla` to create a new SLA rule and follow **Step By Step** the `data_quality_sla_creation_guide.md`.
- Take the new SLA rule and use it to monitor the data quality in **Step 5**.

**Step 5 - Data Quality Monitoring**

- Use the SLA rules retrieved in the previous step to monitor the data quality of all the assets.
- Display the monitoring results to the user.



[//]: # (Copyright [2026] [IBM])
[//]: # (Licensed under the Apache License, Version 2.0 \(http://www.apache.org/licenses/LICENSE-2.0\))
[//]: # (See the LICENSE file in the project root for license information.)