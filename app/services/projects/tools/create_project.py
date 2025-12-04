# This file has been modified with the assistance of IBM Bob AI tool

from app.core.registry import service_registry
from app.services.projects.models.create_project import (
    CreateProjectRequest,
    CreateProjectResponse,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.crn_validator import CRNValidator
import time
from app.services.constants import PROJECTS_BASE_ENDPOINT
from app.core.settings import settings, ENV_MODE_SAAS, ENV_MODE_CPD
from app.shared.exceptions.base import ExternalAPIError
from typing import List, Optional
from enum import Enum

from app.shared.utils.helpers import append_context_to_url
from app.services.tool_utils import is_project_exist_by_name

PROJECT_TYPE_WX = "wx"
PROJECT_TYPE_DF = "df"
PROJECT_TYPE_CPD = "cpd"
PROJECT_TYPE_CPDAAS = "cpdaas"
STORAGE_TYPE_BMCOS = "bmcos_object_storage"
STORAGE_TYPE_ASSETFILES = "assetfiles"
GENERATOR_DF = "df-portal-projects"
GENERATOR_CPD = "cpdaas-portal-projects"

@service_registry.tool(
    name="create_project",
    description="When creating a new project, the system applies a default name i.e. mcp_generated_project_* if none is provided else create project with given name. "
    "If a duplicate project name is detected, an error is thrown with a link to the existing project. "
    "For storage configuration, the system validates available COS storage instances. "
    "When multiple storage instances are found, the user is prompted to specify one by name or CRN before proceeding. "
    "Once the user provides the required storage selection, the project is generated with the validated configuration in the given context.",
)
@auto_context
async def create_project(request: CreateProjectRequest) -> CreateProjectResponse:

    # Create a payload for new project creation
    payload = {}
    payload["name"] = await check_get_project_name(request.name)

    # Set the project description
    mcp_generated_description = "MCP generated project"
    if not is_empty(request.description):
        mcp_generated_description = request.description
    payload["description"] = mcp_generated_description

    # Set the project type and generator, default location will be IBM watsonx projects (Data Fabric)
    project_type, request_type, generator = check_get_type(request.type)
    payload["type"] = project_type
    payload["generator"] = generator

    # Retrieve the storage crn number, implemented only for Cloud Object Storage, Need to handle for cpd assetfiles
    storage = await get_storage(request_storage=request.storage)
    payload["storage"] = storage

    if request.tags and len(request.tags) > 0:
        payload["tags"] = request.tags

    LOGGER.info(
        "Creating a project with name: '%s', storage: '%s'",
        payload["name"],
        storage["type"],
    )

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url)
        + "/transactional"
        + PROJECTS_BASE_ENDPOINT,
        json=payload,
    )

    project_location = prepare_response(response=response, project_type=request_type)
    return CreateProjectResponse(name=payload["name"], location=project_location)

async def check_get_project_name(request_name) -> str:
    # Check if user has not provide the name then add default
    # Assign an MCP-generated project name if the given name already exists
    mcp_generated_name = f"mcp_generated_project_{time.strftime('%Y-%m-%d %H-%M-%S')}"
    if not is_empty(request_name):
        is_exist, context_type, project_id = await is_project_exist_by_name(request_name)
        if not is_exist:
            mcp_generated_name = request_name
        else:
            project_location = ""
            service_url_str = tool_helper_service.base_url
            if service_url_str:
                project_location = append_context_to_url(
                    f"{tool_helper_service.ui_base_url}/projects/{project_id}/",
                    context_type,
                )
            raise ValueError(
                f"Given project name {request_name} already exists. Project URL: {project_location}"
            )
    else:
        raise ValueError(
            f"Project name is required. Suggested name: {mcp_generated_name}"
        )
    return mcp_generated_name

def check_get_type(request_type) -> tuple[str, str, str]:
    project_type = PROJECT_TYPE_WX
    request_project_type = PROJECT_TYPE_DF
    generator = GENERATOR_DF
    if not is_empty(request_type):
        request_type_lower = request_type.lower()
        if PROJECT_TYPE_CPD in request_type_lower:
            project_type = PROJECT_TYPE_CPD
            request_project_type = PROJECT_TYPE_CPDAAS if settings.di_env_mode.upper() == ENV_MODE_SAAS else PROJECT_TYPE_CPD
            generator = GENERATOR_CPD
        elif PROJECT_TYPE_WX in request_type_lower:
            request_project_type = PROJECT_TYPE_WX
        else:
            request_project_type = PROJECT_TYPE_DF
    return project_type, request_project_type, generator


async def get_storage(request_storage):
    """
    Configure storage settings based on environment and request parameters.
    
    Args:
        storage: Dictionary to populate with storage configuration
        request_storage: Storage identifier (CRN or instance name)
    """
    storage = {}
    storage["type"] = get_storage_type()
    
    # Only process cloud storage in SaaS mode
    if settings.di_env_mode.upper() != ENV_MODE_SAAS:
        return storage
    
    # Handle CRN format directly
    if request_storage and request_storage.lower().startswith("crn:"):
        # check for valid crn
        validator = CRNValidator()
        is_valid, error, components = validator.validate_crn(request_storage)
        if is_valid and components:
            storage["resource_crn"] = request_storage
            storage["guid"] = components["resource_id"]
            return storage
        else:
            raise ValueError(f"Invalid CRN format: {error}")
        
    # Fetch COS storage list
    cos_storage_list = await get_cos_storage_list(
        cos_instance=request_storage if request_storage else None
    )
    
    # Validate and set storage from list
    validate_and_set_storage(storage, cos_storage_list, request_storage)
    return storage

def validate_and_set_storage(storage, cos_storage_list, request_storage):
    """Validate COS storage list and set storage configuration."""
    if not cos_storage_list:
        raise ValueError("Cloud Object Storage instance is missing")
    
    if len(cos_storage_list) > 1 and not request_storage:
        storage_names = [
            s.get("name", s.get("crn", "unknown")) for s in cos_storage_list
        ]
        raise ValueError(
            f"Multiple storage instances found: {storage_names}. "
            "Please specify one using its name or CRN and provide new prompt with this."
        )
    
    # Set storage from first (or only) result
    first_storage = cos_storage_list[0]
    storage["resource_crn"] = first_storage.get("crn", "")
    storage["guid"] = first_storage.get("guid", "")

async def get_cos_storage_list(cos_instance=None) -> List:
    if is_empty(cos_instance):
        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.resource_controller_url) + "/v2/resource_instances"
        )
    else:
        response = await tool_helper_service.execute_get_request(
            url=str(tool_helper_service.resource_controller_url)
            + f"/v2/resource_instances?name={cos_instance}"
        )

    resources_list = response.get("resources", [])
    resource_cos = [
        res for res in resources_list if "cloud-object-storage" in res.get("id", "")
    ]
    if not resource_cos:
        raise ExternalAPIError("Cannot create project, no storage resource found")

    return resource_cos

def get_storage_type() -> str:
    """
    Returns the storage type based on the environment.

    Returns:
        str: The storage type.
    """
    if settings.di_env_mode.upper() == ENV_MODE_CPD:
        return STORAGE_TYPE_ASSETFILES
    # elif settings.di_env_mode.upper() == ENV_MODE_AWS:
    #     return "amazon_s3"
    else:
        return STORAGE_TYPE_BMCOS


def is_empty(value) -> bool:
    """Return True if value is None, empty string, or whitespace."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def prepare_response(response, project_type):
    project_location = response.get("location", str)
    project_id = project_location.split(f"{PROJECTS_BASE_ENDPOINT}/")[-1]
    service_url_str = tool_helper_service.ui_base_url
    if service_url_str:
        project_location = append_context_to_url(
            f"{tool_helper_service.ui_base_url}/projects/{project_id}/", project_type
        )

    return project_location


@service_registry.tool(name="create_project",
    description="When creating a new project, the system applies a default name i.e. mcp_generated_project_* if none is provided else create project with given name. "
    "If a duplicate project name is detected, an error is thrown with a link to the existing project. "
    "For storage configuration, the system validates available COS storage instances. "
    "When multiple storage instances are found, the user is prompted to specify one by name or CRN before proceeding. "
    "Once the user provides the required storage selection, the project is generated with the validated configuration in the given context.(Watsonx Orchestrator compatible)")

@auto_context
async def wxo_create_project(
    name: Optional[str] = None,
    description: str = "MCP generated project",
    type: str = PROJECT_TYPE_DF,
    storage: Optional[str] = None,
    tags: List = [],
) -> CreateProjectResponse:
    """Watsonx Orchestrator compatible version that expands CreateProjectRequest object into individual parameters."""

    request = CreateProjectRequest(
        name=name, description=description, type=type, storage=storage, tags=tags
    )

    # Call the original create_project function
    return await create_project(request)
