# Changelog

> All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project **adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)**.

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
- Manual sample prompt templates available in `PROMPTS_SAMPLES/` directory for MCP clients without prompt registration support

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
