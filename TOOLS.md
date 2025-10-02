# MCP Tools Reference

This document provides a comprehensive list of all Model Context Protocol (MCP) tools available in the Data Intelligence MCP Server.

## Table of Contents

- [MCP Tools Reference](#mcp-tools-reference)
  - [Table of Contents](#table-of-contents)
  - [Data Product Service](#data-product-service)
  - [Data Protection Rule Service](#data-protection-rule-service)
  - [Lineage Service](#lineage-service)
  - [Search Service](#search-service)
  - [Text to SQL Service](#text-to-sql-service)
  - [Data Quality Service](#data-quality-service)
  - [Usage Guidelines](#usage-guidelines)
  - [Multi-step Workflows](#multi-step-workflows)
    - [Create and Publish URL Data Product](#create-and-publish-url-data-product)
    - [Create and Publish Data Product from Catalog](#create-and-publish-data-product-from-catalog)

## Data Product Service

Tools for managing data products.

| Tool Name | Description | Sample Prompt |
|-----------|-------------|---------------|
| `data_product_create_url_data_product` | Creates a URL data product draft with specified name and URL details. | "Create a url data product draft with Name: Customer360, URL name: service, URL value: https://example.com/" |
| `data_product_get_assets_from_catalog` | Gets assets from catalog and is called as the first step to create a data product from catalog. | "Show me all assets from catalog" |
| `data_product_create_data_product_from_catalog` | Creates a data product draft from catalog assets. | "Create a data product draft from catalog using customers2 asset and name the product as DataService" |
| `data_product_attach_business_domain` | Attaches a business domain to a data product draft. | "Attach a business domain to this draft with domain name: Business Management" |
| `data_product_attach_url_contract` | Attaches a URL contract to a data product draft. | "Attach a url contract to this draft with contract name as policy and contract url as https://example.com/" |
| `data_product_find_delivery_methods_based_on_connection` | Finds available delivery methods based on connection. | "What delivery methods are available for my data product?" |
| `data_product_add_delivery_methods_to_data_product` | Adds delivery methods to a data product draft. | "Add Download and Data Extract delivery methods to this draft" |
| `data_product_publish_data_product` | Publishes a data product draft to make it available. | "Publish this draft" |
| `data_product_search_data_products` | Searches data products based on a search query or in a domain | "Find me stock related data products" or "Find me data products in Audit domain"

## Data Protection Rule Service
Tools for managing data protection rules.

| Tool Name | Description | Sample Prompt |
|-----------|-------------|---------------|
| `data_protection_rule_create` | Creates data protection rules.| "create me data protection rule name  sample when the asset contains name test and dataclass contains ssn with action allow" |

## Lineage Service

Tools for working with data lineage.

| Tool Name | Description | Sample Prompt |
|-----------|-------------|---------------|
| `lineage_get_lineage_graph_by_cams_id` | Returns upstream/downstream lineage graph using CAMS ID. | "Can you get me lineage graph of asset 'asset_id' from project id 'project_id'" or following on a response of `search_asset` tool "Could you point me to the upstream and downstream lineage of the 'asset name'" |
| `lineage_get_lineage_graph` | Returns upstream/downstream lineage graph of a lineage asset. | "RI would like to get the full lineage graph of lineage asset 'lineage_id'" or following on a response of `lineage_search_lineage_assets` tool "Can you point to the upstream and downstream lineage of this one 'asset name'|
| `lineage_search_lineage_assets` | Searches assets in the Lineage system and returns their lineage history. | "Find lineage asset named ACCOUNT_TYPES_STG" or "What is the lineage of orders, it's a table with IBM Db2 technology" |

## Search Service

Tools for searching artifacts.

| Tool Name | Description | Sample Prompt |
|-----------|-------------|---------------|
| `search_asset` | Searches for data assets based on a search prompt. | "I'm searching for assets about stocks in projects" or "Please search for data related to vehicles in projects" |

## Text to SQL Service

Tools for creating assets and generating queries from SQL.

| Tool Name | Description | Sample Prompt |
|-----------|-------------|---------------|
| `text_to_sql_create_asset_from_sql_query` | Creates a new asset from a SQL query. | "Create an asset in project `project_id` using connection `connection_id` from 'SELECT * FROM schema.actors a WHERE a.surname = 'Kilmer';'" |
| `text_to_sql_generate_sql_query` | Generates a SQL query from natural language request and schema. | "Find all films with rating R in project named Commercials using connection postgres" or "Find all actors with last name Kilmer from a project named Commercials with connection mssql-db" |

## Data Quality Service

Tools for working with data quality of assets.

| Tool Name | Description | Sample Prompt |
|-----------|-------------|---------------|
| `data_quality_get_data_quality_for_asset` | Gets the data quality of a data asset. | Following on assets retrieved by `search_asset` tool "What is the data quality of 'asset name'?" or "Could you please give me more information about data quality of 'eu_daily_trades' asset?" |

## Usage Guidelines

When using these tools:

1. Ensure you have the necessary permissions for the operation
2. Provide all required parameters as specified in the tool documentation
3. Handle any returned errors appropriately
4. For data product operations, follow the proper sequence (create → attach domain/contract → add delivery methods → publish)

## Multi-step Workflows

Some common multi-step workflows:

### Create and Publish URL Data Product

1. `data_product_create_url_data_product` → Create a URL data product draft
2. `data_product_attach_business_domain` → Attach a business domain
3. `data_product_attach_url_contract` → Attach a URL contract
4. `data_product_publish_data_product` → Publish the data product

### Create and Publish Data Product from Catalog

1. `data_product_get_assets_from_catalog` → Get assets from catalog
2. `data_product_create_data_product_from_catalog` → Create a data product draft from catalog
3. `data_product_attach_business_domain` → Attach a business domain
4. `data_product_attach_url_contract` → Attach a URL contract
5. `data_product_find_delivery_methods_based_on_connection` → Find available delivery methods
6. `data_product_add_delivery_methods_to_data_product` → Add delivery methods
7. `data_product_publish_data_product` → Publish the data product
