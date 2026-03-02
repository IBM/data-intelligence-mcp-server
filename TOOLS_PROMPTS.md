# MCP Tools Reference

This document provides a comprehensive list of all Model Context Protocol (MCP) tools available in the Data Intelligence MCP Server.

## Table of Contents

- [MCP Tools Reference](#mcp-tools-reference)
  - [Table of Contents](#table-of-contents)
  - [Data Product Service](#data-product-service)
  - [Data Protection Rule Service](#data-protection-rule-service)
  - [Data Quality Service](#data-quality-service)
  - [Glossary Service](#glossary-service)
  - [Lineage Service](#lineage-service)
  - [Metadata Enrichment Service](#metadata-enrichment-service)
  - [Metadata Import Service](#metadata-import-service)
  - [Projects Service](#projects-service)
  - [Reporting Service](#reporting-service)
  - [Search Service](#search-service)
  - [Text to SQL Service](#text-to-sql-service)
  - [User Service](#user-service)
  - [Usage Guidelines](#usage-guidelines)
  - [Multi-step Workflows](#multi-step-workflows)
    - [Create and Publish URL Data Product](#create-and-publish-url-data-product)
    - [Create and Publish Data Product from an asset in a container](#create-and-publish-data-product-from-an-asset-in-a-container)

## Data Product Service

Tools for managing data products.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `data_product_create_or_update_url_data_product` | Creates a URL data product draft with specified name and URL details or updates an existing draft with a URL asset. | "Create a url data product draft with Name: Customer360, URL name: service, URL value: https://example.com/" or "Add a URL asset with name: service, URL value: https://example.com/ to the draft" | >=0.4.0 | >=5.2.1 |
| `data_product_get_assets_from_container` | Gets assets from a container (catalog/project) and is called as the first step to create a data product from an asset in container. | "Show me all assets from catalog" or "Show me all assets from project" | >=0.3.1 | >=5.2.1 |
| `data_product_create_or_update_from_asset_in_container` | Creates a data product draft from catalog or project assets or updates an existing draft with catalog or project assets. | "Create a data product draft from catalog using CustomerReview asset and name the product as Customer Reviews" or "Create a data product draft from project using Sales asset and name the product as Sales Target" or "Add Sales asset from project to the draft" | >=0.4.0 | >=5.2.1 |
| `data_product_attach_business_domain` | Attaches a business domain to a data product draft. | "Attach a business domain to this draft with domain name: Business Management" | >=0.1.4 | >=5.2.1 |
| `data_product_attach_url_contract` | Attaches a URL contract to a data product draft. | "Attach a url contract to this draft with contract name as policy and contract url as https://example.com/" | >=0.1.4 | >=5.2.1 |
| `data_product_find_delivery_methods_based_on_connection` | Finds available delivery methods based on connection for a specific data asset attached to a draft. | "What delivery methods are available for CustomerReview asset in my data product?" | >=0.1.4 | >=5.2.1 |
| `data_product_add_delivery_methods_to_data_product` | Adds delivery methods to a data asset item of a data product draft. | "Add Download and Data Extract delivery methods to CustomerReview asset in my draft" | >=0.1.4 | >=5.2.1 |
| `data_product_publish_data_product` | Publishes a data product draft to make it available. | "Publish this draft" | >=0.1.4 | >=5.2.1 |
| `data_product_search_data_products` | Searches data products based on a search query or in a domain | "Find me stock related data products" or "Find me data products in Audit domain" | >=0.1.4 | >=5.2.1 |
| `data_product_get_data_contract` | Gets data contract for a specified data product (draft/published) | "Get me data contract for CustomerReview data product" | >=0.5.0 | >=5.3 |
| `data_product_get_contract_templates` | Gets all data contract templates defined in the instance | "What are my contract templates?" | >=0.5.0 | >=5.3 |
| `data_product_attach_contract_template_to_data_product` | Attaches a contract template chosen by the user to a data product draft | "Attach ContractTemplate1 contract template to CustomerReview data product" | >=0.5.0 | >=5.3 |
| `data_product_create_and_attach_custom_contract` | Attaches a custom contract created by the user to a data product draft. This will create a odcs contract from scratch (not from a template) and attach it to the draft. | "I would like to create a contract with name MyCustomContract for research purpose with a limitation that it is only for authorized users. Attach it to CustomerReview data product" | >=0.5.0 | >=5.3 |
| `data_product_get_data_product_details` | Retrieves comprehensive information about a data product including release details, parts/assets with enriched column schemas, primary keys, and subscription information. Provide either data_product_id or data_product_name. | "Get me the details of the CustomerReview data product" or "Show me details for data product with id 12345" or "What are the columns and schema for the Sales data product?" | >=0.6.0 | >=5.3 |

## Data Protection Rule Service
Tools for managing data protection rules.

| Tool Name                     | Description                    | Sample Prompt                                                                                                                | pypi version | CPD version |
|-------------------------------|--------------------------------|------------------------------------------------------------------------------------------------------------------------------|-------------|-------------|
| `create_data_protection_rule_from_text` | Creates data protection rules using natural language description (SaaS only). Automatically validates referenced objects and provides helpful error messages. Uses a two-step workflow: preview first, then create after user confirmation. | "Create me a data protection rule named sample when the asset contains name test and dataclass contains ssn with action allow" or "Create a deny rule for assets with PII classification in the customer database" | >=0.5.1 | >=5.2.1 |
| `create_data_protection_rule` | Creates data protection rules with structured parameters and automatic preview (CP4D). Supports conditions based on asset attributes, data classes, business terms, and tags. Uses a two-step workflow: preview first, then create after user confirmation. All conditions are combined with a single operator (AND or OR). | "Create a deny rule when asset contains dataclass ssn and tag sensitive" or "Create an allow rule for assets owned by admin user" | >=0.5.1 | >=5.2.1 |
| `data_protection_rule_search` | Search data protection rules.  | "Show me all data protection rules with Deny name" or "Find rules related to customer data" | >=0.2.0 | >=5.2.1 |
| `data_protection_rule_search_governance_artifacts` | Search for governance artifacts (classifications, data classes, or glossary terms/business terms) by query to find existing artifacts in IBM Knowledge Catalog. | "Find all classifications related to Personally Identifiable Information data" or "Look up glossary terms about customer information" or "Search for data classes social security data" or "Check if we already have a classification for sensitive personal data" | >=0.5.1 | >=5.2.1 |

## Data Quality Service

Tools for working with data quality of assets.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `get_data_quality_for_asset` | Gets the data quality of a data asset including overall score, consistency, validity, and completeness metrics. | "What is the data quality of 'CustomerTable' asset in 'AgentsDemo' project?" or "Show me quality metrics for 'sales_data' in 'Analytics' catalog" or Following on assets retrieved by `search_asset` tool "What is the data quality of 'eu_daily_trades' asset?" | >=0.6.0 | >=5.3.1 |
| `find_data_quality_rules` | Find and list data quality rules in a project, optionally filtered by rule name. Returns empty list if no rules found. | "Show me all data quality rules in 'DataGovernance' project" or "Find data quality rule named 'validate_email_format' in project 'CRM'" or "List all quality rules in my project" | >=0.6.0 | >=5.3.1 |
| `run_data_quality_rule` | Execute a specific data quality rule to validate data and returns rule details with UI URL. | "Run the 'check_completeness' data quality rule in 'Analytics' project" or "Execute data quality rule 'validate_customer_data' in project 'CRM'" or "Re-run the email validation rule" | >=0.6.0 | >=5.3.1 |
| `create_data_quality_rule_from_sql_query`  | Create a new data quality rule using a SQL query. Optionally specify a data quality dimension (completeness, validity, consistency). | "Create a data quality rule named 'null_check' in project 'DataQuality' using connection 'db_conn' with SQL 'SELECT COUNT(*) FROM customers WHERE email IS NULL'" or "Create a completeness rule 'check_required_fields' with query 'SELECT * FROM orders WHERE customer_id IS NULL'" | >=0.6.0 | >=5.3.1 |
| `set_validates_data_quality_of_relation`  | Link a data quality rule to a specific column in a data asset to report quality scores for that column. | "Link the 'email_validation' rule to the 'email' column in 'customers' asset in 'CRM' project" or "Associate 'check_nulls' rule with 'customer_id' column in 'orders' table" | >=0.6.0 | >=5.3.1 |

## Glossary Service

Tools for working with glossary artifacts (business terms, classifications, data classes, reference data, policies, and rules).

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `explain_glossary_artifact` | Explains detailed information about a glossary artifact by its name. Retrieves and explains metadata about glossary terms, classifications, data classes, reference data, policies, or rules including their definition, purpose, and related metadata. | "Explain the glossary term Customer"| >=0.6.0 | >=5.3.1 |
| `get_glossary_artifacts_for_asset` | Retrieves all business terms and classifications associated with a specific asset. Helps understand the business context and semantic meaning of assets by finding all glossary artifacts that have been assigned to them. | "Get glossary artifacts from catalog GlossaryTestCatalog for asset glossary_asset" | >=0.6.0 | >=5.3.1 |

## Lineage Service

Tools for working with data lineage.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `lineage_convert_to_lineage_id` | Returns lineage ID of a CAMS asset | "What is the lineage id of asset 'asset_id' from project id 'project_id'" or following on a response of `search_asset` tool "Could you show me lineage id of the 'asset name'" | >=0.3.1 | >=5.2.1 |
| `lineage_get_lineage_graph` | Returns lineage graph of lineage assets. | "I would like to get the full lineage graph of lineage asset 'lineage_id'" or following on a response of `lineage_search_lineage_assets` tool "Can you point to the upstream and downstream lineage of this one 'asset name' or "What are the immediate downstream assets of 'asset name'?"| >=0.1.4 | >=5.2.1 |
| `lineage_search_lineage_assets` | Searches assets in the Lineage system. | "Find lineage asset named ACCOUNT_TYPES_STG", "What is the lineage of orders, it's a table with IBM Db2 technology" or  "Find lineage asset that has quality score of less than 65, has a tag dp_source and has business classification PI" | >=0.1.4 | >=5.2.1 |
| `lineage_get_lineage_versions` | Searches for available versions of lineage. | "What are the available versions between 2024 and 2025?" | >=0.6.0 | >=5.4.0 |

## Metadata Enrichment Service

Tools for working with metadata enrichment assets.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `create_or_update_metadata_enrichment_asset` | Creates a metadata enrichment asset in a project. | "Create a metadata enrichment `MDE_HR` for dataset `EMPLOYEE.csv` and `DEPARTMENT.csv` in project `HR_GOVERNANCE` with category `uncategorized` and with objectives `profile`, `dq_gen_constraints` and `analyze_quality`." | >=0.5.0 | >=5.2.1 |
| `execute_metadata_enrichment_asset` | Executes a metadata enrichment by name in the specified project. | "Execute the metadata enrichment `MDE_HR` in the project `HR_GOVERNANCE`." | >=0.4.0 | >=5.2.1 |
| `execute_metadata_enrichment_asset_for_selected_assets` | Executes a metadata enrichment by name in the specified project for the specified data assets. | "Execute the metadata enrichment `MDE_HR` for dataset `EMPLOYEE.csv` in the project `HR_GOVERNANCE`." | >=0.4.0 | >=5.2.1 |
| `execute_data_quality_analysis_for_selected_assets` | Executes data quality analysis for selected assets in a project. | "Execute the data quality analysis for dataset `STAFF.csv` in the project `HR_GOVERNANCE` with category `Sales`." | >=0.4.0 | >=5.2.1 |
| `execute_metadata_expansion_for_selected_assets` | Execute metadata expansion for selected assets in a project. | "Execute the metadata expansion for dataset `ORG.csv` in the project `HR_GOVERNANCE` with category `Finance`." | >=0.4.0 | >=5.2.1 |
| `start_metadata_relationship_analysis` | Starts a relationship analysis for a metadata enrichment area (MDE). Supports primary key (PK) and foreign key (FK) analysis at shallow and deep levels, as well as overlap analysis. | "Start a deep primary key analysis for all datasets in MDE area `MDE_HR` in project `HR_GOVERNANCE`" or "Start a foreign key analysis for datasets `EMPLOYEE.csv` and `DEPARTMENT.csv` in MDE area `MDE_HR` in project `HR_GOVERNANCE` with 50% sampling" | >=0.5.1 | >=5.2.1 |

## Metadata Import Service

Tools for managing metadata import assets and executing import jobs.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `create_metadata_import` | Create a draft metadata import in a project using a connection and scope. | "Create a metadata import in project `MyProject` using connection `my-connection` for first 5 schemas" | >=0.4.0 | >=5.2.1 |
| `list_connection_paths` | List schema/table paths for a connection (paginated). | "List schemas for connection `my-connection` in project `MyProject`" | >=0.4.0 | >=5.2.1|
| `execute_metadata_import` | Executes a metadata import asset to start the import job. This initiates the process of importing assets from the configured data source into the project. The tool returns job details including run ID, current state, and a UI URL for monitoring progress. | "Execute the metadata import `MDI_DB2_Import` in project `DataGovernance`" or "Run the metadata import named `Customer_DB_Import` in project `Analytics`" or "Start the import job for `Sales_Database_MDI` in project `SalesAnalytics`" | >=0.6.0 | >=5.2.1 |

## Projects Service

Tools for managing projects.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `create_project` | Creates a new project with specified name, description, type, storage, and tags. | "Create a new project named CustomerAnalytics with description 'Customer data analysis project'" or "Create a CPD project named SalesData with storage crn:v1:bluemix:public:cloud-object-storage:global:a/abc123:def456::" or "Create a watsonx project named MarketingInsights" | >=0.4.0 | >=5.2.1 |
| `add_or_edit_collaborator` | Add or update one or more collaborators (users or groups) in a project with specified roles. Intelligently searches for users or access groups using fuzzy matching on names and emails. Automatically detects whether members are new or existing and handles them appropriately. Supports role assignment (admin, editor, viewer) with 'viewer' as the default role. | "Add john.doe@example.com as an viewer to project CustomerAnalytics" or "Add users alice@example.com and bob@example.com as admins to project SalesData" or "Update jane.smith@example.com to viewer role in project MarketingInsights" or "Add access group DataScientists as viewer to project Analytics" or "Add user mike@example.com and group Analysts with admin and editor roles to project Research" | >=0.4.0 | >=5.2.1 |

## Reporting Service

Tools for generating and executing SQL queries for reporting purposes.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `reporting_sql_query_generation` | Generates SQL queries from natural language requests for reporting databases. Supports querying data assets, governance artifacts, quality scores, and other metadata. | "Write an SQL query for the project 'Reporting Database' that retrieves the name, quality score, number of rows analyzed, table type, and record count for all data assets where the asset type is 'data_asset'. Sort the results by container ID and asset ID" or "Show the percentage of governance artifacts with assigned stewards for project 'Reporting Database'" | >=0.6.0 | >=5.2.1 |
| `reporting_sql_query_execution` | Executes SQL queries against reporting databases and returns the results. | "Execute the sql query SELECT ca.name AS \"Name\", cda.quality_score AS \"Quality Score\", cda.num_rows_analysed AS \"Num Rows Analysed\", cda.table_type AS \"Table Type\", cda.number_of_records AS \"Number Of Records\" FROM container_assets ca INNER JOIN container_data_assets cda ON cda.container_id = ca.container_id AND cda.asset_id = ca.asset_id WHERE ( ca.asset_type = 'data_asset' ) ORDER BY ca.container_id,ca.asset_id" | >=0.6.0 | >=5.2.1 |

## Search Service

Tools for searching artifacts.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `search_asset` | Searches for data assets based on a search prompt. | "I'm searching for assets about stocks in projects" or "Please search for data related to vehicles in projects" | >=0.1.4 | >=5.2.1 |
| `get_asset_details` | Searches for details of a specific asset including owner name and email. | "Find details of asset TestAsset in TestCatalog catalog" or "Please search for total ratings of asset TestAsset in TestProject project"  or "Find asset attributes of asset TestAsset in TestCatalog catalog" or "Who is the owner of asset TestAsset in TestCatalog catalog?" | >=0.4.0 | >=5.2.1 |
| `search_data_source_definition` | Searches for DSDs based on allowed filters of datasource type, hostname, port, and physical collection. | "Find DSDs with datasource type twitter" or "Find DSDs with database db1" or "Find DSDs with hostname localhost and port 0000" | >=0.4.0 | >=5.2.1 |
| `list_containers` | Lists all available containers - catalogs, projects or spaces. | "List all catalogs" or "Show me all projects" or "List all catalogs and projects" or "Show me all available containers" | >=0.4.0 | >=5.2.1 |
| `find_container` | Finds a specific container (catalog, project or space) by ID or name. | "Find catalog named CustomerData" or "Find project with ID abc-123-def" or "Find the Sales catalog" | >=0.4.0 | >=5.2.1 |
| `search_connection` | Searches for connections based on allowed filters of container, connection name, data source type, or creator. | "Find all connections" or "Find connections with data source type twitter" or "Find connections with connection name test" or "Find connections created by user-123" | >=0.5.0 | >=5.2.1 |

## Text to SQL Service

Tools for creating assets and generating queries from SQL.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `text_to_sql_create_asset_from_sql_query` | Creates a new asset from a SQL query. | "Create an asset 'Kilmers actors' in project `project_id` using connection `connection_id` from 'SELECT * FROM schema.actors a WHERE a.surname = 'Kilmer';'" | >=0.1.4 | >=5.2.1 |
| `text_to_sql_generate_sql_query` | Generates a SQL query from natural language request and schema. | "Find all films with rating R in project named Commercials" or "Find all actors with last name Kilmer from a project named Commercials" | >=0.1.4 | >=5.2.1 |
| `text_to_sql_enable_project_for_text_to_sql` | Enables project for text to sql. | "Please enable project <project_name> for text to SQL" or "Enable text to SQL for my project id <project_id>" | >=0.2.0 | >=5.2.1 |
| `text_to_sql_check_if_onboarding_job_is_completed` | Checks if onboarding job for project completed successfully | "Tell me if project <project_name> has been successfully onboarded for text to SQL?" | >=0.6.0 | >=5.2.1 |

## User Service

Tools for searching and retrieving users, user groups, and user roles.

| Tool Name | Description | Sample Prompt | pypi version | CPD version |
|-----------|-------------|---------------|-------------|-------------|
| `search_user_groups_roles` | Unified tool to search and retrieve users, user groups, or user roles in watsonx.data intelligence. Enables AI agents to quickly find the right identity record by specifying the search type (user, group, or role) and an optional query. Uses intelligent fuzzy matching to find the best matches and returns results with confidence scores and match metadata. Works in both SaaS and CP4D environments (roles search is CP4D only). | "Find user jacob" or "Search for user with email jacob@ibm.com" or "List all users" or "Find group marketing" or "Search for analysts group" or "List all groups" or "Show me all user roles" (CP4D only) or "Find administrator roles" (CP4D only) | >=0.6.0 | >=5.2.1 |

## Usage Guidelines

When using these tools:

1. Ensure you have the necessary permissions for the operation
2. Provide all required parameters as specified in the tool documentation
3. Handle any returned errors appropriately
4. For data product operations, follow the proper sequence (create → attach domain/contract → add delivery methods → publish)

## Multi-step Workflows

Some common multi-step workflows:

### Create and Publish URL Data Product

1. `data_product_create_or_update_url_data_product` → Create a URL data product draft
2. `data_product_attach_business_domain` → Attach a business domain
3. `data_product_attach_url_contract` → Attach a URL contract
4. `data_product_publish_data_product` → Publish the data product

### Create and Publish Data Product from an asset in a container

Note: Container can be a catalog or a project.

1. `data_product_get_assets_from_container` → Get assets from catalog/ Get assets from project
2. `data_product_create_or_update_from_asset_in_container` → Create a data product draft from catalog/project
3. `data_product_attach_business_domain` → Attach a business domain
4. `data_product_attach_url_contract` → Attach a URL contract
5. `data_product_find_delivery_methods_based_on_connection` → Find available delivery methods
6. `data_product_add_delivery_methods_to_data_product` → Add delivery methods
7. `data_product_publish_data_product` → Publish the data product
