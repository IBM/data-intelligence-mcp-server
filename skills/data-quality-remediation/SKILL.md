---
name: data-quality-remediation
description: Use when the user wants to fetch a GitHub issue containing one or more data quality (DQ) or contract violations — including ODCS schema drift (dropped columns) — and automatically create producer code validation checks with error quarantining, data migration scripts, or remediate each violation.
metadata:
  argument-hint: "<issue-url>"
---

# Data Quality Remediation

Fetch a GitHub issue containing one or more data quality or contract violations and automatically apply the appropriate remediation path for **each** violation detected.

## Input Parameters

- `{{issueUrl}}` - The GitHub issue URL to process
- `{{producerDir}}` - Optional directory where the Producer Code is located (used for non-schema-drift violations)
- `{{outputDir}}` - Optional output directory for the generated folder (default: current directory)

---

## Execution Checklist

At the very start of the run, call `update_todo_list` with at least: `Step 1 — Fetch & Parse Issue`, `Step 1b — Print Issue Summary`, then one item per violation (added once the violation list is known; use the namespaced label that matches the violation type, e.g. `RP-2`, `SD-2`, `GDQ-2`). Do not mark `Step 1b` complete until the summary and violation list have actually been printed in chat.

---

## Step 1 — Fetch & Parse Issue

> **Print heading:** `## 🔍 Step 1 — Fetch & Parse Issue`

- Fetch `{{issueUrl}}` using `gh`. Extract: issue number, title, body, labels, status, created date, lineage.
- **Detect whether the URL is a child issue (direct entry point):**
  - If the fetched issue title begins with `[ODCS Remediation Plan]` **or** `[Data Contract Remediation Plan]`, treat `{{issueUrl}}` as a **direct child entry point** and follow the child entry-point flow below instead of the normal two-stage extraction.
  - Otherwise continue with the normal flow.

### Direct child entry-point flow

- The child issue is already fetched. Extract from it using the **child extraction rules** below:
  - **Suggested Plans text**: the content under `### Suggested Plans` if present; otherwise the content under `## Suggested Remediation Plan`.
  - **Quality Name / column**: the value of `### Quality Name` if present; otherwise parse the child issue **title** for the `DATASET/FIELD` or `DATASET/FIELD: description` pattern and use `FIELD` as the column name (e.g. `BANK_CUSTOMERS/EMAIL: Missing or invalid email address` → column = `EMAIL`).
  - **Plan snippet**: the first fenced code block found under the plan section, regardless of its language tag (if any). If no fenced code block exists anywhere in the child body, report the issue as **unparseable** and stop.
  - **`plan_language`**: `python` if the snippet's fence tag is `python` or `py`; otherwise `other` (Java, pseudo-code, untagged, etc.). Only `python` snippets are executable.
- If no plan section and no fenced code block can be located, report the issue as **unparseable** and stop.
- **Resolve the parent issue:**
  - Collect candidate linked issue URLs from three sources (deduplicate by URL):
    1. Bare GitHub issue URLs and Markdown links in the child issue **body**.
    2. Bare GitHub issue URLs and Markdown links in the child issue **comments**.
    3. **Timeline cross-references**: call `GET /repos/{owner}/{repo}/issues/{number}/timeline` (paginated) and extract `source.issue.html_url` from all events where `event == "cross-referenced"`.
  - Filter the combined candidate list to those whose titles match any DQ/contract violation keyword (`"Data Quality Violation"`, `"Contract Violation"`, `"ODCS Violation"`, `"Schema Drift"`, `"Dropped Column"`).
  - **If exactly one keyword-matching link is found** → that is the parent. Fetch it.
  - **If no keyword-matching links are found but exactly one link is found in total** → treat that single link as the parent. Fetch it.
  - **Otherwise** (no links found, or more than one keyword-matching link found) → report the problem clearly (list all links found and why disambiguation failed) and stop.
- From the resolved parent issue body, extract: `asset_id`, `project_id`, `asset_name` (from `## ODCS Violation Metadata` → `Remediation Asset List`).
- Also extract `lineage` from the parent issue body when present.
- Build a single-item **violation list**:
  - If `plan_language` is `python` → type **remediation plan**.
  - If `plan_language` is `other` → type **general DQ/contract violation**, with the child's Suggested Plans text and snippet attached as a **plan hint** (guidance only, never executed).
- **Execute Step 1b — Print Issue Summary (MANDATORY)** below (print the summary and the violation list as chat text).
- Skip the per-violation `ask_followup_question` prompt and proceed directly to the path matching the violation's type (**Remediation Plan Path** or **General DQ/Contract Violation Path**) for this single violation.

---

### Normal flow

- If the issue URL returns a 404, or the title does not match any DQ/contract violation keyword (`"Data Quality Violation"`, `"Contract Violation"`, `"ODCS Violation"`, `"Schema Drift"`, `"Dropped Column"`), call `ask_followup_question` to confirm with the user and abort if unconfirmed.
- **Collect all violations** using the following two-stage approach:
  - **Stage 1 — child issue lookup (always run):**
    - Fetch all comments on the parent issue using `gh`.
    - Infer child issue URLs from the comments by looking for linked issues whose titles begin with `[ODCS Remediation Plan]` **or** `[Data Contract Remediation Plan]`.
    - For each child URL found:
      - Fetch the child issue using `gh` via the full URL.
      - If the fetch fails (inaccessible or not found), log it as **inaccessible**, record a warning, and continue.
      - Extract using the **child extraction rules**:
        - **Suggested Plans text**: the content under `### Suggested Plans` if present; otherwise the content under `## Suggested Remediation Plan`.
        - **Quality Name / column**: the value of `### Quality Name` if present; otherwise parse the child issue **title** for the `DATASET/FIELD` or `DATASET/FIELD: description` pattern and use `FIELD` as the column name (e.g. `BANK_CUSTOMERS/EMAIL: Missing or invalid email address` → column = `EMAIL`).
        - **Plan snippet**: the first fenced code block found under the plan section, regardless of its language tag (if any).
        - **`plan_language`**: `python` if the snippet's fence tag is `python` or `py`; otherwise `other`. Only `python` snippets are executable.
      - If no plan section and no fenced code block can be located, log the child as **unparseable**, record a warning, and continue.
      - If `plan_language` is `python`, add the child to a `remediation_index` map keyed by the column name (lower-cased for comparison). The child data (Suggested Plans text, snippet, Quality Name) is stored here as the authoritative source for that column's remediation.
      - If `plan_language` is `other`, add the child to a separate `plan_hints` map (same key). Its data is guidance for the General DQ path only and is never executed.
    - If no child issues exist, both maps are empty.
  - **Stage 2 — parent body extraction (always run):**
    - Extract all violations listed in the parent issue body. An issue may contain one or many. For each violation, extract: Contract Name/ID, Asset Name/ID, failed rules, violation details, root cause, recommended remediation steps.
    - Classify each violation by applying the following ordered rules:
      1. **Remediation plan**: derive the candidate `output_column` from the violation (the column being remediated, e.g. from the violated rule or Quality Name field). If that column name (lower-cased) exists as a key in `remediation_index` (i.e. the child plan is a Python snippet), this violation is a **remediation plan** violation. Use the matching child issue as the source of truth for the Suggested Plans text and Python snippet when executing the fix. If the column exists only in `plan_hints`, do not apply this rule — continue to rules 2 and 3 and attach the plan hint to the violation.
      2. **Schema drift (dropped column)**: apply the two-pass approach to the Root Cause Analysis section —
         - **Explicit field** (primary): if `**Dropped Columns**: <name>` is present anywhere in the issue body, treat it as a definitive **schema drift** signal and use it as the dropped column name.
         - **Semantic inference** (fallback): if no explicit field is found, read the root cause text and reason about whether the described failure indicates a column that no longer exists in the schema — regardless of exact wording. Any phrasing that implies a field is absent, unrecognised, invalid in context, or cannot be resolved at query time (e.g. "not recognised", "not valid in the context", "column not found", "field does not exist", "missing field", "unknown column", "not found", "SQL syntax error" caused by a column reference) should be treated as a **schema drift** signal.
         - If either pass concludes a column is missing → **schema drift (dropped column)**. Additionally extract: Project ID, Contract ID, Data Product ID, dropped column name, violated rule IDs.
      3. **General DQ/contract violation**: if neither rule 1 nor rule 2 applies.
- Build a **violation list** — an ordered list of all extracted violations with their type and a one-line summary.
- **Execute Step 1b — Print Issue Summary (MANDATORY)** below (print the summary and the violation list as chat text) **before** any per-violation prompt.
- Process violations **one at a time** in order. For each violation:
  - Print its index, type, and one-line summary.
  - Call `ask_followup_question`:
    - `question`: `Violation N/Total — <one-line summary>. Process this violation?`
    - `suggestion_a`: `Yes — process this violation`
    - `suggestion_b`: `No — skip this violation`
  - If the user selects `suggestion_b`, log it as **skipped** and move to the next violation.
  - If the user selects `suggestion_a`, follow the matching path below. After finishing, move to the next violation until all are resolved.

---

### Step 1b — Print Issue Summary (MANDATORY)

> **Print heading:** `## 📋 Step 1b — Issue Summary`

**You MUST print the Issue Summary and the violation list as chat text before calling `ask_followup_question` or starting any per-violation path. Do not skip, defer, or merge this step. Your first user-facing message after fetching and parsing the issue must be this summary — not a prompt.**

Print it once, after fetching and parsing. Render it as a markdown block with:

- **Issue**: number, title, URL, status, labels, created date.
- **Lineage**: the lineage value, or `not provided`.
- **Parent issue** (direct child entry point only): number, title, URL.
- **Child remediation-plan issues** (normal flow only): each child's number, title and Quality Name/column, with any **inaccessible** or **unparseable** children flagged as warnings.
- **Asset**: `asset_name`, `asset_id`, `project_id` when available.
- **Violations found**: total count and a count per type (remediation plan, schema drift, general DQ/contract).

Then print the **violation list** as a table (`#`, `Type`, `One-line summary`).

---

## Schema Drift Path (for each dropped-column violation)

### SD-2 — Route by Available IDs

> **Print heading:** `## 📦 [Violation N/Total] SD-2 — Route by Available IDs`
- **Environment Discovery & Client Initialization**:
  - Discover the `.env` file location by checking candidates in order:
    1. Workspace root (`./.env` or current working directory `.env`)
    2. Repository root / skill root directory
    3. `ENV_FILE` or `DOTENV_PATH` environment variable if set
  - If no `.env` file is found at the standard locations or if initializing `CPDClient.from_env()` raises a `ValueError` for missing credentials (`CPDAAS_URL`, `CPDAAS_API_KEY` / `CPDAAS_TOKEN`), call `ask_followup_question` asking the user to provide the path to their `.env` file.
  - Instantiate the client with `CPDClient.from_env(env_file=resolved_env_path)` — this loads the resolved `.env` file via plain file I/O, exchanges `CPDAAS_API_KEY` for a bearer token automatically, and returns a ready-to-use client. Re-use the same instance across all violations in the run.
- **Routing decision** — evaluate the IDs extracted from the issue in Step 1:
  - **If `DATA_PRODUCT_ID` is present and non-empty** → follow the **Data Product Exchange path** (steps DP-3 through DP-9 below).
  - **Else if both `CONTRACT_ID` and `PROJECT_ID` are present and non-empty** → follow the **Contract Direct path** (steps CD-3 through CD-8 below).
  - **Otherwise** (neither set of IDs is available) → log this violation as **failed** with the message: `"Cannot remediate: neither Data Product ID nor (Contract ID + Project ID) found in the issue body."` Move to the next violation.

---

## Schema Drift — Contract Direct Path (CD-3 through CD-8)

> Used when `DATA_PRODUCT_ID` is absent but `CONTRACT_ID` and `PROJECT_ID` are both present.

### CD-3 — Fetch Contract

> **Print heading:** `## 📄 [Violation N/Total] CD-3 — Fetch Contract`

- Call `client.get_contract(PROJECT_ID, CONTRACT_ID)`.
- From the response, extract:
  - `contract_yaml` — the raw ODCS YAML string.
  - `name`, `server_mappings` — preserved unchanged for the PUT payload later.
- Parse `contract_yaml` in memory (using `yaml.safe_load`) to inspect its structure.
- If the API call fails (non-200), log the violation as **failed**, surface the HTTP error, and move to the next violation.

### CD-4 — Analyze & Generate Change Summary

> **Print heading:** `## 🧮 [Violation N/Total] CD-4 — Analyze & Generate Change Summary`

- Inspect the parsed ODCS document for every reference to the dropped column(s):
  - **Property-level** (`schema[*].properties[*]`): entries whose `name` equals a dropped column.
  - **Property quality rules** (`schema[*].properties[*].quality[*]`): rules on surviving properties whose `name` or `query` references a dropped column.
  - **Table-level quality rules** (`schema[*].quality[*]`): rules whose `name` or `query` references a dropped column.
- If multiple columns are dropped in this violation, collect all affected entries for every dropped column before proceeding.
- Show the user:
  - Properties to be removed (per dropped column)
  - Quality rules to be removed (property-level and table-level, per dropped column)
  - Version bump, e.g. `1.0.0` → `1.0.1`

### CD-5 — Request User Confirmation

> **Print heading:** `## ✅ [Violation N/Total] CD-5 — Request User Confirmation`

- Present the full change summary for this violation.
- Call `ask_followup_question` with:
  - `question`: "Apply these changes to the contract for violation N?"
  - `suggestion_a`: "Yes – apply the changes"
  - `suggestion_b`: "No – skip this violation"
  - `suggestion_c`: "Modify – let me adjust first"
- If the user selects `suggestion_b`, skip to the next violation.
- If the user selects `suggestion_c`, wait for the user to describe adjustments, apply them to the in-memory document, and re-present the summary before proceeding.

### CD-6 — Build Updated Contract YAML

> **Print heading:** `## ✏️ [Violation N/Total] CD-6 — Build Updated Contract YAML`

- Call `CPDClient.build_contract_yaml_patch(contract_yaml, dropped_columns)` — this static method:
  1. Parses the ODCS YAML string.
  2. Removes every dropped column's property entry from `schema[*].properties`.
  3. Removes every quality rule (property-level and table-level) whose `name` or `query` references a dropped column.
  4. Increments the patch component of the top-level `version` field.
  5. Returns the updated YAML string.
- Construct the PUT payload:
  ```
  {
    "name": <name from GET response>,
    "contract_yaml": <updated YAML string from build_contract_yaml_patch>,
    "server_mappings": <server_mappings from GET response, unchanged>
  }
  ```
  Include `"type"` in the payload only if it was present in the GET response.

### CD-7 — PUT Updated Contract

> **Print heading:** `## 🚀 [Violation N/Total] CD-7 — PUT Updated Contract`

- Call `client.update_contract(PROJECT_ID, CONTRACT_ID, payload)`.
- If the API call fails (non-200), log the violation as **failed**, surface the HTTP error with the full response body, and move to the next violation.
- On success, confirm to the user: `"Contract {CONTRACT_ID} updated successfully (version bumped to {new_version})."`

### CD-8 — Verify and Report

> **Print heading:** `## 📊 [Violation N/Total] CD-8 — Verify and Report`

- Re-fetch the contract via `client.get_contract(PROJECT_ID, CONTRACT_ID)`.
- Parse the returned `contract_yaml` and confirm:
  - Every dropped column's property entry is absent from `schema[*].properties`.
  - No quality rule referencing any dropped column remains (property-level or table-level).
- If verification passes, report a clean success.
- If any dropped column is still present, surface a warning:
  > ⚠️ **Verification failed** — the PUT was accepted but the `{COLUMN}` property is still present in the stored contract. Please review and re-apply manually.
- Note the result in the running remediation summary.

---

## Schema Drift — Data Product Exchange Path (DP-3 through DP-9)

> Used when `DATA_PRODUCT_ID` is present and non-empty.

### DP-3 — Check for Pending Draft

> **Print heading:** `## 🔎 [Violation N/Total] DP-3 — Check for Pending Draft`

- If the response contains a non-empty `drafts` array, **pause this violation**, inform the user:
  > "Violation N: Data product `{DATA_PRODUCT_ID}` already has an open draft. Please publish or discard it before applying remediation."
  - Call `ask_followup_question`:
    - `suggestion_a`: "Skip this violation and continue with the remaining ones"
    - `suggestion_b`: "Abort all remaining violations"
  - Act on the user's choice; if skipping, move to the next violation.
- If `drafts` is empty, extract `latest_release.id` and proceed.

### DP-4 — Fetch Latest Release

> **Print heading:** `## 📄 [Violation N/Total] DP-4 — Fetch Latest Release`

- Call `GET {CPDAAS_URL}/data_product_exchange/v1/data_products/{DATA_PRODUCT_ID}/releases/{LATEST_RELEASE_ID}` using `CPDClient.get_data_product_release()`.
- The full release JSON contains `contract_terms[*].schema[*].properties` (property-level quality rules) and `contract_terms[*].schema[*].quality` (table-level quality rules).

### DP-5 — Analyze & Generate Change Summary

> **Print heading:** `## 🧮 [Violation N/Total] DP-5 — Analyze & Generate Change Summary`

- Identify every rule in the release that references the dropped column(s) for this violation:
  - **Property-level** (`contract_terms[*].schema[*].properties[*]`): properties whose `name` equals a dropped column, plus any quality rule inside another property whose `name` or `query` references the column.
  - **Table-level** (`contract_terms[*].schema[*].quality`): any rule whose `name` or `query` references the column.
- If **multiple columns** are dropped within the same data product violation, handle them all iteratively in this step: collect all affected properties and rules for every dropped column before proceeding.
- Show the user:
  - Properties to be removed (per dropped column)
  - Rules to be removed entirely
  - The incremented revision, e.g. `1.0.0` → `1.0.1`

### DP-6 — Request User Confirmation

> **Print heading:** `## ✅ [Violation N/Total] DP-6 — Request User Confirmation`

- Present the full change summary for this violation.
- Call `ask_followup_question` with:
  - `question`: "Apply these changes to the contract for violation N?"
  - `suggestion_a`: "Yes – apply the changes"
  - `suggestion_b`: "No – skip this violation"
  - `suggestion_c`: "Modify – let me adjust first"
- If the user selects `suggestion_b`, skip to the next violation.

### DP-7 — POST Draft Shell

> **Print heading:** `## 🚀 [Violation N/Total] DP-7 — Create Draft Shell`

- Call `CPDClient.build_draft_post_payload(release)` to produce a minimal payload containing only `asset.container.id`, `data_product.id`, and the incremented `version`.
- Call `CPDClient.create_data_product_draft(data_product_id, payload)` to POST the draft.
- From the response, extract:
  - `DRAFT_ID` — top-level `id` field
  - `CONTRACT_TERMS_ID` — `contract_terms[0].id`

### DP-8 — PATCH Contract Terms

> **Print heading:** `## 🩹 [Violation N/Total] DP-8 — Patch Contract Terms`

- Call `CPDClient.build_contract_terms_patch(release, dropped_columns)` to produce the PATCH body: the cleaned `contract_terms[0]` with every dropped column's property and all referencing rules removed, and `id`, `asset`, `contract_test` stripped.
- Call `CPDClient.patch_draft_contract_terms(data_product_id, DRAFT_ID, CONTRACT_TERMS_ID, patch)`.

### DP-9 — Verify and Report

> **Print heading:** `## 📊 [Violation N/Total] DP-9 — Verify and Report`

- After the PATCH call returns, re-fetch the draft (GET `.../drafts/{DRAFT_ID}`) and compare the properties list against the expected post-patch state (i.e. the dropped column must be absent, and all referencing quality rules must be gone).
- If any dropped column still appears in `contract_terms[0].schema[*].properties` in the re-fetched draft, this is a **known partial-update bug** in the Data Product Exchange PATCH endpoint. Surface it to the user:
  > ⚠️ **Known API bug** — the PATCH was accepted (HTTP 200) but the `{COLUMN}` property was not removed from the stored draft. This is a known issue tracked at https://github.ibm.com/wdp-gov/tracker/issues/356156. The quality-rule removals were applied correctly.
  
  Replace `{COLUMN}` with the actual column name(s) still present.
- If the re-fetch confirms all dropped columns are absent and all referencing rules are removed, report a clean success.
- Note the result in the running remediation summary (used to update the issue in the final step).
- Remind the user to review and publish the new draft once all violations are processed.

---

## Remediation Plan Path (for each remediation plan)

### RP-2 — Present Plan and Request Approval

> **Print heading:** `## 📋 [Violation N/Total] RP-2 — Present Remediation Plan`

- Display the following for the current remediation-plan violation:
  - **Violation explanation** (from the parent issue body)
  - **Quality Name** (column to be remediated)
  - **Suggested Plan** (from the plan section extracted by the child extraction rules)
  - **Python snippet** — only violations whose child plan is a Python snippet (`plan_language == python`) reach this path. Display the snippet in a ```` ```python ```` fenced block labelled `**Suggested Plan (Python, used for execution)**`. It must define a callable `task(input_data)`; if it defines a differently named function, wrap or rename it to `task` and show the result. Store this function as the snippet to execute in RP-3.

### RP-3 — Execute Fix

> **Print heading:** `## ▶️ [Violation N/Total] RP-3 — Execute Fix`

- Extract from the remediation-plan issue:
  - `output_column`: derived using the child extraction rules — from `### Quality Name` if present, otherwise from the title `DATASET/FIELD` pattern. Take the part before the `/` if a `/` is present; otherwise the full value (e.g. `EMAIL` from `BANK_CUSTOMERS/EMAIL: description`, or `COUNTRY_NAME` from `COUNTRY_NAME`).
  - `input_column`: the input column the pseudo-code reads from (infer it from the pseudo-code logic, e.g. the key it looks up in `input_data`)
  - `asset_id` and `project_id`: from the parent issue body (`## ODCS Violation Metadata` → `Remediation Asset List` → `Asset ID`, and `Project ID`)
  - `asset_name`: from the parent issue body (`## ODCS Violation Metadata` → `Remediation Asset List` → `Asset Name`)
- Fetch only the **first batch** of the dataset to read its schema **before** generating the executor script — do not download the whole table for this. Use `with contextlib.closing(client.iter_asset_data_flight(asset_id, project_id)) as batches: first = next(batches, None)` (instance method on the `CPDClient` instance) and take the schema from `first.schema`. If `first` is `None` the asset has no rows: log the violation as **failed** with a clear message and stop. Inspect each field's metadata in that schema for `columnPrimaryKey == 'true'` to identify PK columns:
  - If exactly one PK column is found: use it automatically and inform the user.
  - If multiple PK columns are found: present them as options via `ask_followup_question` and let the user choose. Always include a final option `suggestion_d`: `"Another — let me type in the column name"`. If the user chooses this option, wait for them to type a column name and use that.
  - If no PK column is found: list all column names as suggestions in `ask_followup_question` (up to three explicit column suggestions, then `suggestion_d`: `"Another — let me type in the column name"`). If the user chooses the "Another" option, wait for them to type a column name and use that.
- **Resolve the `.env` file path.** Check whether `<skill_dir>/.env` exists (where `<skill_dir>` is the directory containing this `SKILL.md`):
  - If it **exists** — use it. Inform the user: `"Using .env at <path>."` and proceed.
  - If it **does not exist** — call `ask_followup_question`:
    - `question`: `"No .env file found at <skill_dir>/.env. Where are the credentials?"`
    - `suggestion_a`: `"Use .env from the repository root"`
    - `suggestion_b`: `"I will provide the full path to my .env file"`
  - If `suggestion_a`: set `env_path = <repo_root>/.env`. If that file also does not exist, log the violation as **failed** with a clear message and stop.
  - If `suggestion_b`: wait for the user to type the path. Accept both absolute paths and paths relative to the repository root — resolve relative paths against `<repo_root>` before checking existence. Use the resolved absolute path as `env_path`. If the file does not exist, log the violation as **failed** with a clear message and stop.
  - Store the resolved `env_path` and reuse it for all subsequent violations in the same run — do **not** ask again.
- **Read `DB_TYPE`** from the resolved `.env` file (parse it with plain line-by-line I/O — no external library). If `DB_TYPE` is absent or empty, default to `db2`. Supported values: `db2`. If an unrecognised value is found, log the violation as **failed** with the message `"Unsupported DB_TYPE '<value>'. Supported: db2."` and stop.
- Warn the user explicitly that the code about to run may have irreversible side effects (for example database writes, API calls, or data mutations). Include the detected `DB_TYPE` in the warning, e.g. `"DB type: db2"`.
- Call `ask_followup_question`:
  - `question`: `Apply this remediation plan for violation N (Quality Name: <name>)?`
  - `suggestion_a`: `Yes — execute the Python implementation`
  - `suggestion_b`: `No — skip this violation`
  - `suggestion_c`: `Let me edit the Python first — paste the modified snippet and I will use it instead`
- If the user selects `suggestion_b`, log the violation as **skipped** and move to the next violation.
- If the user selects `suggestion_c`, wait for the user to paste a replacement Python snippet, then use that snippet for execution.
- Generate a self-contained Python executor script on the fly. The script must:
  1. Open with a comment block listing the runtime dependencies required to execute it — these are **not** part of the skill's own `requirements.txt` but must be installed in the environment where the script runs. For `db2` the comment must read:
     ```
     # Runtime dependencies (install before running):
     #   pip install ibm-db pyarrow requests
     ```
     Then resolve the skill directory and make all imports path-independent:
     ```python
     import sys, pathlib
     _skill_dir = pathlib.Path(__file__).resolve().parent
     sys.path.insert(0, str(_skill_dir))
     ```
     Import only the CPD client:
     ```python
     from scripts.api.cpd_client import CPDClient
     ```
  2. Generate an `_load_env(path)` helper that parses the `.env` file with plain line-by-line I/O and populates `os.environ` without overwriting already-set vars. Hard-code `_ENV_PATH` as the resolved `env_path` string literal (set at generation time) and call `_load_env(_ENV_PATH)` immediately so all subsequent code sees the loaded vars. Raise an `EnvironmentError` if the file does not exist.
  3. Generate a **`_db_connect()` function** appropriate for the detected `DB_TYPE`. Add a `# DB_TYPE=<value>` comment above it for traceability. For `db2` (the default): use `ibm_db` / `ibm_db_dbi` to build a TCPIP connection string from the `DB2_*` env vars (`DB2_DATABASE`, `DB2_HOST`, `DB2_PORT` defaulting to `50000`, `DB2_USER`, `DB2_PASSWORD`), append `SECURITY=SSL;` when `DB2_USE_SSL=true`, and set `CURRENTSCHEMA` when `DB2_SCHEMA` is non-empty. Read `DB2_SCHEMA` into `_DB_SCHEMA` and raise an `EnvironmentError` if it is empty. Raise an `EnvironmentError` listing any missing required `DB2_*` vars before attempting to connect. Derive the qualified table name as `_DB_SCHEMA + "." + ASSET_NAME` (substituted at generation time).
  4. Instantiate `CPDClient` with `CPDClient.from_env(env_file=_ENV_PATH)`. Stream the dataset with `for batch in client.iter_asset_data_flight(asset_id, project_id):` (instance method — do **not** call it as a standalone function), which yields one `pyarrow.RecordBatch` at a time. Do **not** load the whole table into memory. Access columns by name via `batch.column(col_name).to_pylist()`. Do not use the connections REST API — it is capped at 100 rows.
  5. For each batch, and for each row index within it, build an `input_data` dict keyed by column name, call the `task(input_data)` function (the Python snippet from RP-2, or the user's pasted replacement), and append `(new_value, pk_value)` to a `pairs` buffer using the selected PK column. If the plan is an imputation (that is, the Suggested Plans text contains `imputed` or `imputation`, case-insensitive), only include rows where the current value of `output_column` is `None` or an empty or whitespace-only string. Embed verbatim, as the callable `task(input_data)` function, the Python snippet shown in RP-2 (or the user's pasted replacement if `suggestion_c` was chosen).
  6. Keep a `sample` list of the first 5 `(pk_value, old_value, new_value)` triples (old value from the current batch's column list at the same row index) and a running `total` count of collected pairs. Immediately before the first database write (or after the stream ends, if nothing was written yet), print `sample` as a table with columns `pk_value`, `old_value`, `new_value`. Once the stream is exhausted, if `total` is greater than 5, print `… and N more rows` (where `N = total - 5`) directly before the final count line. Print nothing else between the sample rows and these two lines.
  7. Write in chunks while streaming. Whenever `len(pairs)` reaches `CHUNK_SIZE = 1000`, and once more for the remainder after the stream ends, connect with `_db_connect()` (once, on the first flush), execute `UPDATE <qualified_table> SET "<output_column>" = ? WHERE "<pk_column>" = ?` via `cursor.executemany(sql, pairs)`, call `connection.commit()`, and clear `pairs`. Committing per chunk keeps transaction-log usage bounded and allows partial progress if the job is interrupted; clearing the buffer keeps memory bounded to one batch plus one chunk. Close the connection when finished.
  8. After the stream is exhausted and the final chunk is committed, print `Updated N row(s) in <qualified_table> (column: <output_column>)` with `N = total`.
- Execute the generated script and capture stdout and stderr.
- If execution succeeds:
  - Parse the captured stdout to extract the sample rows (lines between the header row and the `… and N more rows` / count line) and the final count line.
  - Render the sample as a formatted markdown table in the chat response (not as a raw stdout block), with a heading `### Imputation Preview (up to 5 rows)`.
  - Render the final count line (`Updated N row(s) in …`) as a bold line beneath the table.
  - If stderr is non-empty, show it in a collapsed `<details>` block labelled `Script output`.
  - Log the violation as **remediated**.
- If execution fails: log it as **failed**, print the error output, and surface actionable guidance that distinguishes missing dependencies, missing env vars (`CPDAAS_URL`, `DB2_HOST`, and so on), and other failures.

### RP-4 — Summary

> **Print heading:** `## ✅ [Violation N/Total] RP-4 — Summary`

- Record the remediation-plan violation outcome as one of **remediated**, **skipped**, **failed**, **inaccessible**, or **unparseable**.
- Post the current violation outcome as a GitHub comment on that child remediation-plan issue.

---

## General DQ/Contract Violation Path

### GDQ-2 — Apply Producer Code Validation & Quarantining

> **Print heading:** `## 🛠️ [Violation N/Total] GDQ-2 — Apply Producer Code Validation & Quarantining`

- Check whether the user supplied a real directory path for the producer code location. A real path is any value that is NOT the literal string `{{producerDir}}` and is NOT empty.
  - If a real path was supplied, search within that directory.
  - If no real path was supplied, call `ask_followup_question` **once** for the first violation that needs it; reuse the answer for subsequent violations in the same issue:
    - `suggestion_a`: "Search for the producer code in the current directory"
    - `suggestion_b`: "I will provide the path to the producer code"
- If the user selects `suggestion_b`, wait for the user to type a path, then use that path.
- Locate the producer code responsible for writing/ingesting the data:
  - The producer file is provided as lineage
  - If lineage is not provided, search for the ingestion/transformation logic in the repo
- **Apply Validation Checks (Do NOT Mutate/Fix Data Inline in Producer Code):**
  - Implement explicit validation checks against the data contract and data quality rules for the affected column(s).
  - Do not auto-correct, impute, or modify invalid data values inline to force them to pass.
  - **Direct Write Control**: Logging or warnings alone are strictly insufficient. Validation must directly control the actual write operation — only validated/valid records proceed to the destination write/insert operation, while invalid records must be prevented from being written.
  - **Quarantine / Error Preservation**: Preserve rejected records along with their validation failure reasons for inspection and remediation. Route rejected records to an appropriate error output or quarantine mechanism (e.g., quarantine table/dataset, dedicated rejection file/CSV, or error DataFrame/output log with failed records and failure reasons).
- Apply the changes to the producer code using `apply_diff`.
- Before applying any code change, explain what the change does and why, in plain English, in the chat:
  - The specific validation rules being enforced
  - How validation directly controls the write operation (excluding invalid records from target persistence)
  - How rejected records and their failure reasons are preserved in quarantine/error output

### GDQ-3 — Write Data Migration Script

> **Print heading:** `## 📝 [Violation N/Total] GDQ-3 — Write Data Migration Script`

- If the violation carries a **plan hint** (a non-Python child plan from `plan_hints`), use its Suggested Plans text and snippet only as guidance for *how existing bad rows are repaired* in the migration script (e.g. fallback sources, placeholders). Do **not** execute the snippet, and do **not** put its imputation or fallback logic in the producer code — GDQ-2 forbids inline correction. Show the plan hint in chat and state how the migration script differs from it, if at all.
- Use the output folder `issue-{number}-{sanitized-title}` (lowercase, alphanumeric + hyphens, title capped at 50 chars) under `{{outputDir}}` (default: current directory). Create it once; reuse it for all violations in the same issue.
- Before writing the script, explain in the chat:
  - What data is violating the contract and why
  - What the script will do to fix it (which rows/columns are updated and how)
- Create `{folder}/fix_issue_{number}_{description}_violation_{N}.{ext}` — include the violation index `N` in the filename so multiple scripts from the same issue do not collide. Infer the file extension from the producer code found in GDQ-2.

### GDQ-4 — Run the Data Migration Script

> **Print heading:** `## ▶️ [Violation N/Total] GDQ-4 — Run Data Migration Script`

- Call `ask_followup_question`:
  - `suggestion_a`: "Yes, run the migration script now"
  - `suggestion_b`: "No, skip running this script"
- If the user selects `suggestion_a`, execute the migration script.
- If the user selects `suggestion_b`, skip and proceed.

## GDQ-5 — Create a PR

> **Print heading:** `## 🔀 GDQ-5 — Create a Pull Request`

- Runs **once** after all general DQ/contract violations have been processed (schema drift violations have their own per-violation reporting in DP-9/CD-8 and do not contribute to this PR).
- If no general DQ violations were processed (all violations were schema drift), skip this step entirely.
- Create a new Git branch named `fix/issue-{number}-{sanitized-title}`, switch to it, commit all generated files (producer code validation/quarantine fixes + migration scripts from all violations).
- Use the `create_pr_workflow` to open the Pull Request. The PR description must list every violation addressed and reference the issue number.
- Capture the URL of the newly created PR — it is required in GDQ-6.

## GDQ-6 — Post Issue Summary Comment

> **Print heading:** `## 💬 GDQ-6 — Post Issue Summary Comment`

- Runs **once** after GDQ-5 completes, so the PR URL is available to include in the comment.
- If no general DQ violations were processed (all violations were schema drift), skip this step entirely.
- Post a **new GitHub issue comment** on `{{issueUrl}}` using `gh issue comment`. The comment **must** include:
  - A `## Remediation Summary` heading.
  - One numbered entry per violation processed in this run, each containing:
    - The violation title (rule name) and its final status (**remediated**, **skipped**, **failed**, **inaccessible**, or **unparseable**).
    - **Producer Code Validation**: what was changed in the producer file and the path to the quarantine output.
    - **Migration Script**: the generated script filename and a one-line description of what it does.
  - A closing line referencing the PR URL from GDQ-5, e.g. `"Pull request opened: <PR URL>"`.
- This step is **mandatory** whenever GDQ-5 runs. Do not skip it even if some violations were skipped or failed.

---

## Notes

- **Never** call `ask_followup_question` for a violation before the Issue Summary and violation list (Step 1b) have been printed in chat in the current run.
- At the start of every step, print the bold heading shown in each step (with the `[Violation N/Total]` counter) so the user always knows which violation and step is running.
- Before applying any code change, explain what the change does and why, in plain English, in the chat.
- Always summarize each step as a markdown block before proceeding.
- Reference the issue number and violation index in all generated comments and file names.
- If a violation cannot be fully remediated (e.g. open draft, inaccessible child issue, unparseable child issue, execution failure, user skip), log it in the running and final summaries with the appropriate status and continue with the rest unless the user explicitly aborts.
- Authentication tokens obtained in the schema drift path should be reused across all schema drift violations in the same run to avoid redundant auth calls.
- For all `gh` command calls (fetching issues, posting issue comments, creating PRs): run the command as-is first. Only if the call fails (non-zero exit code or an authentication error in the output) should you re-run it with the `GITHUB_TOKEN` from the skill `.env` injected as an environment variable (e.g. `GITHUB_TOKEN=<value> gh ...`). The `.env` file lives inside the skill directory alongside this `SKILL.md`.

## Implementation Notes

- Uses `scripts/api/cpd_client.py` → `CPDClient` for all API communication. This file is located in the same directory as this `SKILL.md`. All generated scripts must resolve its path using `pathlib.Path(__file__).resolve().parent` and insert it into `sys.path` before importing — see RP-3 for the exact pattern.
  - `from_env(env_file=_ENV_PATH)` *(classmethod)* — load the resolved `.env` path and authenticate; call once, reuse the instance. `_ENV_PATH` is the path resolved during the `.env` discovery step.
  - **Data Product Exchange path** (when `DATA_PRODUCT_ID` is present):
    - `get_data_product(data_product_id)` — DP-3
    - `get_data_product_release(data_product_id, release_id)` — DP-4
    - `build_draft_post_payload(release)` *(static)* — DP-7: minimal POST payload
    - `create_data_product_draft(data_product_id, payload)` — DP-7: POST
    - `build_contract_terms_patch(release, dropped_columns)` *(static)* — DP-8: PATCH body (accepts a list of dropped columns)
    - `patch_draft_contract_terms(data_product_id, draft_id, contract_terms_id, patch)` — DP-8: PATCH
  - **Contract Direct path** (fallback when `DATA_PRODUCT_ID` is absent but `CONTRACT_ID` + `PROJECT_ID` are present):
    - `get_contract(project_id, contract_id)` — CD-3: fetch ODCS contract via `GET /data_quality/v4/projects/{project_id}/data_contracts/{contract_id}`
    - `build_contract_yaml_patch(contract_yaml, dropped_columns)` *(static)* — CD-6: remove dropped column properties and referencing quality rules from the ODCS YAML string, bump patch version
    - `update_contract(project_id, contract_id, contract_data)` — CD-7: write back via `PUT /data_quality/v4/projects/{project_id}/data_contracts/{contract_id}`
- Requires `CPDAAS_AUTH_URL`, `CPDAAS_API_KEY`, and `CPDAAS_URL` in the resolved `.env` file. For the Remediation Plan path additionally requires `DB2_HOST`, `DB2_DATABASE`, `DB2_USER`, `DB2_PASSWORD`, `DB2_SCHEMA` (and optionally `DB2_PORT`, `DB2_USE_SSL`). `DB_TYPE` defaults to `db2` if absent.

## Error Handling

- API authentication failures
- Contract not found
- Neither `DATA_PRODUCT_ID` nor (`CONTRACT_ID` + `PROJECT_ID`) present in the issue — log violation as **failed** and continue
- `get_contract` API failure — log violation as **failed**, surface HTTP error, and continue
- `update_contract` API failure — log violation as **failed**, surface HTTP error with full response body, and continue
- `build_contract_yaml_patch` parse failure (invalid YAML in `contract_yaml`) — log violation as **failed** and continue
- Data product has an open draft — pause that violation, offer skip or abort
- Child remediation-plan issue fetch failures — mark as **inaccessible** and continue
- Child remediation-plan issues without any fenced code block — mark as **unparseable** and continue
- Child remediation-plan issues whose snippet is not tagged `python`/`py` — not an error; the violation is processed on the General DQ path with the plan as a hint and the snippet is never executed
- Multiple columns dropped within a single violation — handle all iteratively in CD-4/CD-6 (Contract Direct) or DP-5/DP-8 (Data Product Exchange)
- Multiple violations of any supported type in a single issue — process each in order
- Missing dependencies or environment variables required by the remediation-plan executor (distinguish: missing `.env` file, missing `DB_TYPE` key, unrecognised `DB_TYPE` value, missing DB connection vars)
- `.env` file not found at skill dir, repo root, or user-supplied path
- Network errors
- Issue URL returns 404 or does not match any DQ/contract violation keyword