# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.auth import get_access_token
from app.services.data_protection_rules.models.create_rule import Rule
from app.shared.utils.http_client import get_http_client
from app.services.constants import JSON_CONTENT_TYPE
from app.core.settings import settings
from app.services.constants import DPR_RULES

async def create_rule_util(rule: Rule) -> str:
    """Create a data protection rule in the system."""
    auth = await get_access_token()
    headers = {
        "Content-Type": JSON_CONTENT_TYPE,
        "Authorization": auth
    }
    client = get_http_client()


    response = await client.post(
        f"{settings.di_service_url}{DPR_RULES}",
        headers=headers,
        data=rule.model_dump(),
    )

    rule_id = response.get("metadata", {}).get("guid", "")
    return  rule_id


