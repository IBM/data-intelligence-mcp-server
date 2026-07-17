# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import time
from typing import Literal, Optional, Annotated
from pydantic import Field

from app.core.auth import get_bss_account_id, get_iam_url, get_user_identifier
from app.core.registry import service_registry
from app.services.constants import (
    GEN_AI_ONBOARD_API,
    GROUPS_BASE_ENDPOINT,
)
from app.services.text_to_sql.models.enable_container_for_text_to_sql import (
    EnableContainerForTextToSqlRequest,
    EnableContainerForTextToSqlResponse,
)
from app.services.tool_utils import find_project_id, find_catalog_id, get_onboarding_job_run_url, build_container_members_url
from app.shared.exceptions.base import ServiceError, ValidationError
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
        params["limit"] = "100"
        params["member_type"] = "all"

    response = await tool_helper_service.execute_get_request(
        url=build_container_members_url(container_id, container_type),
        params=params,
        tool_name="enable_container_for_text_to_sql",
    )

    return await check_if_user_has_role(response, container_type)

async def _is_editor_of_container(container_id, container_type) -> bool:
    """
    Check if the current user is an editor of the container.

    Args:
        container_id (str): ID of the container to check.
        container_type (str): Type of the container.

    Returns:
    bool: True if the current user is an editor of the container, False otherwise.
    """
    params = {"roles": "editor"}
    if container_type == "catalog":
        params["limit"] = "100"
        params["member_type"] = "all"

    response = await tool_helper_service.execute_get_request(
        url=build_container_members_url(container_id, container_type),
        params=params,
        tool_name="enable_container_for_text_to_sql",
    )

    return await check_if_user_has_role(response, container_type)

async def check_if_user_has_role(response: dict | bytes, container_type: str) -> bool:
    """
    Check if the user has the required role in the response.
    Args:
        response (dict): The response from the tool helper service.
    Returns:
        bool: True if the user has the required role in the response, False otherwise.
    """
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
    return any(group_id in group_members for group_id in user_groups)


async def _enable_container_for_text_to_sql(
    input: EnableContainerForTextToSqlRequest,
) -> EnableContainerForTextToSqlResponse:

    LOGGER.info(
        "Calling enable_container_for_text_to_sql, container_id_or_name: %s, container_type: %s, project_id_or_name: %s",
        input.container_id_or_name,
        input.container_type,
        input.project_id_or_name,
    )

    container_id = ""
    project_for_onboarding = ""
    if input.container_type == "project":
        container_id = await confirm_uuid(input.container_id_or_name, find_project_id)
        project_for_onboarding = container_id
    elif input.container_type == "catalog":
        if not input.project_id_or_name:
            raise ValidationError(
                "project_id_or_name is required when onboarding a catalog to determine the project to create the onboarding job in.",
                remediation_steps="Provide project_id_or_name parameter of existing project.",
                tool="enable_container_for_text_to_sql"
            )
        container_id = await confirm_uuid(input.container_id_or_name, find_catalog_id)
        project_for_onboarding = await confirm_uuid(input.project_id_or_name, find_project_id)
        if not await _is_admin_of_container(project_for_onboarding, "project") and not await _is_editor_of_container(project_for_onboarding, "project"):
            raise ServiceError(
                f"Tool enable_container_for_text_to_sql failed because user is not admin or editor of project {project_for_onboarding}",
                remediation_steps="Provide project_id_or_name for the project where user have admin or editor role",
                tool="enable_container_for_text_to_sql"
            )

    if not await _is_admin_of_container(container_id, input.container_type):
        raise ServiceError(
            f"Tool enable_container_for_text_to_sql failed because user is not admin of {input.container_type} {container_id}",
                remediation_steps="Provide container_id_or_name for the container where user have admin role",
                tool="enable_container_for_text_to_sql"
        )

    params = {
        "container_type": "project",
        "container_id": project_for_onboarding,
    }

    payload = {
        "containers": [{"container_id": container_id, "container_type": input.container_type}],
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

    return EnableContainerForTextToSqlResponse(
        message=f"UI link to the onboarding job for enabling {input.container_type} {container_id} for Text To SQL {get_onboarding_job_run_url(project_for_onboarding, 'project', job_id, run_id)}"
    )


@service_registry.tool(
    name="enable_container_for_text_to_sql",
    annotations={
        "title": "Enable a Project or Catalog for Text-to-SQL",
        "destructiveHint": True
    },
    description="""
                Use this tool when you need to enables the specified project or catalog for Text To SQL.
                When onboarding a non-project container (for ex: catalog), the user needs
                to provide an additional the project_id_or_name i.e the name or UUID of '
                the project to create the onboarding job in. This is not needed in case of
                onboarding a project container.
                Example: Onboard agent-test project.
                In this case, container_id_or_name will be agent-test, container_type will be project
                and project_id_or_name will be None.
                Example: Onboard agent-test catalog with agent-job project.
                In this case, container_id_or_name will be agent-test, container_type will be catalog
                and project_id_or_name will be agent-job.
                Returns: A message with the UI link to monitor the onboarding job that enables the specified project or catalog for Text-to-SQL functionality.
                """,
)
@auto_context   
async def enable_container_for_text_to_sql(
    container_id_or_name: Annotated[str, Field(description="Name or UUID of the container to onboard.")],
    container_type: Annotated[Literal["catalog", "project"], Field(description="The container type of the container to onboard, project by default.")] = "project",
    project_id_or_name: Annotated[Optional[str], Field(description="Name or UUID of the project to create the onboarding job in, only required when onboarding non-project container.")] = None
) -> EnableContainerForTextToSqlResponse:
    """Wrapper version that expands EnableProjectForTextToSqlRequest object into individual parameters."""

    request = EnableContainerForTextToSqlRequest(
        container_id_or_name=container_id_or_name, 
        container_type=container_type, 
        project_id_or_name=project_id_or_name
    )

    # Call the original enable_container_for_text_to_sql function
    return await _enable_container_for_text_to_sql(request)
