# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.auth import get_access_token
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
from app.services.constants import SEARCH_PATH

async def check_rule_exists(rule_name: str) -> bool:
    """Check if a data protection rule with the given name already exists."""
    auth = await get_access_token()
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": auth
    }
    client = get_http_client()

    # Construct the Elasticsearch-style query payload
    search_query = {
        "query": {
            "bool": {
                "must": [
                    { "term": { "metadata.name.keyword": rule_name } }
                ],
                "filter": [
                    { "term": { "metadata.artifact_type": "data_protection_rule" } }
                ]
            }
        }
    }

    response = await client.post(
        f"{settings.di_service_url}{SEARCH_PATH}",
        headers=headers,
        data=search_query,
    )
    rule_count = response.get("size", 0)
    return  rule_count > 0


