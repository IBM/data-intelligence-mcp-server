# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Optional

from app.core.registry import service_registry
from app.services.metadata_enrichment.models.metadata_enrichment import MetadataImportResponse
from app.services.tool_utils import find_project_id, find_all_available_metadata_import
from app.shared.logging import auto_context, LOGGER
from app.shared.utils.helpers import confirm_uuid


@service_registry.tool(
    name="search_metadata_import",
    description="""Searches for the available metadata import .
    
    This function is mainly used when a user want to create or update a metadata enrichment (MDE) and does not provide an asset or want to use a metadata import (MDI).
    This function can search for all the available metadata imports (MDI) or search a metadata imports by name 
    - The user must provide a project name or the project ID
    - Optional: the user can provide the metadata import name to search a specific MDI
    
    This function supports wildcard search
    
    Return the result in a table in MD format.
    """,
)
@auto_context
async def search_metadata_import(
        project: str,
        metadata_import_name: Optional[str] = None,
) -> List[MetadataImportResponse]:
    LOGGER.info(
        f"search_medata_import called with project: {project}, "
        f"metadata_import_name: {metadata_import_name}"
    )

    project_id = await confirm_uuid(project, find_project_id)

    return await find_all_available_metadata_import(project_id, metadata_import_name)


@service_registry.tool(
    name="search_metadata_import",
    description="""Searches for the available metadata import .

    This function is mainly used when a user want to create or update a metadata enrichment (MDE) and does not provide an asset or want to use a metadata import (MDI).
    This function can search for all the available metadata imports (MDI) or search a metadata imports by name 
    - The user must provide a project name or the project ID
    - Optional: the user can provide the metadata import name to search a specific MDI

    This function supports wildcard search

    Return the result in a table in MD format.
    """,
)
@auto_context
async def wxo_search_metadata_import(
        project: str,
        metadata_import_name: Optional[str] = None,
) -> List[MetadataImportResponse]:
    return await search_metadata_import(project, metadata_import_name)