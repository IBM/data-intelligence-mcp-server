# Changelog

> All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project **adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)**.

## [0.1.0] - Oct 3rd, 2025

### Added
- MCP infrastructure for http and stdio mode of transport
- apikey and Bearer token support
- Logs
- pypi packaging change
- Tools for Lineage, Text to SQL, Data Product Hub, Data Protection rules, Search, and Data Quality (see [TOOLS.md](TOOLS.md) for details)

## [0.1.4] - Oct 3rd, 2025

### Added
- Fixed mcp client error notification in stdio mode
- pypi package changes for 0.1.4

## [0.2.0] - Oct 23rd, 2025

### Added
- With MCP transport mode `http`, server now defaults to starting on `https` url (can be configured to start on http by setting `SERVER_HTTPS=False`). 
  Refer to `readme_guides\SERVER_HTTPS.md` on how to generate and/or pass-in the ssl certificate and key to start the server with `https`
- Added `context` parameter to tools with URL responses (e.g., `context=df`), ensuring asset links open in the appropriate context
- Created `readme_guides` directory with documentation for server configuration and SSL certificate setup
- Enhanced formatting of scores in data quality responses
- Added `data_protection_rule_search` tool - Search data protection rules 
- Added `enable_project_for_text_to_sql` tool - Enables the specified project for text-to-sql