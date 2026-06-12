---
name: data-product-creation
description: Use this skill when a user wants to create, publish, or set up a new data product in IBM watsonx.data intelligence (wxdi) / Data Product Hub. Trigger when the user says things like "create a data product", "publish a dataset as a data product", "I want to share this data as a product", "set up a data product for X", "onboard this asset to the catalog as a product", or "build a data product from my data". This skill uses a file-based specification approach where data product definitions are created as JSON/YAML files in the workspace, reviewed and refined iteratively, then batch-submitted to DPH. This enables version control, collaboration, and reusability.
---
 
# Data Product Creation Skill (File-Based Specification)
 
You are helping a user create and publish a high-quality data product in IBM watsonx.data intelligence (Data Product Hub) using an **Infrastructure-as-Code** approach. Instead of making iterative API calls, you will generate specification files that define the data product, allow the user to review and refine them, then batch-submit to DPH.
 
## Core Paradigm: File-Based Specification
 
**File-Based Approach (Use This):**
```
Human ↔ LLM ↔ Workspace Files → MCP Tools (5-7 batch API calls)
```
 
**Benefits:**
- **Version Control**: Files can be committed to Git, tracked, branched, and merged
- **Collaboration**: Multiple stakeholders can review and edit specification files
- **Reusability**: Templates can be created for common data product patterns
- **Validation**: Files can be validated before any API calls are made
- **Transparency**: Complete data product definition visible in one place
- **Iteration**: Refine specifications without touching the DPH server
---
 
## Workflow Overview
 
This skill has **five phases**. Follow them in order:
 
1. **Discovery & Requirements** (conversational + MCP tools)
2. **Specification Generation** (create files in workspace)
3. **Iterative Refinement** (user reviews/edits files)
4. **Validation** (AI code review of files)
5. **Publication** (batch MCP tool calls)
---
 
## Optional Calls
 
WHEN: User asks about available data contracts (e.g., "What data contracts are available?")
 
CALL: `list_data_product_contract_templates` tool

WHEN: User asks about available business domains (e.g., "What domains are available?")

CALL: `list_data_product_business_domains` tool

WHEN: User asks about available delivery methods for a data asset (e.g., "What delivery methods are available for asset_name?")

CALL: `find_data_product_delivery_methods_based_on_connection` tool

---
 
## Phase 1 — Discovery & Requirements
 
**Goal:** Understand what the user wants to create and check for duplicates.
 
### 1.1 Deduplication Check

<Steps>
<Step>

1. Use `search_data_products` with the user's intended product name/topic

</Step>
<Step>

2. If matches found:
   - Use `get_data_product_details` to inspect them
   - Use `get_data_product_contract` to check their contracts
   - Present findings: "A data product named 'Customer 360' already exists. It includes..."
   - **If an existing product meets their need, stop here and direct them to it**

</Step>
<Step>

3. If nothing relevant exists, proceed to requirements gathering

</Step>
</Steps>

### 1.2 Requirements Gathering
 
Have a focused conversation to capture:
 
**Essential Information:**
- **Name & Description**: What is this data product called (max length: 256)? What does it do (max length: 5000)?
- **Data Source Type**: 
  - Asset from catalog/project (use `search_asset` to find)
  - URL-based data source
- **Business Domain**: Which domain (Finance, HR, Operations, etc.)?
**Optional Information (can be refined later):**
- **Required Fields**: Specific columns or topics they care about?
- **Quality SLAs**: Freshness, completeness, validity thresholds?
- **Delivery Methods**: Flight (programmatic), download, or both?
- **Contract Type**: URL contract, template-based, or custom?
**Document assumptions clearly** — the user will review them in the specification files.
 
---
 
## Phase 2 — Specification Generation
 
**Goal:** Create structured specification files in the workspace that define the complete data product.

### Template Placeholder Conventions

When creating specification files, use the template files in [`templates/`](templates/) as a guide. Templates use descriptive placeholders to indicate how values should be populated:

- **`<USER_PROVIDED_*>`** - Value must be collected from user through conversation
- **`<POPULATED_BY_*_TOOL>`** - Value automatically populated by MCP tool call (AI agent populates, user does not modify)
- **`<USER_PROVIDED_OR_SELECTED_*>`** - Value either provided by user or selected from a list presented to user
- **`<OPTIONAL_*>`** - Optional field that may be populated if available from tool responses
- **`<MUST_MATCH_*>`** - Value must match a corresponding value from another specification file

**Examples:**
- `<USER_PROVIDED_PRODUCT_NAME>` → Ask user: "What would you like to name this data product?"
- `<POPULATED_BY_SEARCH_ASSET_TOOL>` → Use the asset_id returned by `search_asset` tool
- `<USER_PROVIDED_OR_SELECTED_FROM_LIST>` → Present domain list and ask user to choose
- `<OPTIONAL_FROM_GET_ASSET_DETAILS>` → Include quality scores if returned by `get_asset_details`
- `<MUST_MATCH_ASSET_NAME_FROM_MANIFEST>` → Use the exact asset_name from assets_manifest.json

**Important:** Replace ALL placeholders with actual values when creating specification files. Do not leave placeholder text in the generated files.
 
### 2.1 Create Workspace Directory

<Steps>
<Step>
1. Create a directory structure for this data product:

```
.data_products/<product-name>/
├── data_product_spec.json       # Core product definition
├── assets_manifest.json         # Assets to include
├── delivery_config.json         # Delivery methods per asset
├── contract_spec.json           # Contract definition
└── README.md                    # Human-readable summary
```
</Step>
<Step>
2. Use whatever file-writing capability your environment provides to create each file. Use the product name (slugified) as the directory name.
</Step>
</Steps>
 
### 2.2 File: `data_product_spec.json`
 
**Purpose:** Core data product metadata
 
**Schema:** See [template](templates/data_product_spec.json)
 
**Populate from Phase 1 requirements.** Mark assumptions clearly.
 
### 2.3 File: `assets_manifest.json`
 
**Purpose:** Define which assets to include in the data product
 
**For Asset-Based Data Products:**
 
Use `search_asset` to find candidate assets, then `get_asset_details` to retrieve metadata.

**Schema:** See [template](templates/assets_manifest_asset_based.json)
 
**For URL-Based Data Products:**
 
**Schema:** See [template](templates/assets_manifest_url_based.json)
 
**Include multiple assets if needed.** Document why each asset was selected.
 
### 2.4 File: `delivery_config.json`
 
**Purpose:** Define how consumers will access each asset
 
**Schema:** See [template](templates/delivery_config.json)
 
**For URL-based products:** Delivery method is automatically "Open URL" — no configuration needed.
 
**Leave method_id as placeholder** if not yet discovered. Note that `find_data_product_delivery_methods_based_on_connection` will be called during publication to get actual IDs.
 
### 2.5 File: `contract_spec.json`
 
**Purpose:** Define the data contract (SLAs, terms, usage guidelines).

**Choose the contract type based on user needs.** URL contracts are fastest; custom contracts are most detailed.
 
**Three Contract Types:**
 
**A. URL Contract (simplest):**

**Schema:** See [template](templates/contract_url.json)
 
**B. Template-Based Contract:**

**Schema:** See [template](templates/contract_template.json)

As the user adds any customizations, update the `customizations` object in the `contract_spec.json` file.
 
**C. Custom Contract (most flexible):**

**Schema:** See [template](templates/contract_custom.json)

Report to user that this is a sample contract and ask for real values.

 
### 2.6 File: `README.md`
 
**Purpose:** Human-readable summary for review
 
```markdown
# Customer 360 Data Product
 
## Overview
Comprehensive customer data for analytics and reporting.
 
## Business Context
- **Domain**: Accounting and finance
- **Use Case**: Enable marketing and sales teams to access unified customer profiles
 
## Assets Included
1. **customer_master_table** (Catalog: catalog-xyz-789)
   - Master customer table with demographics
   - Quality: 95% complete, 98% valid
   - Key columns: customer_id, name, email, segment
 
## Delivery Methods
- **Use Flight service**: Programmatic access for data science
- **Download**: Manual download for ad-hoc analysis
 
## Contract
- **Type**: Template-based (Standard Data Product Contract)
- **SLAs**: Daily refresh, 95% completeness
 
## Assumptions
- Data refreshed daily
- Covers US customers only
 
## Next Steps
1. Review all specification files
2. Make any necessary edits
3. Confirm to proceed with publication
```
 
**This file is for the user to quickly understand what will be created.**
 
---
 
## Phase 3 — Iterative Refinement
 
**Goal:** Allow the user to review and refine the specification files before any API calls. This step is important. You MUST update the corresponding specification files based on the user edits.
 
### 3.1 Present Files to User

<Steps>
<Step>
1. After creating all files, present a summary:

```
I've created the data product specification in `.data_products/customer-360/`:

 data_product_spec.json - Core product definition
 assets_manifest.json - Assets to include (1 asset)
 delivery_config.json - Delivery methods (Flight + Download)
 contract_spec.json - Contract definition (template-based)
 README.md - Human-readable summary

Please review these files. You can:
- Edit any file directly in your editor
- Ask me to make specific changes
- Ask questions about any field

When ready, say "looks good" or "publish" to proceed.
```
</Step>
</Steps>
 
### 3.2 Handle User Feedback

**CRITICAL RULE: Every change request = immediate file update.**
When the user asks for any change — no matter how small — you MUST update the relevant specification file(s) before replying. Do NOT just acknowledge the change conversationally and move on. The file is the source of truth; your words are not.

<Steps>
<Step>

1. **User wants changes:**
- "Change the domain to Finance" → Update `data_product_spec.json` immediately
- "Add another asset" → Update `assets_manifest.json` immediately (use `search_asset` to find it first)
- "Remove the download delivery method" → Update `delivery_config.json` immediately
- "Use a URL contract instead" → Replace `contract_spec.json` immediately

</Step>
<Step>

2. **How to update files:**
Use whatever file-writing capability your environment provides — `bash_tool`, `create_file`, `write_to_file`, `apply_diff`, a code editor tool, etc. The specific tool doesn't matter; what matters is that the file on disk is actually updated before you respond to the user.
After updating, confirm to the user: "Updated `data_product_spec.json` — domain is now set to Finance."

</Step>
<Step>

3. **User edits files directly:**
- Read the updated file using whatever file-reading capability is available (`bash_tool` with `cat`, `read_file`, a viewer tool, etc.)
- Validate the changes (Phase 4)
- Proceed if valid

</Step>
<Step>

4. **Iterate until the user is satisfied.**

</Step>
</Steps>
 
---
 
## Phase 4 — Validation
 
**Goal:** Validate specification files before making any API calls. Do not assume the specification file contents. Always read the specification files at the start of this phase.
 
### 4.1 Validation Checklist

<Steps>
<Step>
1. Before proceeding to publication, validate:

**data_product_spec.json:**
- `name` is not empty
- `description` is not empty
- `domain` is specified

**assets_manifest.json:**
- At least one asset or URL is defined
- For assets: `asset_id`, `container_id`, `container_type` are present
- For URLs: `url_name` and `url_value` are present and valid HTTPS URLs

**delivery_config.json:**
- Delivery methods are specified for each asset (except URL-based products)
- At least one delivery method per asset

**contract_spec.json:**
- `contract_type` is one of: "url", "template", "custom"
- For URL contracts: `contract_url` is valid HTTPS URL
- For template contracts: `template_id` is specified (or will be looked up)
- For custom contracts: `contract_terms` has required fields
</Step>
</Steps>

### 4.2 Report Validation Results

<Steps>
<Step>
1. If validation fails, report issues clearly:

```
Validation failed:
- data_product_spec.json: 'domain' field is missing
- contract_spec.json: 'contract_url' is not a valid HTTPS URL

Please fix these issues before proceeding.
```
</Step>
<Step>
2. If validation passes:

```
All specification files validated successfully!

Ready to create the data product. This will:
1. Create draft data product in DPH
2. Add assets with delivery methods
3. Attach business domain
4. Attach contract
5. Publish the data product

Proceed? (yes/no)
```
</Step>
<Step>
3. **Wait for explicit user confirmation before Phase 5.**
</Step>
</Steps>
 
---
 
## Phase 5 — Publication
 
**Goal:** Batch-submit the specification to DPH using MCP tools.

### Critical Rule: Spec Files Are Always Source of Truth

Any change that occurs during publication — whether triggered by a tool error, a user decision, or a fallback — MUST immediately update the corresponding specification file BEFORE proceeding to the next step. This mirrors the CRITICAL RULE in Phase 3 and applies equally here.

Examples:
- Domain not found → user picks alternative → update `data_product_spec.json` immediately
- Delivery method IDs resolved → update `delivery_config.json` with actual method_ids immediately  
- User adds/removes a delivery method mid-publication → update `delivery_config.json` immediately
- Contract details collected → update `contract_spec.json` immediately

The spec files must reflect the actual published state of the data product at all times.
 
### 5.1 Read Specification Files

<Steps>
<Step>
1. Use whatever file-reading capability your environment provides to load all specification files:

- `data_product_spec.json`
- `assets_manifest.json`
- `delivery_config.json`
- `contract_spec.json`

</Step>
<Step>
2. Parse the JSON and prepare for API calls.
</Step>
</Steps>
 
### 5.2 Create Draft Data Product

**For Asset-Based Products:**

Asset-based data products use a **two-step workflow** for better performance and reusability:

<Steps>
<Step>

1. **Import assets to DPH catalog** (all assets at once):

   ```
   Call: import_remote_assets_to_data_product_catalog
   Input:
     - asset_ids: [list of all asset_ids from assets_manifest.json]
     - container_id_of_assets: from assets_manifest.json (same for all)
     - container_type: from assets_manifest.json (catalog or project)
     - force: false (if user wants to create a data product even if there are existing data products with same assets)
   
   Output: target_asset_ids (list of imported asset IDs in DPH catalog)
   ```
   
   **Note:** This step copies assets from the source container to the DPH catalog. The `force: false` parameter enables deduplication - if data products already exist with these assets, the import will be skipped. If you want to still create new data products, set `force: true`.

</Step>
<Step>

2. **Create draft with imported assets**:
   ```
   Call: create_update_data_product_from_asset_in_container
   Input:
     - name: from data_product_spec.json
     - description: from data_product_spec.json
     - target_asset_ids: [output from step 1]
     - existing_data_product_draft_id: None (for new draft)
   
   Output: data_product_draft_id, contract_terms_id
   ```
   
   **To add more assets to existing draft:**
   ```
   - Import additional assets using step 1
   - Call create_or_update with:
     - target_asset_ids: [new imported asset IDs]
     - existing_data_product_draft_id: <draft_id from previous call>
   ```

</Step>
</Steps>

**For URL-Based Products:**

<Steps>
<Step>

1. **Create URL Product Draft**:
  ```
  Call: create_or_update_url_data_product
  Input:
    - name: from data_product_spec.json
    - description: from data_product_spec.json
    - url_name: from assets_manifest.json
    - url_value: from assets_manifest.json
    - existing_data_product_draft_id: None (first URL)
    - force: false (check for duplicates)

  Output: data_product_draft_id, contract_terms_id
  ```

</Step>
</Steps>

**Store `data_product_draft_id` and `contract_terms_id` — you'll need them for subsequent steps.**

 
### 5.3 Add Delivery Methods

**Skip this step for URL-based products** (delivery method is automatic).

<Steps>
<Step>

1. For each asset in `delivery_config.json`:

**Discover available methods:**
  ```
  Call: find_data_product_delivery_methods_based_on_connection
  Input:
    - data_product_draft_id: from step 5.2
    - data_asset_name: from delivery_config.json
    
    Output: List of available delivery methods with IDs
  ```

</Step>
<Step>

2. **Match user's desired methods** from `delivery_config.json` to available methods by name.
   **IMPORTANT:** Update `delivery_config.json` to update method_id and method_name from the available methods for this asset.

   - method_id: from step 5.3.1
   - method_name: from step 5.3.1

</Step>
<Step>

3. **Add selected methods:**
   ```
   Call: add_delivery_methods_to_data_product
   Input:
      - data_product_draft_id: from step 5.2
      - data_asset_name: from delivery_config.json
      - delivery_method_ids: matched IDs from step 5.3.1
   ```
</Step>
<Step>

4. **Repeat for each asset.**

</Step>
</Steps>
 
### 5.4 Attach Business Domain

<Steps>
<Step>

1. 
```
Call: attach_business_domain_to_data_product
Input:
  - domain: from data_product_spec.json
  - data_product_draft_id: from step 5.2
```

</Step>
<Step>

2. If domain not found:
  - Tool returns list of available domains
  - Ask user to choose from the list
  - Update data_product_spec.json with chosen domain
  - Retry the step 1
</Step>
</Steps>
 
### 5.5 Attach Contract (Interactive Workflow)

**IMPORTANT:** This step is interactive. Ask the user which contract type they want, then guide them through the specific workflow. Update `contract_spec.json` as you collect information.

<Steps>
<Step>

1. **Ask User to Choose Contract Type**

Present three options to the user and wait for their choice.

</Step>
<Step>

2. **Execute Based on User's Choice**

**A. URL Contract Workflow:**
- Ask for contract URL (must be HTTPS) and contract name
- Update `contract_spec.json` with the URL and name
- Call `attach_url_contract_to_data_product` with the values from contract_spec.json

**B. Template-Based Contract Workflow:**
- Call `list_data_product_contract_templates` to list available templates
- Present templates to user and ask them to choose one
- Call `attach_contract_template_to_data_product` with contract_terms=None to preview the template
- Show the template defaults to the user
- Ask: "Use defaults as-is or customize fields?"
- If customize: Iteratively collect field customizations one by one, updating `contract_spec.json` after each
- When user says "done", confirm the customizations
- Call `attach_contract_template_to_data_product` with customizations from contract_spec.json

**C. Custom Contract Workflow:**
- Call `create_attach_custom_data_product_contract` with contract_terms=None to show the schema
- Initialize `contract_spec.json` with empty contract_terms
- Iteratively ask for each field value, updating `contract_spec.json` after each response
- When user says "done", confirm the complete contract
- Call `create_attach_custom_data_product_contract` with contract_terms from contract_spec.json

**IMPORTANT:** Make sure `contract_spec.json` is updated as you collect information.

</Step>
<Step>

3. **Verify and Save**

After successful attachment, confirm to the user that the contract has been attached and saved to `contract_spec.json`.

</Step>
</Steps>
 
### 5.6 Publish Data Product

<Steps>
<Step>

1. 
```
Call: publish_data_product
Input:
  - data_product_draft_id: from step 5.2
Output: Success message and URL to published data product
```

</Step>
<Step>

2. **The tool validates that all required fields are present before publishing:**
- Business domain attached
- Contract attached
- Delivery methods added to all assets

</Step>
<Step>

3. If validation fails, the tool returns an error with details. Fix the issue and retry.

</Step>
</Steps>
 
### 5.7 Confirm Success

<Steps>
<Step>

1. Present a final summary:

```
Data product published successfully!

Product: Customer 360 Data Product
URL: https://dph.example.com/data_products/abc-123-def-456
Specification: .data_products/customer-360/

Summary:
- 1 asset included (customer_master_table)
- 2 delivery methods (Flight, Download)
- Domain: Accounting and finance
- Contract: Template-based with custom SLAs
The specification files have been preserved in your workspace.
You can:
- Commit them to Git for version control
- Use them as a template for similar data products
- Update and re-publish as needed
```

</Step>
</Steps>
 
---
 
## Error Handling
 
### Common Errors and Solutions
 
**Domain not found:**
- Tool returns list of available domains
- Ask user to choose
- Update `data_product_spec.json`
- Retry domain attachment
 
**Asset not found:**
- Use `search_asset` with different search terms
- Ask user for more specific asset name or ID
- Update `assets_manifest.json`
 
**Delivery method not available:**
- Tool returns available methods for that connection type
- Ask user to choose from available methods
- Update `delivery_config.json`
 
**Contract template not found:**
- Use `list_data_product_contract_templates` to list all templates
- Ask user to choose
- Update `contract_spec.json`
 
**Duplicate URL:**
- `create_or_update_url_data_product` returns error with existing products
- Ask user if they want to proceed anyway (set `force: true`)
- Or help them use the existing data product
 
**Validation errors before publish:**
- Tool returns specific missing fields
- Update specification files
- Retry publication

**When importing remote assets to DPH Catalog fails:**
- Display the error message AS IT IS to the user to take corrective steps. Point out the assets that failed the import with the error message, and assets that passed the import step.
- Wait for the user input to resolve the issue before proceeding with the data product creation.
- Give an option to user to proceed with the assets that are successfully processed and imported, but always wait for the user the user input.
- If user wants to proceed with the successfully processed assets, then proceed with the data product creation - call `create_update_data_product_from_asset_in_container` with target asset IDs of the successfully processed/imported assets.

 
### Rollback Strategy
 
If publication fails partway through:
 
1. **Draft created but not published** — Draft remains in DPH, user can:
   - Fix issues and retry publication
   - Delete draft manually in DPH UI
   - Use specification files to recreate from scratch
 
2. **Specification files preserved** — User can:
   - Review what went wrong
   - Fix specification files
   - Retry entire publication process
 
---
 
## Advanced Scenarios
 
### Scenario 1: Multiple Assets from Different Containers
 
```json
// assets_manifest.json
{
  "source_type": "asset",
  "assets": [
    {
      "asset_id": "asset-1",
      "container_id": "catalog-abc",
      "container_type": "catalog",
      ...
    },
    {
      "asset_id": "asset-2",
      "container_id": "project-xyz",
      "container_type": "project",
      ...
    }
  ]
}
```
 
**Publication:** Call `import_remote_assets_to_data_product_catalog` tool for all assets at once. Then call `create_update_data_product_from_asset_in_container` once for all target_asset_ids returned by the previous tool call.
 
### Scenario 2: Mixed Asset and URL in one Data Product
 
User can choose both asset-based AND URL-based in one product, if desired.
 
### Scenario 3: Update Existing Data Product
 
**This skill creates new data products.** 
Once the data product is published, it is immutable. Therefore, to update an existing data product, the option is to:
- Create a new version using this skill with updated specifications

### Scenario 4: Template for Common Patterns
 
After creating a data product, suggest:
 
```
Tip: You can use these specification files as a template!
 
To create a similar data product:
1. Copy .data_products/customer-360/ to .data_products/new-product/
2. Edit the JSON files with new values
3. Run this skill again
 
This is especially useful for:
- Creating data products for different regions
- Onboarding similar datasets
- Standardizing data product structure across teams
```
 
---
 
## Key Principles
 
1. **Files First, API Calls Last**: Generate complete specifications before touching DPH
2. **Validate Early**: Catch errors in files before making API calls
3. **Iterate Freely**: User can refine specifications without API rate limits or side effects
4. **Preserve History**: Files can be versioned in Git
5. **Batch Operations**: Make 5-7 API calls instead of 15-20
6. **Clear Communication**: Always explain what you're doing and why
7. **User Confirmation**: Never publish without explicit user approval
8. **Spec Files Are Always Source of Truth**: If there is any change request, update the specification file first before proceeding.
 
---
 
## Critical Reminders
 
1. **Treat specification files as source of truth** - DPH is the deployment target
3. **Never publish without user confirmation** - always validate first
4. **Preserve specification files** - they enable version control and reusability
5. **Validate before API calls** - catch errors early in the workflow
6. **Batch operations** - minimize API calls by using complete specifications
---

[//]: # (Copyright [2026] [IBM])
[//]: # (Licensed under the Apache License, Version 2.0 \(http://www.apache.org/licenses/LICENSE-2.0\))
[//]: # (See the LICENSE file in the project root for license information.)
