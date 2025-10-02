# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.auth import get_access_token
from app.services.data_protection_rules.models.create_rule import Entity, RuleRhsTermResponse
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
from app.services.constants import SEARCH_PATH


async def search_rhs_terms(term_name: str, artifact_type: str) -> RuleRhsTermResponse:
    """Search for RHS terms matching the given term name."""
    auth = await get_access_token()
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": auth
    }
    client = get_http_client()

    # Construct the Elasticsearch-style query payload
    search_query = {
            "size": 50,
            "from": 0,
            "query": {
                "bool": {
                    "must": {
                        "gs_user_query": {
                            "search_string": term_name,
                            "search_fields": ["metadata.name", "metadata.description"]
                        }
                    },
                    "filter": [
                        {"term": {"metadata.artifact_type": artifact_type}}
                    ]
                }
            },
            "sort": [
                {"metadata.name.keyword": "asc"}
            ]
        }

    response = await client.post(
        f"{settings.di_service_url}{SEARCH_PATH}",
        headers=headers,
        data=search_query,
    )

    # Extract global IDs from response, filtering by state and enabled status
    entities = []
    total_count = 0

    if response and "size" in response:
        total_count = response.get("size", 0)

        for row in response["rows"]:
            # Check if metadata.state is PUBLISHED
            metadata = row.get("metadata", {})
            if metadata.get("state") != "PUBLISHED":
                continue
            name = metadata.get("name", "N/A")

            # Check if entity.artifacts.enabled is true and extract global_id
            entity = row.get("entity", {})
            artifacts = entity.get("artifacts", {})

            if artifacts.get("enabled") and "global_id" in artifacts:
                entities.append(Entity(name=name, globalid="$" + artifacts["global_id"]))


        return RuleRhsTermResponse(
            entities=entities,
            total_count=total_count,
            search_string=term_name
        )
