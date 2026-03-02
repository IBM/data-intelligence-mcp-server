# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import time

from app.core.auth import get_bss_account_id, get_iam_url, get_user_identifier
from app.core.registry import service_registry
from app.services.constants import (
    CATALOGS_BASE_ENDPOINT,
    GEN_AI_ONBOARD_API,
    GROUPS_BASE_ENDPOINT,
    PROJECTS_BASE_ENDPOINT,
)
from app.services.text_to_sql.models.enable_project_for_text_to_sql import (
    EnableProjectForTextToSqlRequest,
    EnableProjectForTextToSqlResponse,
)
from app.services.tool_utils import find_project_id, get_onboarding_job_run_url
from app.shared.exceptions.base import ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import confirm_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


async def _is_admin_of_container(container_id, container_type) -> bool:
    """
    Check if the current user is an admin of the container.

    Args:
        container_id (str): ID of the container to check.
        container_type (str): Type of the container.

    Returns:
    bool: True if the current user is an admin of the container, False otherwise.
    """

    params = {"roles": "admin"}
    if container_type == "catalog":
        params["limit"] = 100
        params["member_type"] = "all"

    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}{CATALOGS_BASE_ENDPOINT if container_type == 'catalog' else PROJECTS_BASE_ENDPOINT}/{container_id}/members",
        params=params,
        tool_name="enable_container_for_text_to_sql",
    )

    if [
        member
        for member in response.get("members", [])
        if member.get("user_iam_id" if container_type == "catalog" else "id", "")
        == await get_user_identifier()
    ]:
        return True

    # Filter group type container admin members
    group_members = [
        member.get("access_group_id" if container_type == "catalog" else "id", "")
        for member in response.get("members", [])
        if member.get("type", "") == "group" or "access_group_id" in member.keys()
    ]
    if not group_members:
        return False

    # Retrieve user's group memberships
    response = await tool_helper_service.execute_get_request(
        url=f"{get_iam_url()}{GROUPS_BASE_ENDPOINT}",
        params={"account_id": await get_bss_account_id(), "limit": 100},
        tool_name="enable_container_for_text_to_sql",
    )

    # Check if any of user's groups are container admin members
    user_groups = [
        user_group.get("id", "") for user_group in response.get("groups", [])
    ]
    return any([group_id in group_members for group_id in user_groups])


@service_registry.tool(
    name="text_to_sql_enable_project_for_text_to_sql",
    description="This tool enables the specified project for Text To SQL.",
)
@auto_context
async def enable_project_for_text_to_sql(
    input: EnableProjectForTextToSqlRequest,
) -> EnableProjectForTextToSqlResponse:
    LOGGER.info(
        "Calling enable_project_for_text_to_sql, project_id_or_name: %s",
        input.project_id_or_name,
    )
    project_id = await confirm_uuid(input.project_id_or_name, find_project_id)

    if not await _is_admin_of_container(project_id, "project"):
        raise ServiceError(
            f"Tool enable_project_for_text_to_sql failed because user is not admin of project {input.project_id_or_name}"
        )

    params = {
        "container_type": "project",
        "container_id": project_id,
    }

    payload = {
        "containers": [{"container_id": project_id, "container_type": "project"}],
        "description": "Onboard the asset containers for text2sql capability",
        "name": f"Onboard for generative AI {time.strftime('%Y-%m-%d %H-%M-%S')}",
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GEN_AI_ONBOARD_API,
        params=params,
        json=payload,
    )

    job_id = response.get("job_id", "")
    run_id = response.get("run_id", "")

    return EnableProjectForTextToSqlResponse(
        message=f"UI link to the onboarding job for enabling Project {input.project_id_or_name} for Text To SQL {get_onboarding_job_run_url(project_id, job_id, run_id)}"
    )


@service_registry.tool(
    name="text_to_sql_enable_project_for_text_to_sql",
    description="This tool enables the specified project for Text To SQL.",
)
@auto_context
async def wxo_enable_project_for_text_to_sql(
    project_id_or_name: str,
) -> EnableProjectForTextToSqlResponse:
    """Watsonx Orchestrator compatible version that expands EnableProjectForTextToSqlRequest object into individual parameters."""

    request = EnableProjectForTextToSqlRequest(project_id_or_name=project_id_or_name)

    # Call the original enable_project_for_text_to_sql function
    return await enable_project_for_text_to_sql(request)
