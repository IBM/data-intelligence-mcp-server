# Changelog

> All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project **adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)**.

## [0.8.0.post1] - Apr 10th, 2026
- Removed docling from requirements

## [0.8.0] - Apr 8th, 2026

### Added
- **Data Product Hub (DPH)**:
  - `data_product_search_data_product_subscriptions` - Search and filter data product subscriptions (asset lists) with query support for filtering by asset ID, name, state, and owner
  - `data_product_get_data_product_subscription_details` - Retrieve actual content (items) being delivered in a specific subscription including delivery states and access information
- **Metadata Enrichment (MDE)**:
  - `execute_term_generation` - Executes term generation on a metadata enrichment area (MDE) in a project
  - `execute_advanced_profiling` - Executes advanced profiling on a metadata enrichment asset for selected datasets.
- **Metadata Import (MDI)**:
  - `search_metadata_import` - Searches the metadata imports (MDI) in a given project. If a name is provided, the tool will use wildcard search otherwise it return all the available MDIs.
- **Text to Query Search**: 
  - `dynamic_query_search` - Generates dynamic search queries from natural language and executes them against the search engine.

### Changed
- **Data Product Hub (DPH)**:
  - `data_product_search_data_products` - Added creation date filters (`created_date_after` and `created_date_before`) and URL in response for each data product result
  - `data_product_get_data_product_details` -  Updated the response to also return the url of the data product.
- **Lineage**:
  - Enhanced `search_lineage_assets` with improved filtering and search capabilities
- **Glossary**:
  - Improved CSV import validation and error handling
  - Enhanced glossary artifact retrieval with better asset association handling
- **Workflow**:
  - Enhanced workflow task formatters with improved display and data handling
- **Authentication**: Enhanced AWS environment support with improved IAM endpoint handling

### Fixed
- **Connections**:
  - `copy_connection` - Fix the tool to create a reference connection that is tested and ready to use, instead of creating a duplicate connection without credentials.
- **User Search & Projects**: Updated user group API endpoints to support CPD 5.4+ by implementing fallback mechanism:
  - Primary: Uses new `/usermgmt/v4/groups` endpoint with pagination support
  - Fallback: Falls back to legacy `/usermgmt/v2/groups` endpoint for backward compatibility
  - Affects `search_user_groups_roles` tool and `add_or_edit_collaborator` tool

## [0.7.0] - Mar 18th, 2026

### Added
- **Workflow**:
  - `get_my_workflows` - Retrieves workflows initiated by the current user with light and deep dive modes
  - `get_workflow_tasks_from_my_inbox` - Retrieve tasks from workflow task inbox for the current user
  - `list_business_terms_by_search_term` - Search business terms in glossary
  - `list_data_classes_by_search_term` - Search data classes in glossary
  - `list_user_tasks_approval_data_for_artifact` - Retrieve approval and review user tasks for specific glossary artifact
- **Connections**: Added a new service to add tools for managing (create, copy, move etc.) connections:
  - `copy_connection` - Added a new tool for copying existing connections between catalogs or projects.
- **Glossary**:
  - `glossary_csv_import` - Import business glossary terms and categories from CSV files following IBM watsonx.data intelligence format with validation and merge options
  - `get_glossary_csv_schema` - Get detailed information about the CSV schema for importing glossary artifacts
- **Metadata Enrichment (MDE)**:
  - `search_categories` - Search for user's categories, mainly used when creating or updating metadata enrichment without providing a category

### Changed
- **Data Protection Rules (DPS)**: Refactored data protection rule creation logic to simplify the API by consolidating natural language and structured rule creation into a single JSON-based approach
- **Data Product Hub (DPH)**:
  - `data_product_get_data_product_details` - Added `flight_client_url` field to subscription details to provide direct Arrow Flight connection URL for data extraction. Enhanced subscription details to return only the latest successful subscription (sorted by last_updated_at). Added `data_product_version_id` to search_data_products response
- **Search**:
  - `search_data_source_definition` - Enhanced the search data source definition tool to filter results by DSD name
- **HTTP Client**: Support file payloads in http_client & tool helper service for handling non-JSON responses and byte payloads

## [0.6.0] - Mar 2nd, 2026

### Added
- **Data Product Hub (DPH)**: 
  - `data_product_get_data_product_details` - Retrieves comprehensive information about a data product including release details, parts/assets with enriched column schemas, primary keys, and subscription information.
- **Reporting**: 
  - `reporting_sql_query_execution` - Execute SQL SELECT queries against tenant-specific reporting database with read-only access and query validation
  - `reporting_sql_query_generation` - Generate SQL queries from natural language input using text-to-SQL service for reporting use cases
- **Lineage**: 
  - `lineage_get_lineage_versions` - Returns list of lineage versions available between two dates for comparison
- **Data Quality**:
  - `create_data_quality_rule_from_sql_query` - Create a new data quality rule using a SQL query. Optionally specify a data quality dimension (completeness, validity, consistency).
  - `find_data_quality_rules` - Find and list data quality rules in a project, optionally filtered by rule name.
  - `run_data_quality_rule` - Execute a specific data quality rule to validate data and returns rule details with UI URL.
  - `set_validates_data_quality_of_relation` - Link a data quality rule to a specific column in a data asset to report quality scores for that column.
- **Glossary**: 
  - `explain_glossary_artifact` - Retrieves and explains metadata about glossary terms, classifications, data classes, reference data, policies, or rules including their definition, purpose, and related metadata.
  - `get_glossary_artifacts_for_asset` - Retrieves all business terms and classifications associated with a specific asset.
- **Metadata Import (MDI)**: 
  - `execute_metadata_import` - Executes a metadata import asset to start the import job. This initiates the process of importing assets from the configured data source into the project.
- **Text to SQL**: 
  - `text_to_sql_check_if_onboarding_job_is_completed` - checks if onboarding job for project completed successfully.
- **User Search**: 
  - `search_user_groups_roles` - Unified tool that searches for users, groups, or roles based on search_type parameter ("user", "group", or "role"). Simplifies identity search with a single tool interface. Supports intelligent fuzzy matching with confidence scores and listing all items when no query is provided

### Changed
- **HTTP Client**: Enhanced `http_client` and `tool_helper_service` to support non-JSON responses and byte payloads
- **Data Quality**: 
    - Refactored data quality tools with improved error handling and utility functions in `data_quality_common_utils`
    - `get_data_quality_for_asset` - Retrieve data quality metrics for specific assets
- **Lineage**: Enhanced lineage tools with date-based filtering and version comparison support

### Fixed
- **Search Tool**: Fix the issue where assets created or updated by a service_id cause a crash in `get_asset_details` tool because they do not appear in the user list. Resolve this by skipping traversal from user_profiles to prevent the crash.
- **Data Quality**: Fixed `_ratio_to_percentage` edge case logic for proper decimal formatting

## [0.5.1] - Jan 30th, 2026

### Added
- **Metadata Enrichment (MDE)**: `start_metadata_relationship_analysis` tool to initiate relationship analysis for metadata enrichment assets
- **Data Protection Rules (DPS)**: `data_protection_rule_search_governance_artifacts` tool to search for governance artifacts (classifications, data classes, or glossary terms/business terms) by query to find existing artifacts in IBM Knowledge Catalog
- **Prompt Templates**: Added Data Intelligence Tool Usage Guide - Prompt for using all Data Intelligence MCP tools correctly with workflow rules and best practices. Added as MCP prompt as well as prompt template samples in `PROMPTS_TEMPLATE_SAMPLES/` directory for MCP clients without prompt registration support
- **Prompt Templates**: Added Data Protection Rule Creation Guide (`create_rule_guide_prompt`) - Interactive prompt to guide users through creating data protection rules with configurable actions (deny/redact/filter row/anonymize/pseudonymize) and trigger conditions including user groups, governance artifacts, data assets, and tags. Includes governance artifact verification, rule preview, and step-by-step confirmation workflow

### Changed
- **Data Protection Rules (DPS)**: Replaced single `data_protection_rule_create` tool with two specialized tools with improved validation and error handling:
  - `create_data_protection_rule_from_text` - Create data protection rules using natural language descriptions in SaaS environments. Automatically validates referenced objects (classifications, user groups, etc.) and converts natural language into structured rule format with a two-step workflow (preview then create)
  - `create_data_protection_rule` - Create data protection rules with structured parameters in CP4D environments. Supports configurable trigger conditions (data classes, tags, asset names, business terms, owners) with operators (CONTAINS, LIKE), automatic validation of operator-field compatibility, and a two-step workflow with automatic preview generation before rule creation
- **Data Product Hub (DPH)**: Updated `data_product_search_data_products` tool to search all data products including both releases and drafts
- **Data Product Hub (DPH)**: URL validation for contract URLs in `data_product_attach_url_contract_to_data_product` tool to ensure valid URL format before attaching contracts to data products
- **Data Product Hub (DPH)**: URL validation for data product URLs in `data_product_create_or_update_url_data_product` tool to ensure valid URL format when creating or updating URL-based data products

### Fixed
- **Project Tools**: Fixed context parameter handling in `create_project` tool to correctly determine project type based on environment mode (CPD on-premises vs SaaS) and user-specified type, ensuring appropriate context values (`icp4data`, `cpdaas`, or `df`) are appended to project URLs. The `list_containers` tool now properly lists all projects with correct context values

## [0.5.0] - Jan 13th, 2026

### Added
- `data_product_get_data_contract` tool to get data contract for the specified data product (draft/published)
- `data_product_get_contract_templates` tool to get all data contract templates defined in the instance
- `data_product_attach_contract_template_to_data_product` tool to attach a contract template chosen by the user to a data product draft
- `data_product_create_and_attach_custom_contract` tool to create a custom contract and attach it to a data product draft.
- `search_connection` tool to search for connections based on allowed filters of container, connection name, data source type, or creator
- `create_metadata_enrichment_asset` tool replaced by `create_or_update_metadata_enrichment_asset` which supports update also now
- **Lineage Impact Analysis** prompt to perform impact analysis using data lineage to understand downstream and upstream dependencies
- **Search Assets** prompt to get guidance on how to search for data assets effectively in catalogs or projects
- Manual sample prompt templates available in `PROMPTS_TEMPLATE_SAMPLES/` directory for MCP clients without prompt registration support

### Changed
- `add_or_edit_collaborator` tool default role changed from 'editor' to 'viewer'
- `get_asset_details` tool enhanced to return asset owner name and email information


## [0.4.0] - Dec 3rd, 2025

### Added
- Sample prompt template for search assets
- Create project tool
  - `create_project` tool to create a new project with specified name, description, type, storage, and tags
- Search tools:
  - `get_asset_details` tool to retrieve details of a given asset (by ID or name)
  - `search_data_source_definition` tool to search for DSDs based on allowed filters of datasource type, hostname, port, and physical collection
  - `list_containers` tool to list all containers (catalogs, projects, and spaces)
  - `find_container` tool to find a container (catalog, project, or space) by ID or name
- Metadata Import tools:
  - `create_metadata_import` tool to create a draft metadata import (MDI) asset in a project using a connection and scope
  - `list_connection_paths` tool to list available schema/table paths for a connection (supports pagination and filtering)
- Metadata Enrichment (MDE) tools:
  - `create_metadata_enrichment_asset` tool to create a metadata enrichment asset in a project
  - `execute_metadata_enrichment_asset` tool to execute a metadata enrichment by name in the specified project
  - `execute_metadata_enrichment_asset_for_selected_assets` tool to execute a metadata enrichment by name in the specified project for the specified data assets
  - `execute_metadata_expansion_for_selected_assets` tool to execute metadata expansion for selected assets in a project
  - `execute_data_quality_analysis_for_selected_assets` tool to execute data quality analysis for specific datasets within a project
- DPH tools:
  - `data_product_create_or_update_url_data_product` tool to create a URL data product draft, or update an existing draft with a URL asset. If an existing draft ID is passed from the context, then this is an update operation to add the given URL as an asset to an existing draft.
  - `data_product_create_or_update_from_asset_in_container` tool to create a data product draft from asset in catalog or project, or update an existing draft with a catalog or project asset. If an existing draft ID is passed from the context, then this is an update operation to add the given asset from catalog or project to an existing draft.

### Changed
- Lineage tools now return the path of an asset based on hierarchy instead of identity_key
- `data_product_find_delivery_methods_based_on_connection` also accepts a mandatory input - data asset name. This is the name of the data asset for which we need to find the delivery method options.
- `data_product_add_delivery_methods_to_data_product` also accepts a mandatory input - data asset name. This is the name of the data asset in the data product draft for which we need to add delivery methods.

### Removed
- `get_system_prompts` tool - This tool was retrieving tool descriptions, which MCP clients can already retrieve from tool registration
- `data_product_create_url_data_product` tool (replaced by `data_product_create_or_update_url_data_product`)
- `data_product_create_data_product_from_asset_in_container` tool (replaced by `data_product_create_or_update_from_asset_in_container`)


## [0.3.1] - Nov 13th, 2025

### Added
- `convert_to_lineage_id` tool that returns the lineage ID of a CAMS asset as a replacement for the `get_lineage_graph_by_cams_id` tool
- `data_product_get_assets_from_container` tool to retrieve assets from a container based on container type (either `project` or `catalog`). This tool replaces `data_product_get_assets_from_catalog`, which only fetched assets from catalogs
- `data_product_create_data_product_from_asset_in_container` tool to create a data product from an asset in a container (either `project` or `catalog`). This tool replaces `data_product_create_data_product_from_catalog`, which only created data products from catalogs
- PyPI and CPD version information indicating when tools became available for each tool in the `TOOLS_PROMPTS.md` file

### Changed
- `enable_project_for_text_to_sql` tool now accepts both project ID and project name
- `search_lineage_assets` tool now includes additional filtering parameters: `is_operational`, `tag`, `data_quality_operator`, `data_quality_value`, `business_term`, and `business_classification`
- `search_lineage_assets` tool now returns lineage assets with their parent assets and tags
- `get_lineage_graph` tool now includes additional parameters to specify the number of upstream and downstream levels in the lineage graph (`hop_up`, `hop_down`) and the `ultimate` parameter
- `get_lineage_graph` tool now accepts a list of asset IDs as input and returns a list of edges in the graph
- `data_product_create_url_data_product` tool now returns a URL to the data product draft
- `data_product_publish_data_product` tool now returns a URL to the published data product
- `data_product_search_data_product` tool now returns a message indicating that the tool returns a maximum of 20 data products
- Error message when certificates are missing for HTTPS mode
- Validations for empty search prompts and invalid container types, and tool descriptions for the `search_asset` tool

### Removed
- `get_lineage_graph_by_cams_id` tool (replaced by `convert_to_lineage_id` tool)
- `data_product_get_assets_from_catalog` tool (replaced by `data_product_get_assets_from_container` tool)
- `data_product_create_data_product_from_catalog` tool (replaced by `data_product_create_data_product_from_asset_in_container` tool)

## [0.2.0] - Oct 24th, 2025

### Added
- With MCP transport mode `http`, server now defaults to starting on `https` url (can be configured to start on http by setting `SERVER_HTTPS=False`). 
  Refer to `readme_guides\SERVER_HTTPS.md` on how to generate and/or pass-in the ssl certificate and key to start the server with `https`
- Added `context` parameter to tools with URL responses (e.g., `context=df`), ensuring asset links open in the appropriate context
- Created `readme_guides` directory with documentation for server configuration and SSL certificate setup
- Enhanced formatting of scores in data quality responses
- Added `data_protection_rule_search` tool - Search data protection rules 
- Added `enable_project_for_text_to_sql` tool - Enables the specified project for text-to-sql

## [0.1.4] - Oct 3rd, 2025

### Added
- Fixed mcp client error notification in stdio mode
- pypi package changes for 0.1.4

## [0.1.0] - Oct 3rd, 2025

### Added
- MCP infrastructure for http and stdio mode of transport
- apikey and Bearer token support
- Logs
- pypi packaging change
- Tools for Lineage, Text to SQL, Data Product Hub, Data Protection rules, Search, and Data Quality (see [TOOLS_PROMPTS.md](TOOLS_PROMPTS.md) for details)
