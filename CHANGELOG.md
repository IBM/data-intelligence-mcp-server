# Changelog

> All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project **adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)**.

## [0.1.0] - Oct 3rd, 2025

### Added
- MCP infrastructure for http and stdio mode of transport
- apikey and Bearer token support
- Logs
- pypi packaging change
- Tools for Lineage, Text to SQL, Data Product Hub, Data Protection rules, Search, and Data Quality (see [TOOLS_PROMPTS.md](TOOLS_PROMPTS.md) for details)

## [0.1.4] - Oct 3rd, 2025

### Added
- Fixed mcp client error notification in stdio mode
- pypi package changes for 0.1.4

## [0.2.0] - Oct 24th, 2025

### Added
- With MCP transport mode `http`, server now defaults to starting on `https` url (can be configured to start on http by setting `SERVER_HTTPS=False`). 
  Refer to `readme_guides\SERVER_HTTPS.md` on how to generate and/or pass-in the ssl certificate and key to start the server with `https`
- Added `context` parameter to tools with URL responses (e.g., `context=df`), ensuring asset links open in the appropriate context
- Created `readme_guides` directory with documentation for server configuration and SSL certificate setup
- Enhanced formatting of scores in data quality responses
- Added `data_protection_rule_search` tool - Search data protection rules 
- Added `enable_project_for_text_to_sql` tool - Enables the specified project for text-to-sql
  
## [0.3.0] - Nov 11th, 2025

### Added
- `convert_to_lineage_id` tool that returns the lineage ID of a CAMS asset as a replacement for the `get_lineage_graph_by_cams_id` tool
- `data_product_request_new_data_product` tool to request a new data product
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