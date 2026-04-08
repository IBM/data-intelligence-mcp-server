# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

MAX_SEARCH_RESULTS: int = 100

# Container type constant for searching across both projects and catalogs
CONTAINER_TYPE_PROJECT_AND_CATALOG = "project_and_catalog"

VALID_CONTAINER_TYPES: list[str] = ["project", "catalog", CONTAINER_TYPE_PROJECT_AND_CATALOG]

VALID_ARTIFACT_TYPES: list[str] = [
    "data_asset",
    "data_asset_column",
    "connection",
    "ibm_data_source",
    "data_rule",
    "data_rule_definition",
    "glossary_term",
    "category",
    "job",
    "classification",
    "data_class",
    "data_protection_rule",
    "reference_data",
    "metadata_enrichment_area",
    "metadata_import"
]

# Named entities that can be used within names_to_ids text2query API request body.
VALID_NAMED_ENTITIES: list[str] = [
    "connection",
    "metadata_import",
    "metadata_enrichment_area",
    "category"
]

# Governance artifact types that share the glossary-term URL pattern.
GOVERNANCE_GLOSSARY_PATHS: dict[str, str] = {    
    "glossary_term": "terms",
    "classification": "classifications",
    "data_class": "data-classes",
    "reference_data": "refdata",
}

TOOL_DESCRIPTION = """Understand user's request about searched items and return list of fetched data.
                       This tool is capable of generating dynamic search queries and executing them against search engine based on natural language input.
                       It may find data based on items metadata ( linked connection, tags, assigned business terms, schema details, etc.)
                       It may find different types of data. Possible artifact types: [data_asset, data_asset_column, connection, ibm_data_source, data_rule, data_rule_definition, glossary_term, category, job, classification, data_class, data_protection_rule, reference_data, metadata_import, metadata_enrichment_area ]
                       This function takes a user's search prompt as input and may take container type: project or catalog, project_and_catalog. Default container type to project_and_catalog.
                       It can only find items in the specified container when container_name is specified in the request.
                       It then returns list of items that has been found. Response object contains also query that was generated based on user's input. Always include this as a part of your response.
                       The response may include an optional message field with additional information. Always include the message in your response if present.

                       Examples:
                        - Give me assets tagged customer in project AgentTest: search_prompt="Give me assets tagged customer in project AgentTest", container_name="AgentTest", container_type="project", artifact_types=["data_asset"]
                        - Find assets with business term Address in catalogs: search_prompt="Find assets with business term Address in catalogs", container_type="catalog", artifact_types=["data_asset"]
                        - Find connections with 'postgresql' in name in project AgentTest: search_prompt="Find connections with 'postgresql' in name in project AgentTest", container_name="AgentTest", container_type="project", artifact_types=["connection"]
                        - Find data source definitions: search_prompt="Find data source definitions", artifact_types=["ibm_data_source"]
                        - Find assets modified today in AgentTest: search_prompt="Find assets modified today in AgentTest", container_name="AgentTest", artifact_types=["data_asset"]
                        - Find asset Car in project: search_prompt="Find asset Car in project", container_type="project"
                        - Find data related to policies: search_prompt="Find data related to policies", artifact_types=["data_asset"]
                        - List data with classification PII: search_prompt="List data with classification PII"
                        - Search for assets with business term Address: search_prompt="Search for assets with business term Address"
                        - Give me list of assets created after 4 Nov 2025: search_prompt="Give me list of assets created after 4 Nov 2025"
                        - List business terms: search_prompt="List business terms", artifact_types=["glossary_term"]
                        - List glossary terms: search_prompt="List glossary terms", artifact_types=["glossary_term"]
                        - Search for columns with naming pattern 'orders': search_prompt="Search for columns with naming pattern 'orders'", artifact_types=["data_asset_column"]
                        - Find data quality rules: search_prompt="Find data quality rules", artifact_types=["data_rule"]
                        - Find data quality definitions: search_prompt="Find data quality definitions", artifact_types=["data_rule_definition"]
                        - Search for assets and columns in project AgentTest: search_prompt="Search for assets and columns in project AgentTest", container_type="project", container_name="AgentTest", artifact_types=["data_asset", "data_asset_column"]
                        - Search for assets in project AgentsDemo that are sourced from connection testConnName: search_prompt="Search for assets in project AgentsDemo that are sourced from connection testConnName", container_name="AgentsDemo", container_type="project", names_mapping=[{"name": "testConnName", "type": "connection"}]
                        - Search for assets in project AgentsDemo that are from MDI testMDIName: search_prompt="Search for assets in project AgentsDemo that are from MDI testMDIName", container_name="AgentsDemo", container_type="project", names_mapping=[{"name": "testMDIName", "type": "metadata_import"}]
                       
                       IMPORTANT CONSTRAINTS:
                       - values are wrapped in the request
                       - search_prompt cannot be empty
                       - ALWAYS pass the user's FULL ORIGINAL QUESTION exactly as provided to search_prompt parameter. DO NOT try to optimise or shorten the questions. It may have impact on the quality of search results
                       - container_type must be one of: "catalog", "project", "project_and_catalog"
                       - If the user asks about specific container (project or catalog) by its name add this value as container_name parameter.
                       - If the user specified a type of asset, populate the 'artifact_types' parameter with that value. Otherwise, leave the 'artifact_types' parameter as "data_asset".
                            Possible artifact types: [data_asset, data_asset_column, connection, ibm_data_source, data_rule, data_rule_definition, glossary_term, category, job, classification, data_class, data_protection_rule, reference_data ]
                            Use only types specified in the list above.
                       - If the user mentions named entities (like specific connection names or metadata import area names) that are NOT catalog/project names, use the names_mapping parameter.
                            Format: [{"name": "entityName", "type": "entityType"}]
                            Supported types: "connection", "metadata_import", "metadata_enrichment_area", "category"
                            The tool will automatically resolve these names to IDs and pass them to the query generation API.
                       - Invalid values will result in errors
                       - ALWAYS include subset or whole list of found data in your response with all details.
                       - If there's search query included in the response please return it."""

# Made with Bob
