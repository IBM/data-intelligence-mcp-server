# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Literal
from app.core.registry import service_registry
from app.services.data_protection_rules.models.search_glossary import (
    SearchGovernanceArtifactRequest,
    SearchGovernanceArtifactResponse,
    GovernanceArtifact,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.core.auth import get_access_token
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
from app.shared.logging import LOGGER, auto_context
from app.services.constants import SEARCH_PATH


@service_registry.tool(
    name="data_protection_rule_search_governance_artifacts",
    description="""
    This tool searches for governance artifacts (classifications, data classes, or glossary terms(another name is business term)) by query and returns matching results.
    Use this tool to search for existing governance artifacts by correct names in IBM Knowledge Catalog.
    
    Examples:
        - "Find all classifications related to Personally Identifiable Information data"
        - "Look up glossary terms about customer information"
        - "Look up business terms about account"
        - "Search for data classes social security data"
        - "Check if we already have a classification for sensitive personal data"
    """,
    tags={"search", "data_protection_rules", "governance"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def search_governance_artifacts(
    request: SearchGovernanceArtifactRequest,
) -> SearchGovernanceArtifactResponse:
    """Search for governance artifacts by query and return matching results."""
    LOGGER.info(
        f"In the data_protection_rule_search_governance_artifacts tool, searching for {request.rhs_type} with query '{request.query_value}'."
    )

    # Validate rhs_type
    if request.rhs_type not in ["classification", "data_class", "glossary_term"]:
        LOGGER.error(
            f"Invalid rhs_type: {request.rhs_type}. Must be one of: classification, data_class, glossary_term."
        )
        return SearchGovernanceArtifactResponse(
            count=0,
            artifacts=[],
            message=f"Invalid rhs_type '{request.rhs_type}'. Must be one of: 'classification', 'data_class', 'glossary_term'."
        )

    # Validate query_value
    if not request.query_value or request.query_value.strip() == "":
        LOGGER.error("query_value cannot be empty.")
        return SearchGovernanceArtifactResponse(
            count=0,
            artifacts=[],
            message="query_value cannot be empty."
        )

    try:
        # Execute search
        results = await get_rhs_terms_by_query(request.rhs_type, request.query_value)
        
        if not results:
            LOGGER.info(
                f"No {request.rhs_type} found matching query '{request.query_value}'."
            )
            return SearchGovernanceArtifactResponse(
                count=0,
                artifacts=[],
                message=f"Cannot find '{request.query_value}' in {request.rhs_type}. Please use correct query or artifact type and try again."
            )
        
        # Convert results to GovernanceArtifact objects
        artifacts = [
            GovernanceArtifact(name=result["name"], global_id=result["global_id"])
            for result in results
        ]
        
        LOGGER.info(f"Found {len(artifacts)} {request.rhs_type} artifacts.")
        
        artifact_names = "\n".join([artifact.name for artifact in artifacts])
        return SearchGovernanceArtifactResponse(
            count=len(artifacts),
            artifacts=artifacts,
            message=f"Found {len(artifacts)} {request.rhs_type} artifact(s):\n{artifact_names}"
        )

    except ExternalAPIError as e:
        LOGGER.error(
            f"Failed to run data_protection_rule_search_governance_artifacts tool. External API error: {str(e)}"
        )
        raise ExternalAPIError(
            f"Failed to search governance artifacts. External API error: {str(e)}"
        )
    except Exception as e:
        LOGGER.error(
            f"Failed to run data_protection_rule_search_governance_artifacts tool. Unexpected error: {str(e)}"
        )
        raise ServiceError(
            f"Failed to search governance artifacts. Unexpected error: {str(e)}"
        )


@service_registry.tool(
    name="data_protection_rule_search_governance_artifacts",
    description="""
    This tool searches for governance artifacts (classifications, data classes, or glossary terms) by query and returns matching results.
    Use this tool to search for existing governance artifacts by correct names in IBM Knowledge Catalog.
    
    Examples:
        - "Find all classifications related to Personally Identifiable Information data"
        - "Look up glossary terms about customer information"
        - "Look up business terms about account"
        - "Search for data classes social security data"
        - "Check if we already have a classification for sensitive personal data"
    """,
    tags={"search", "data_protection_rules", "governance"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def wxo_search_governance_artifacts(
    rhs_type: Literal["classification", "data_class", "glossary_term"],
    query_value: str
) -> SearchGovernanceArtifactResponse:
    """Watsonx Orchestrator compatible version that expands SearchGovernanceArtifactRequest object into individual parameters."""
    
    request = SearchGovernanceArtifactRequest(
        rhs_type=rhs_type,
        query_value=query_value
    )
    
    # Call the original search_governance_artifacts function
    return await search_governance_artifacts(request)


async def get_rhs_terms_by_query(rhs_type: str, query: str):
    """
    Search for RHS terms by query and return a list of terms with name and global_id.
    Returns None if no results found.

    Args:
        rhs_type (str): limit on one of those items: classification, data_class, glossary_term
        query (str): The search query string

    Returns:
        list[dict] | None: List of dictionaries with 'name' and 'global_id' for each term,
                          or None if no results found
    """
    # Call the search function
    response = await search_rhs_terms(rhs_type, query)

    # Check if we got any results
    if response.get('size', 0) == 0:
        return None

    # Extract name and global_id from each item
    results = []
    for item in response.get('rows', []):
        try:
            name = item['metadata']['name']
            global_id = item['entity']['artifacts']['global_id']
            results.append({
                'name': name,
                'global_id': global_id
            })
        except (KeyError, TypeError):
            # Skip items with missing data
            continue

    return results if results else None


async def search_rhs_terms(rhs_type: str, query: str):
    """
    Search for RHS terms using the search API.
    
    Args:
        rhs_type: classification | data_class | glossary_term
        query: The search query string
        
    Returns:
        dict: Search response from the API
    """
    token = await get_access_token()
    
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": token,
    }
    
    json_body = {
        "size": 10000,
        "from": "0",
        "_source": [
            "metadata.name",
            "artifact_id",
            "metadata.artifact_type",
            "categories.primary_category_name",
            "entity.artifacts.version_id",
            "entity.artifacts.global_id"
        ],
        "query": {
            "bool": {
                "must": [
                    {"match": {"provider_type_id": "glossary"}},
                    {"match": {"metadata.artifact_type": rhs_type}},
                    {"match": {"metadata.name": query}}
                ]
            }
        }
    }
    
    client = get_http_client()
    
    try:
        response = await client.post(
            url=f"{settings.di_service_url}{SEARCH_PATH}?role=viewer&auth_scope=all",
            headers=headers,
            data=json_body,
        )
        return response
    except Exception as e:
        LOGGER.error(f"Error searching RHS terms: {str(e)}")
        raise ExternalAPIError(f"Failed to search RHS terms: {str(e)}")

# Made with Bob
