# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from string import Template
import json
import uuid
from typing import Optional, List, Union
from app.shared.logging import LOGGER, auto_context
from app.core.registry import service_registry
from app.services.tool_utils import find_project_id, find_connection_id
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.logging import LOGGER

from app.services.metadata_import.models.create_metadata_import import (
    CreateMetadataImportRequest,
    CreateMetadataImportResponse,
    MetadataImportRequest,
    MetadataImport,
    MetadataImportScope,
)
from app.services.metadata_import.tools.list_connection_paths import list_connection_paths, wxo_list_connection_paths


def get_metadata_import_service_url() -> str:
    """Get the metadata import service URL."""
    return f"{tool_helper_service.base_url}/v2/metadata_imports"


def get_metadata_import_resource_uri(mdi_id: str, project_id: str) -> str:
    """Get the metadata import resource URI."""
    template = Template(
        f"{tool_helper_service.ui_base_url}/gov/metadata-imports/$mdi_id?project_id=$project_id"
    )
    return template.substitute(mdi_id=mdi_id, project_id=project_id)


@auto_context
@service_registry.tool(
    name="create_metadata_import",
    description="Create a metadata import (MDI) in a project. PREREQUISITE: Must call list_connection_paths FIRST if schemas are not explicitly provided by user.",
    tags={"creat_metadata_import", "metadata_import"},
    meta={"version": "1.0", "service": "metadata_import"},
)
async def create_metadata_import(input: CreateMetadataImportRequest) -> CreateMetadataImportResponse:
    """
    Create a metadata import after determining the desired scope of schemas/tables to import.
    Returns:
         str: A descriptive confirmation message with the draft metadata import details,
             including project, connection, scope, and the draft MDI URL
    """

    LOGGER.info(
        "Calling tool 'create_metadata_import' to create a new metadata import - projectName=%s, connectionName=%s, scope=%s",
        input.project_name,
        input.connection_name,
        input.scope,
    )

    # Normalize scope which may be provided as a JSON string, list, or MetadataImportScope object
    if isinstance(input.scope, MetadataImportScope):
        scope = input.scope.paths
    elif isinstance(input.scope, list):
        scope = input.scope
    else:
        try:
            parsed = json.loads(str(input.scope))
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                scope = parsed
            else:
                scope = None
        except Exception:
            scope = None
    
    if scope is None or len(scope) == 0:
        scope = ["/"]

    project_id = await find_project_id(input.project_name)
    connection_id = await find_connection_id(input.connection_name, project_id)

    # Construct the payload for the service call
    import_name = input.name if input.name else f"{input.project_name}_{input.connection_name}_import_{uuid.uuid4().hex[:2]}"
    
    metadata_import_request = MetadataImportRequest(
        name=import_name,
        description=f"Import from {input.connection_name} into {input.project_name}",
        import_type="metadata",
        connection_id=connection_id,
        target_project_id=project_id,
        scope=MetadataImportScope(paths=scope)
    )

    LOGGER.info("Final payload: %s", metadata_import_request.model_dump())
    
    response = await tool_helper_service.execute_post_request(
        url=get_metadata_import_service_url(),
        json=metadata_import_request.model_dump(),
        params={
            "project_id": project_id,
            "job_name": metadata_import_request.name + "_job",
            "create_job": True,
        },
        tool_name="create_metadata_import",
    )

    mdi = MetadataImport(**response)
    mdi_url = get_metadata_import_resource_uri(
        mdi_id=mdi.metadata.asset_id, project_id=mdi.metadata.project_id
    )

    scope_str = '", "'.join(scope)
    message = (
        f'The metadata import has been created in your project {input.project_name} '
        f'with connection {input.connection_name}. The scope of the import is "{scope_str}". '
        f'The URL of the metadata import is [{mdi_url}]({mdi_url}). '
        f'Please review the draft metadata-import at the link above. You may edit the scope, advanced options, or import options'
    )

    LOGGER.info("Returning user-friendly message: %s", message)
    return CreateMetadataImportResponse(message=message)


@service_registry.tool(
    name="create_metadata_import",
    description="Create a metadata import (MDI) in a project. PREREQUISITE: Must call list_connection_paths FIRST if schemas are not explicitly provided by user.",
    tags={"metadata-import", "wxo"},
    meta={"version": "1.0", "service": "metadata-import"},
)
@auto_context
async def wxo_create_metadata_import(
    project_name: str,
    connection_name: str,
    scope: Union[List[str], str],
    name: Optional[str] = None
) -> CreateMetadataImportResponse:
    """Watsonx Orchestrator compatible version that expands CreateMetadataImportRequest object into individual parameters."""
    request = CreateMetadataImportRequest(
        project_name=project_name,
        connection_name=connection_name,
        scope=scope,
        name=name
    )
    
    # Call the original create_metadata_import function
    return await create_metadata_import(request)

