# Data Product Specification Templates

This directory contains JSON schema templates used by the data-product-creation skill. These templates define the structure of specification files that the AI agent creates during the data product creation workflow.

## Placeholder Conventions

Templates use descriptive placeholders to indicate how values should be populated:

- **`<USER_PROVIDED_*>`** - Value must be collected from user through conversation
- **`<POPULATED_BY_*_TOOL>`** - Value automatically populated by MCP tool call (user does not modify)
- **`<USER_PROVIDED_OR_SELECTED_*>`** - Value either provided by user or selected from a list
- **`<OPTIONAL_*>`** - Optional field that may be populated if available
- **`<MUST_MATCH_*>`** - Value must match a corresponding value from another file

Examples:
- `<USER_PROVIDED_PRODUCT_NAME>` - User provides the data product name
- `<POPULATED_BY_SEARCH_ASSET_TOOL>` - Asset ID returned by search_asset tool
- `<USER_PROVIDED_OR_SELECTED_FROM_LIST>` - User chooses domain from available list

## Template Files

### Core Specification Files

- **`data_product_spec.json`** - Core data product metadata including name, description, domain, version, tags, use case, and assumptions.

- **`assets_manifest_asset_based.json`** - Template for asset-based data products. Defines assets from catalogs or projects to include in the data product.

- **`assets_manifest_url_based.json`** - Template for URL-based data products. Defines external data sources accessible via URLs.

- **`delivery_config.json`** - Defines delivery methods for each asset (e.g., Flight service, Download). Not needed for URL-based products.

### Contract Templates

- **`contract_url.json`** - Simplest contract type. References an external contract document via HTTPS URL.

- **`contract_template.json`** - Uses a predefined contract template from DPH with optional customizations.

- **`contract_custom.json`** - Most flexible contract type. Allows full customization of all contract terms including SLAs, pricing, support channels, etc.

## Usage

These templates are referenced in the [SKILL.md](../SKILL.md) file and serve as:

1. **Documentation** - Shows users and AI agents the expected structure
2. **Validation Reference** - Helps validate user-provided specifications
3. **Starting Point** - Can be copied and customized for new data products
4. **Testing** - Can be used in automated tests and scripts

## File-Based Specification Approach

The skill uses an Infrastructure-as-Code approach where:

1. Templates define the schema
2. AI agent creates actual specification files in `.data_products/<product-name>/`
3. User reviews and refines the specifications
4. Specifications are validated
5. Specifications are batch-submitted to Data Product Hub

This approach enables version control, collaboration, and reusability of data product definitions.