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
from app.core.auth import is_aws_environment
from app.shared.exceptions.base import ExternalAPIError, ValidationError
from typing import Annotated, List, Optional
from pydantic import Field

from app.shared.utils.helpers import append_context_to_url, get_project_or_space_type_based_on_context
from app.services.tool_utils import (
    is_project_exist_by_name,
    get_response_context,
    PROJECT_TYPE_CPD,
    RESPONSE_CONTEXT_ICP4DATA,
    RESPONSE_TYPE_CPDAAS,
    RESPONSE_TYPE_DF,
)

PROJECT_TYPE_WX = "wx"
STORAGE_TYPE_BMCOS = "bmcos_object_storage"
AWS_STORAGE = "amazon_s3"
STORAGE_TYPE_ASSETFILES = "assetfiles"
GENERATOR_DF = "df-portal-projects"
GENERATOR_CPDAAS = "cpdaas-portal-projects"
GENERATOR_CPD = "icp4data-portal-projects"

async def _create_project(request: CreateProjectRequest) -> CreateProjectResponse:

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


def build_project_location_url(project_id: str, project_type: str) -> str:
    """Build the project location URL based on environment and context type.
    
    Args:
        project_id: The ID of the existing project
        context_type: The context type of the project (cpd or wx)
        
    Returns:
        The full project location URL
    """
    if not tool_helper_service.base_url:
        return ""
    
    context_type = get_response_context(project_type)
    return append_context_to_url(
        f"{tool_helper_service.ui_base_url}/projects/{project_id}/",
        context_type
    )


async def check_get_project_name(request_name) -> str:
    """Check and validate the project name, returning a valid name or raising an error.
    
    Args:
        request_name: The requested project name from the user
        
    Returns:
        A valid project name
        
    Raises:
        ValidationError: If the name is empty or already exists
    """
    if is_empty(request_name):
        raise ValidationError(
            "Project name is required. Please provide a meaningful name for your project.",
            tool="create_project"
        )
    
    is_exist, project_type, project_id = await is_project_exist_by_name(request_name)
    if is_exist:
        project_location = build_project_location_url(project_id, project_type)
        raise ValidationError(
            f"Given project name {request_name} already exists. Project URL: {project_location}",
            remediation_steps="Call the list_containers tool with container_type set to 'project' to retrieve the list of available projects. Then provide a project name that does not exist in that list.",
            tool="create_project"
        )
    
    return request_name

def check_get_type(request_type: str | None) -> tuple[str, str, str]:
    """
    Determine project type, request type, and generator based on environment and request.
        
    Args:
        request_type: The requested project type (optional, case-insensitive)
        
    Returns:
        tuple: (project_type, request_project_type, generator)
            - project_type: Internal project type identifier ('cpd' or 'wx')
            - request_project_type: Response context type for UI
            - generator: Project generator identifier
    """
    # CPD (On-Prem) environment - always returns CPD configuration
    if settings.di_env_mode.upper() == ENV_MODE_CPD:
        return PROJECT_TYPE_CPD, RESPONSE_CONTEXT_ICP4DATA, GENERATOR_CPD
    
    # Normalize and validate request_type once
    request_type_normalized = None
    if request_type and not is_empty(request_type):
        request_type_normalized = request_type.lower().strip()
    
    # Check if CPD type is explicitly requested
    if request_type_normalized and PROJECT_TYPE_CPD in request_type_normalized:
        return PROJECT_TYPE_CPD, RESPONSE_TYPE_CPDAAS, GENERATOR_CPDAAS
    
    # If no explicit request, use context-based default
    if not request_type_normalized:
        project_type_based_context = get_project_or_space_type_based_on_context()
        if project_type_based_context == PROJECT_TYPE_CPD:
            return PROJECT_TYPE_CPD, RESPONSE_TYPE_CPDAAS, GENERATOR_CPDAAS
        # Default to DF for 'wx' context or None
        return PROJECT_TYPE_WX, RESPONSE_TYPE_DF, GENERATOR_DF
    
    # Default to DF for any other explicit request type
    return PROJECT_TYPE_WX, RESPONSE_TYPE_DF, GENERATOR_DF


async def get_storage(request_storage):
    """
    Configure storage settings based on environment and request parameters.
    
    Args:
        storage: Dictionary to populate with storage configuration
        request_storage: Storage identifier (CRN or instance name)
    """
    storage = {}
    storage["type"] = get_storage_type()

    # CPD (assetfiles) uses platform-managed storage, so no IBM Cloud Object
    # Storage resource lookup is needed outside of IBM Cloud SaaS mode.
    if settings.di_env_mode.upper() != ENV_MODE_SAAS:
        return storage

    # If the user explicitly provided a CRN, validate its format up front so a
    # malformed value is rejected on any cloud (IBM Cloud or AWS) rather than
    # being silently ignored.
    crn_components = None
    if request_storage and request_storage.lower().startswith("crn:"):
        validator = CRNValidator()
        is_valid, error, crn_components = validator.validate_crn(request_storage)
        if not is_valid or not crn_components:
            raise ValidationError(f"Invalid CRN format: {error}",
                                  tool="create_project")

    # AWS uses platform-managed Amazon S3 storage. The transactional projects API
    # requires a `properties` object on the storage; sending an empty object lets
    # the platform auto-provision the S3 bucket from the account's storage
    # delegation settings (role_arn, bucket_region, bucket_name are filled in by
    # the platform). IBM Cloud Object Storage CRNs do not apply on AWS.
    if is_aws_environment():
        storage["properties"] = {}
        return storage

    # IBM Cloud SaaS: a valid COS CRN can be used directly.
    if crn_components:
        storage["resource_crn"] = request_storage
        storage["guid"] = crn_components["resource_id"]
        return storage

    # Otherwise look up the COS instance from the IBM Cloud resource controller.

    cos_storage_list = await get_cos_storage_list(
        cos_instance=request_storage if request_storage else None
    )

    # Validate and set storage from list
    validate_and_set_storage(storage, cos_storage_list, request_storage)
    return storage

def validate_and_set_storage(storage, cos_storage_list, request_storage):
    """Validate COS storage list and set storage configuration."""
    if not cos_storage_list:
        raise ValidationError("Cloud Object Storage instance is missing",
                              tool="create_project")
    
    if len(cos_storage_list) > 1 and not request_storage:
        storage_names = [
            s.get("name", s.get("crn", "unknown")) for s in cos_storage_list
        ]
        raise ValidationError(
            f"Multiple storage instances found: {storage_names}. "
            "Please specify one using its name or CRN and provide new prompt with this.",
            tool="create_project"
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
        raise ExternalAPIError("Cannot create project, no storage resource found",
                               tool="create_project")

    return resource_cos

def get_storage_type() -> str:
    """
    Returns the storage type based on the environment.

    Returns:
        str: The storage type.
    """
    if settings.di_env_mode.upper() == ENV_MODE_CPD:
        return STORAGE_TYPE_ASSETFILES
    elif is_aws_environment():
        return AWS_STORAGE
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
    description="Use this tool when you need to creates a new project with the specified name. "
    "A project name is required - if not provided, ask the user for a meaningful name. "
    "If a duplicate project name is detected, an error is thrown with a link to the existing project. "
    "For storage configuration, the system validates available COS storage instances. "
    "When multiple storage instances are found, the user is prompted to specify one by name or CRN before proceeding. "
    "Once the user provides the required information, the project is generated with the validated configuration in the given context." \
    "Return: The name of the newly created project and the API location URL to access it.",
    annotations={
        "title": "Creates a New Project with the Given Name",
        "destructiveHint": True
    })

@auto_context
async def create_project(
    name: Annotated[Optional[str], Field(description="The name of the new project")] = None,
    description: Annotated[str, Field(description="A description for the new project")] = "MCP generated project",
    type: Annotated[Optional[str], Field(description="The project type: 'cpd' for IBM Cloud Pak for Data projects, 'wx' or 'df' for IBM watsonx/Data Fabric projects")] = None,
    storage: Annotated[Optional[str], Field(description="Storage identifier: Cloud Object Storage instance name or CRN (for SaaS), or 'assetfiles' (for CPD)")] = None,
    tags: Annotated[List, Field(description="List of user-defined tags to attach to the project")] = [],
) -> CreateProjectResponse:
    """Wrapper that expands CreateProjectRequest object into individual parameters."""

    request = CreateProjectRequest(
        name=name, description=description, type=type, storage=storage, tags=tags
    )

    # Call the original create_project function
    return await _create_project(request)
