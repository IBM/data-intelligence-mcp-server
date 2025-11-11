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
    - [Create and Publish Data Product from an asset in a container](#create-and-publish-data-product-from-an-asset-in-a-container)

## Data Product Service

Tools for managing data products.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `data_product_create_url_data_product` | Creates a URL data product draft with specified name and URL details. | "Create a url data product draft with Name: Customer360, URL name: service, URL value: https://example.com/" | >=0.1.4 | >=5.2.1 |
| `data_product_get_assets_from_container` | Gets assets from a container (catalog/project) and is called as the first step to create a data product from an asset in container. | "Show me all assets from catalog" or "Show me all assets from project" | >=0.3.0 | >=5.2.1 |
| `data_product_create_data_product_from_asset_in_container` | Creates a data product draft from catalog or project assets. | "Create a data product draft from catalog using CustomerReview asset and name the product as Customer Reviews" or "Create a data product draft from project using Sales asset and name the product as Sales Target" | >=0.3.0 | >=5.2.1 |
| `data_product_attach_business_domain` | Attaches a business domain to a data product draft. | "Attach a business domain to this draft with domain name: Business Management" | >=0.1.4 | >=5.2.1 |
| `data_product_attach_url_contract` | Attaches a URL contract to a data product draft. | "Attach a url contract to this draft with contract name as policy and contract url as https://example.com/" | >=0.1.4 | >=5.2.1 |
| `data_product_find_delivery_methods_based_on_connection` | Finds available delivery methods based on connection. | "What delivery methods are available for my data product?" | >=0.1.4 | >=5.2.1 |
| `data_product_add_delivery_methods_to_data_product` | Adds delivery methods to a data product draft. | "Add Download and Data Extract delivery methods to this draft" | >=0.1.4 | >=5.2.1 |
| `data_product_publish_data_product` | Publishes a data product draft to make it available. | "Publish this draft" | >=0.1.4 | >=5.2.1 |
| `data_product_search_data_products` | Searches data products based on a search query or in a domain | "Find me stock related data products" or "Find me data products in Audit domain" | >=0.1.4 | >=5.2.1 |
| `data_product_request_new_data_product` | Requests a new data product. This reads a number of mandatory and optional fields from user for requesting a data product. | "Request a new data product" or "I would like to request a data product with name RequestDP" | >=0.3.0 | >=5.2.1 |

## Data Protection Rule Service
Tools for managing data protection rules.

| Tool Name                     | Description                    | Sample Prompt                                                                                                                | pypi version | CPD version |
|-------------------------------|--------------------------------|------------------------------------------------------------------------------------------------------------------------------|-------------|-------------|
| `data_protection_rule_create` | Creates data protection rules. | "create me data protection rule name  sample when the asset contains name test and dataclass contains ssn with action allow" | >=0.1.4 | >=5.2.1 |
| `data_protection_rule_search` | Search data protection rules.  | "show me all data protection rules with Deny name"                                                                           | >=0.2.0 | >=5.2.1 |

## Lineage Service

Tools for working with data lineage.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `lineage_convert_to_lineage_id` | Returns lineage ID of a CAMS asset | "What is the lineage id of asset 'asset_id' from project id 'project_id'" or following on a response of `search_asset` tool "Could you show me lineage id of the 'asset name'" | >=0.3.0 | >=5.2.1 |
| `lineage_get_lineage_graph` | Returns lineage graph of lineage assets. | "I would like to get the full lineage graph of lineage asset 'lineage_id'" or following on a response of `lineage_search_lineage_assets` tool "Can you point to the upstream and downstream lineage of this one 'asset name' or "What are the immediate downstream assets of 'asset name'?"| >=0.1.4 | >=5.2.1 |
| `lineage_search_lineage_assets` | Searches assets in the Lineage system. | "Find lineage asset named ACCOUNT_TYPES_STG", "What is the lineage of orders, it's a table with IBM Db2 technology" or  "Find lineage asset that has quality score of less than 65, has a tag dp_source and has business classification PI" | >=0.1.4 | >=5.2.1 |


## Search Service

Tools for searching artifacts.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `search_asset` | Searches for data assets based on a search prompt. | "I'm searching for assets about stocks in projects" or "Please search for data related to vehicles in projects" | >=0.1.4 | >=5.2.1 |

## Text to SQL Service

Tools for creating assets and generating queries from SQL.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `text_to_sql_create_asset_from_sql_query` | Creates a new asset from a SQL query. | "Create an asset in project `project_id` using connection `connection_id` from 'SELECT * FROM schema.actors a WHERE a.surname = 'Kilmer';'" | >=0.1.4 | >=5.2.1 |
| `text_to_sql_generate_sql_query` | Generates a SQL query from natural language request and schema. | "Find all films with rating R in project named Commercials using connection postgres" or "Find all actors with last name Kilmer from a project named Commercials with connection mssql-db" | >=0.1.4 | >=5.2.1 |
| `text_to_sql_enable_project_for_text_to_sql` | Enables project for text to sql. | "Please enable project <project_name> for text to SQL" or "Enable text to SQL for my project id <project_id>" | >=0.2.0 | >=5.2.1 |

## Data Quality Service

Tools for working with data quality of assets.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `data_quality_get_data_quality_for_asset` | Gets the data quality of a data asset. | Following on assets retrieved by `search_asset` tool "What is the data quality of 'asset name'?" or "Could you please give me more information about data quality of 'eu_daily_trades' asset?" | >=0.1.4 | >=5.2.1 |

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

### Create and Publish Data Product from an asset in a container

Note: Container can be a catalog or a project.

1. `data_product_get_assets_from_container` → Get assets from catalog/ Get assets from project
2. `data_product_create_data_product_from_asset_in_container` → Create a data product draft from catalog/project
3. `data_product_attach_business_domain` → Attach a business domain
4. `data_product_attach_url_contract` → Attach a URL contract
5. `data_product_find_delivery_methods_based_on_connection` → Find available delivery methods
6. `data_product_add_delivery_methods_to_data_product` → Add delivery methods
7. `data_product_publish_data_product` → Publish the data product
