# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.constants import PROJECTS_BASE_ENDPOINT
from app.shared.exceptions.base import ServiceError
from app.core.auth import get_bss_account_id


async def get_project_storage_details(project_id: str) -> dict:
    """
    Fetch project details and extract storage information.

    For AWS S3 storage, this includes credentials needed to access the S3 bucket.
    The function requests storage and credentials information via the include parameter.

    Args:
        project_id: Id of the project

    Returns:
        Dictionary containing storage details including type, properties, credentials, etc.
    """

    # Include storage and credentials for AWS S3 access.
    # bss_account_id is required by the SaaS /v2/projects endpoint to scope the request.
    query_params = {
        "include": "storage,credentials",
        "bss_account_id": await get_bss_account_id(),
    }

    project_response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + PROJECTS_BASE_ENDPOINT + "/" + project_id,
        params=query_params,
        tool_name="create_glossary_from_files",
    )

    if not project_response or project_response == {}:
        LOGGER.error(f"Failed to get project details for project id: {project_id}")
        raise ServiceError(f"Unable to find the project details for the project id: {project_id}")

    storage_details = project_response.get("entity", {}).get("storage", {})

    LOGGER.info(f"Successfully found project storage details: type={storage_details.get('type')}")

    return storage_details
