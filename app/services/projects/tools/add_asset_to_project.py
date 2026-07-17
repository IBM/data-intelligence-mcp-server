# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated, Optional, Dict, Any
from app.core.auth import get_bss_account_id, get_iam_url, get_user_identifier
from app.core.registry import service_registry
from app.services.projects.models.add_asset_to_project import (
    AddAssetToProjectRequest,
    AddAssetToProjectResponse,
)
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError, ExternalAPIError
from app.services.constants import CAMS_ASSETS_BASE_ENDPOINT, PROJECTS_BASE_ENDPOINT, CATALOGS_BASE_ENDPOINT, GROUPS_BASE_ENDPOINT, ASSET_TYPE_BASE_ENDPOINT
from app.services.tool_utils import (
    find_project_id,
    find_catalog_id,
    is_project_exist,
)
from app.shared.utils.helpers import append_context_to_url, is_uuid_bool, get_closest_match


UNEXPECTED_RESPONSE_FORMAT_ERROR = "Unexpected response format from API"


async def _add_asset_to_project(request: AddAssetToProjectRequest) -> AddAssetToProjectResponse:
    """
    Add a catalog asset to a project by creating a reference.

    This function:
    1. Validates the project exists and user has access
    2. Resolves asset name to ID if needed
    3. Validates the asset exists in a catalog
    4. Checks user has admin or editor role on the project
    5. Creates an asset reference in the project pointing to the catalog asset

    Args:
        request: AddAssetToProjectRequest containing asset_id_or_name, project_id_or_name, and optional catalog_id_or_name

    Returns:
        AddAssetToProjectResponse with details of the added asset

    Raises:
        ServiceError: If validation fails or user lacks permissions
        ExternalAPIError: If API calls fail
    """
    
    # Step 1: Resolve project ID - this will raise ServiceError if project doesn't exist
    LOGGER.info("Resolving project ID and validating user permissions")

    project_id, project_name, user_role = await _resolve_and_validate_project(request.project_id_or_name)

    # Step 2: Validate user permissions.
    # If the role is known (admin/editor/viewer), enforce it explicitly.
    # If the role is None the user may have access via an IAM group; let the
    # downstream API call act as the authoritative permission check.
    if user_role is not None:
        _validate_user_permissions(user_role, project_name)
        LOGGER.info(f"User has '{user_role}' role - proceeding with asset addition")
    else:
        # Role is None - could be group access or other indirect access
        # Let the API call validate permissions
        LOGGER.info(f"Could not determine direct user role for project '{project_name}'. "
                   f"Proceeding with API call - backend will validate permissions.")
    
    # Step 3: Resolve asset ID if name was provided
    asset_id = await _resolve_asset_id(
        request.asset_id_or_name,
        request.catalog_id_or_name
    )
    
    # Step 4: Get asset details from catalog
    asset_details = await _get_asset_details(
        asset_id,
        request.catalog_id_or_name
    )
    
    # Step 5: Check if asset already exists in project
    await _check_asset_not_in_project(project_id, asset_details["asset_name"])
    
    # Step 6: Copy the catalog asset into the project
    project_asset_id = await _create_asset_reference_in_project(
        asset_id=asset_id,
        project_id=project_id,
        catalog_id=asset_details["catalog_id"],
        asset_name=asset_details["asset_name"],
    )

    # Step 7: Build response using the project-scoped asset ID from bulk_copy
    asset_url = _build_asset_url(project_id, project_asset_id)

    LOGGER.info(
        f"Successfully added asset '{asset_details['asset_name']}' (catalog ID: {asset_id}, "
        f"project ID: {project_asset_id}) from catalog '{asset_details['catalog_name']}' "
        f"to project '{project_name}' (ID: {project_id})"
    )

    return AddAssetToProjectResponse(
        asset_id=project_asset_id,
        asset_name=asset_details["asset_name"],
        project_id=project_id,
        project_name=project_name,
        catalog_id=asset_details["catalog_id"],
        catalog_name=asset_details["catalog_name"],
        asset_url=asset_url,
        message=f"Asset '{asset_details['asset_name']}' successfully added to project '{project_name}'"
    )


async def _resolve_and_validate_project(project_id_or_name: str) -> tuple[str, str, str]:
    """
    Resolve project identifier to ID and validate user access.
    
    Returns:
        tuple: (project_id, project_name, user_role)
    """
    known_name: Optional[str] = None

    # Check if input is UUID or name
    if is_uuid_bool(project_id_or_name):
        project_id = project_id_or_name
        # Validate project exists and get details
        exists, _, actual_id = await is_project_exist(project_id)
        if not exists:
            raise ServiceError(f"Project with ID '{project_id}' not found or you don't have access to it",
                               remediation_steps="Call the list_containers tool with container_type set to 'project' to retrieve the list of available projects. Then provide a project ID from the list.",
                               tool="add_asset_to_project")
        project_id = actual_id
    else:
        # Resolve name to ID; the input is the authoritative project name.
        known_name = project_id_or_name
        project_id = await find_project_id(project_id_or_name)
    
    # Get project details including user role
    project_details = await _get_project_details(project_id, known_name=known_name)
    
    return project_id, project_details["name"], project_details["user_role"]


async def _get_project_details(project_id: str, known_name: Optional[str] = None) -> Dict[str, Any]:
    """Get project details including user's role.
    
    Args:
        project_id: The UUID of the project.
        known_name: If already known (e.g. the caller resolved it from the project list),
                    skip the extra GET call and use this value directly.
    """
    try:
        if known_name:
            project_name = known_name
        else:
            # Fetch name from the single-project endpoint
            project_response = await tool_helper_service.execute_get_request(
                url=f"{tool_helper_service.base_url}{PROJECTS_BASE_ENDPOINT}/{project_id}",
                tool_name="add_asset_to_project"
            )
            
            # Type assertion for response
            if isinstance(project_response, bytes):
                raise ServiceError(UNEXPECTED_RESPONSE_FORMAT_ERROR, tool="add_asset_to_project")
            
            project_name = project_response.get("entity", {}).get("name", "")
        
        # Get current user's identifier (IAM ID or UID)
        current_user_id = await get_user_identifier()
        
        LOGGER.info("=== Checking Project Access ===")
        LOGGER.info("Project: %s (ID: %s)", project_name, project_id)
        LOGGER.info("Current User ID: %s", current_user_id)
        
        # Check if user is admin or editor using the same approach as enable_container_for_text_to_sql
        user_role = await _check_user_role_in_project(project_id, current_user_id)
        
        LOGGER.info("=== Final user_role: %s ===", user_role)
        
        return {
            "name": project_name,
            "user_role": user_role
        }
    except Exception as e:
        LOGGER.error(f"Failed to get project details: {str(e)}")
        raise ServiceError(f"Failed to retrieve project details: {str(e)}", tool="add_asset_to_project")


async def _check_user_role_in_project(project_id: str, current_user_id: str) -> Optional[str]:
    """
    Check user's role in project using the same approach as enable_container_for_text_to_sql.
    Checks for admin first, then editor, then viewer, and also handles group memberships.
    
    Returns:
        Optional[str]: The user's role ("admin", "editor", "viewer", or None if not found)
    """
    # Check admin role
    if await _has_role_in_project(project_id, current_user_id, "admin"):
        return "admin"
    
    # Check editor role
    if await _has_role_in_project(project_id, current_user_id, "editor"):
        return "editor"
    
    # Check viewer role
    if await _has_role_in_project(project_id, current_user_id, "viewer"):
        return "viewer"
    
    return None


async def _has_role_in_project(project_id: str, current_user_id: str, role: str) -> bool:
    """
    Check if user has a specific role in the project (directly or through groups).
    Uses the same logic as enable_container_for_text_to_sql.
    """
    # Query members with specific role filter
    params = {"roles": role}
    
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{PROJECTS_BASE_ENDPOINT}/{project_id}/members",
            params=params,
            tool_name="add_asset_to_project"
        )
        
        if isinstance(response, bytes):
            return False
        
        members = response.get("members", [])
        LOGGER.info(f"Found {len(members)} members with role '{role}'")
        
        # Check if user is directly a member with this role
        for member in members:
            member_id = member.get("id", "")
            member_state = member.get("state", "")
            if member_id == current_user_id and member_state == "active":
                LOGGER.info(f"✓ User has direct '{role}' role")
                return True
        
        # Check if user has this role through group membership
        group_members = [
            member.get("id", "")
            for member in members
            if member.get("type", "") == "group"
        ]
        
        if not group_members:
            LOGGER.info(f"No group members with '{role}' role")
            return False
        
        LOGGER.info(f"Found {len(group_members)} group(s) with '{role}' role, checking user's group memberships")
        
        # Get user's group memberships
        groups_response = await tool_helper_service.execute_get_request(
            url=f"{get_iam_url()}{GROUPS_BASE_ENDPOINT}",
            params={"account_id": await get_bss_account_id(), "limit": 100},
            tool_name="add_asset_to_project"
        )
        
        if isinstance(groups_response, bytes):
            return False
        
        user_groups = [
            user_group.get("id", "") for user_group in groups_response.get("groups", [])
        ]
        
        # Check if any of user's groups have this role in the project
        has_role_via_group = any(group_id in group_members for group_id in user_groups)
        if has_role_via_group:
            LOGGER.info(f"✓ User has '{role}' role through group membership")
        
        return has_role_via_group
        
    except Exception as e:
        LOGGER.error(f"Error checking '{role}' role: {str(e)}")
        return False



async def _list_all_catalog_ids() -> list[str]:
    """Return the IDs of all accessible catalogs."""
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{CATALOGS_BASE_ENDPOINT}",
            tool_name="add_asset_to_project",
        )
        if isinstance(response, bytes):
            return []
        return [
            c.get("metadata", {}).get("guid")
            for c in response.get("catalogs", [])
            if c.get("metadata", {}).get("guid")
        ]
    except Exception:
        return []



async def _search_asset_in_catalog(asset_id_or_name: str, catalog_id: str) -> Optional[str]:
    """Search for an asset by name in a single catalog and return its ID, or None."""
    search_response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}{ASSET_TYPE_BASE_ENDPOINT}/asset/search",
        params={"catalog_id": catalog_id},
        json={"query": f"asset.name:{asset_id_or_name}"},
    )

    if isinstance(search_response, bytes):
        return None

    results = search_response.get("results", [])

    # Prefer exact (case-insensitive) match first
    asset_id = next(
        (r["metadata"]["asset_id"] for r in results
         if r.get("metadata", {}).get("name", "").lower() == asset_id_or_name.lower()),
        None,
    )

    # Fall back to fuzzy match among the name-filtered results
    if not asset_id and results:
        asset_list = [
            {"name": r["metadata"]["name"], "id": r["metadata"]["asset_id"]}
            for r in results
        ]
        asset_id = get_closest_match(asset_list, asset_id_or_name)

    return asset_id


async def _resolve_asset_id(asset_id_or_name: str, catalog_id_or_name: Optional[str]) -> str:
    """
    Resolve asset identifier to ID.

    If the input is a valid UUID, return it as-is.
    If it's a name, resolve it to an ID using the catalog.

    Args:
        asset_id_or_name: Asset ID (UUID) or name
        catalog_id_or_name: Optional catalog ID or name to search in

    Returns:
        str: Asset ID (UUID)

    Raises:
        ServiceError: If asset name cannot be resolved to ID
    """
    if is_uuid_bool(asset_id_or_name):
        return asset_id_or_name

    # Resolve the list of catalogs to search
    if catalog_id_or_name:
        resolved_id = catalog_id_or_name if is_uuid_bool(catalog_id_or_name) else await find_catalog_id(catalog_id_or_name)
        catalog_ids = [resolved_id]
    else:
        catalog_ids = await _list_all_catalog_ids()

    # Search each candidate catalog for the asset name
    for catalog_id in catalog_ids:
        try:
            asset_id = await _search_asset_in_catalog(asset_id_or_name, catalog_id)
        except ServiceError:
            raise
        except Exception:
            continue

        if asset_id:
            LOGGER.info(
                f"Resolved asset name '{asset_id_or_name}' to ID '{asset_id}' "
                f"in catalog '{catalog_id}'"
            )
            return asset_id

    raise ServiceError(
        f"Failed to resolve asset name '{asset_id_or_name}' in catalog. "
        f"Please verify the asset name and catalog.",
        remediation_steps="Call the search_asset tool with search_prompt set to '*' and container_type set to 'catalog' to retrieve the available assets, then provide a valid asset name from the results.",
        tool="add_asset_to_project"
    )


def _validate_user_permissions(user_role: str, project_name: str):
    """
    Validate user has admin or editor permissions.
    
    Note: This function should only be called when user_role is not None.
    If user_role is None, the caller should skip validation and let the API validate.
    """
    LOGGER.info("=== _validate_user_permissions called ===")
    LOGGER.info("Received user_role: %s (type: %s)", user_role, type(user_role).__name__)
    LOGGER.info("Project name: %s", project_name)
    
    allowed_roles = ["admin", "editor"]
    if user_role.lower() not in allowed_roles:
        raise ServiceError(
            f"Insufficient permissions. You need 'admin' or 'editor' role on project '{project_name}' "
            f"to add assets. Your current role: '{user_role}'",
            tool="add_asset_to_project"
        )


async def _get_asset_details(asset_id: str, catalog_id_or_name: Optional[str]) -> Dict[str, Any]:
    """
    Get asset details from catalog.
    
    Returns:
        dict with keys: asset_name, asset_type, catalog_id, catalog_name
    """
    # If catalog specified, use it directly
    if catalog_id_or_name:
        if is_uuid_bool(catalog_id_or_name):
            catalog_id = catalog_id_or_name
        else:
            catalog_id = await find_catalog_id(catalog_id_or_name)
    else:
        # Search for asset across all accessible catalogs
        catalog_id = await _find_catalog_containing_asset(asset_id)
    
    # Get asset details
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/{asset_id}",
            params={"catalog_id": catalog_id},
            tool_name="add_asset_to_project"
        )
        
        # Type assertion for response
        if isinstance(response, bytes):
            raise ServiceError(UNEXPECTED_RESPONSE_FORMAT_ERROR, tool="add_asset_to_project")
        
        metadata = response.get("metadata", {})
        asset_name = metadata.get("name", "")
        asset_type = metadata.get("asset_type", "")
        
        if not asset_name:
            raise ServiceError(f"Asset with ID '{asset_id}' not found in catalog", tool="add_asset_to_project")
        
        if not asset_type:
            raise ServiceError(f"Asset with ID '{asset_id}' is missing asset_type in metadata", tool="add_asset_to_project")
        
        # Get catalog name
        catalog_details = await _get_catalog_details(catalog_id)
        
        return {
            "asset_name": asset_name,
            "asset_type": asset_type,
            "catalog_id": catalog_id,
            "catalog_name": catalog_details["name"]
        }
    except ExternalAPIError as e:
        if "404" in str(e):
            raise ServiceError(
                f"Asset with ID '{asset_id}' not found in the specified catalog. "
                "Please verify the asset ID and catalog.",
                remediation_steps="Call the search_asset tool with search_prompt set to '*' and container_type set to 'catalog' to retrieve the available assets, then provide a valid asset id from the results.",
                tool="add_asset_to_project"
            )
        raise


async def _find_catalog_containing_asset(asset_id: str) -> str:
    """Find which catalog contains the given asset."""
    # Get list of accessible catalogs
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{CATALOGS_BASE_ENDPOINT}",
            tool_name="add_asset_to_project"
        )
        
        # Type assertion for response
        if isinstance(response, bytes):
            raise ServiceError(UNEXPECTED_RESPONSE_FORMAT_ERROR, tool="add_asset_to_project")
        
        catalogs = response.get("catalogs", [])
        
        # Try to find asset in each catalog
        for catalog in catalogs:
            catalog_id = catalog.get("metadata", {}).get("guid")
            if not catalog_id:
                continue
            
            try:
                # Try to get asset from this catalog
                await tool_helper_service.execute_get_request(
                    url=f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/{asset_id}",
                    params={"catalog_id": catalog_id},
                    tool_name="add_asset_to_project"
                )
                # If successful, asset is in this catalog
                return catalog_id
            except Exception:
                # Asset not in this catalog, continue searching
                continue
        
        raise ServiceError(
            f"Asset with ID '{asset_id}' not found in any accessible catalog. "
            "Please specify the catalog containing this asset.",
            remediation_steps="Call the search_asset tool with search_prompt set to '*' and container_type set to 'catalog' to retrieve the available assets, then provide a valid asset id from the results.",
            tool="add_asset_to_project"
        )
    except ServiceError:
        raise
    except Exception as e:
        raise ServiceError(f"Failed to search for asset across catalogs: {str(e)}", tool="add_asset_to_project")


async def _get_catalog_details(catalog_id: str) -> Dict[str, Any]:
    """Get catalog details."""
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{CATALOGS_BASE_ENDPOINT}/{catalog_id}",
            tool_name="add_asset_to_project"
        )
        
        # Type assertion for response
        if isinstance(response, bytes):
            return {"name": "Unknown"}
        
        return {
            "name": response.get("entity", {}).get("name", "")
        }
    except Exception as e:
        LOGGER.error(f"Failed to get catalog details: {str(e)}")
        return {"name": "Unknown"}


async def _check_asset_not_in_project(project_id: str, asset_name: str):
    """
    Check if an asset with the given name already exists in the project.

    The asset name is resolved before this call (from the catalog copy) and passed
    directly, avoiding a bare GET /v2/assets/{id} that could resolve to the wrong
    container or fail silently after the first add.
    Uses the asset search endpoint (POST /v2/asset_types/asset/search) which is the
    reliable way to query assets within a container.
    """
    try:
        if not asset_name:
            LOGGER.warning("Asset name not provided for duplicate check - proceeding")
            return

        # Search for assets with the same name in the project using the search endpoint,
        # which is the correct CAMS API pattern for querying assets within a container.
        search_response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}{ASSET_TYPE_BASE_ENDPOINT}/asset/search",
            params={"project_id": project_id},
            json={"query": f"asset.name:{asset_name}"},
            tool_name="add_asset_to_project"
        )

        if isinstance(search_response, bytes):
            LOGGER.warning("Could not search project assets - proceeding")
            return

        # Check if any assets were found with this exact name
        results = search_response.get("results", [])
        match = next(
            (r for r in results if r.get("metadata", {}).get("name", "").lower() == asset_name.lower()),
            None,
        )
        if match:
            # Asset with same name already exists in project
            raise ServiceError(
                f"Asset with name '{asset_name}' already exists in this project. "
                "No need to add it again.", tool="add_asset_to_project"
            )

        LOGGER.info(f"Asset '{asset_name}' not in project yet - proceeding with add")
        return

    except ServiceError:
        # Re-raise ServiceError (duplicate found)
        raise
    except ExternalAPIError as e:
        # If we can't check, log warning and proceed
        LOGGER.warning(f"Could not verify if asset exists in project: {str(e)} - proceeding")
        return
    except Exception as e:
        # Handle any other exceptions
        LOGGER.warning(f"Error checking if asset exists in project: {str(e)} - proceeding")
        return


async def _create_asset_reference_in_project(
    asset_id: str,
    project_id: str,
    catalog_id: str,
    asset_name: str,
) -> str:
    """
    Copy a catalog asset into a project using the bulk_copy API.

    Uses POST /v2/assets/bulk_copy, which is the correct CAMS endpoint for
    bringing an existing catalog asset into a project.  This produces a fully
    backed project asset that the UI can open and preview.

    Returns:
        The project-scoped asset ID assigned by the platform to the copied asset.
    """
    payload = {
        "project_id": project_id,
        "copy_configurations": [{"asset_id": asset_id}],
    }

    try:
        response = await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}{CAMS_ASSETS_BASE_ENDPOINT}/bulk_copy",
            params={
                "catalog_id": catalog_id,
                "auto_copy_connections_in_remote_attachments": True,
            },
            json=payload,
            tool_name="add_asset_to_project"
        )

        # Extract the new project-scoped asset ID from the response
        responses = response.get("responses", []) if isinstance(response, dict) else []
        if responses:
            copied_assets = responses[0].get("copied_assets", [])
            if copied_assets:
                project_asset_id = copied_assets[0].get("target_asset_id", asset_id)
                LOGGER.info(
                    f"Copied catalog asset '{asset_name}' into project; "
                    f"project asset ID: {project_asset_id}"
                )
                return project_asset_id

        # Fallback: return the original catalog asset_id if the response shape
        # is unexpected (avoids a hard failure when the copy did succeed).
        LOGGER.warning(
            f"bulk_copy response missing target_asset_id for '{asset_name}'; "
            f"falling back to source asset ID"
        )
        return asset_id

    except Exception as e:
        LOGGER.error(f"Failed to create asset reference: {str(e)}")
        raise ServiceError(
            f"Failed to add asset to project. This may be due to insufficient permissions "
            f"or the asset type may not support project references. Error: {str(e)}",
            tool="add_asset_to_project"
        )


def _build_asset_url(project_id: str, asset_id: str) -> str:
    """Build URL to access asset in project UI."""
    if not tool_helper_service.ui_base_url:
        return ""
    
    # Build URL based on UI base URL
    base_url = f"{tool_helper_service.ui_base_url}/projects/{project_id}/assets/{asset_id}"
    
    # Add context if needed
    return append_context_to_url(base_url, "wx")


@service_registry.tool(
    name="add_asset_to_project",
    description="""Add a catalog asset to a project by creating a reference. This enables downstream work like SQL asset creation on the catalog asset within the project context. The tool validates that the caller has admin or editor access to the target project. The asset must exist in a catalog. You can provide either the asset ID (UUID) or asset name. When providing an asset name, you must also specify the catalog_id_or_name parameter.

Use this tool when you want to:
- Add an existing catalog asset into a project for downstream work
- Make a catalog asset available in a project context without duplicating the source asset
- Prepare a catalog asset for project-based operations such as SQL asset creation

**SQL View Workflow (primary use case)**
To create a SQL view on top of a catalog table, run these tools in order:
1. Call add_asset_to_project to bring the source table into your project.
2. Call create_asset_from_sql_query, pointing at the same project and the connection that backs the table, with your SELECT statement.

Example of adding an asset and then creating a SQL view:
  add_asset_to_project:
    asset_id_or_name: "sales_orders"
    project_id_or_name: "Analytics Project"
    catalog_id_or_name: "Enterprise Catalog"

  create_asset_from_sql_query:
    sql_query: "SELECT order_id, customer_id, total FROM sales_orders WHERE status = 'shipped'"
    container_id_or_name: "Analytics Project"
    container_type: "project"
    connection_id_or_name: "<connection that backs the table>"
    asset_name: "shipped_orders_view"

Returns:
    AddAssetToProjectResponse: Details of the added asset reference including the asset ID, asset name, target project ID and name, source catalog ID and name, project asset URL, and a success message.

Example request (by name):
    asset_id_or_name: "customer_data"
    project_id_or_name: "Analytics Project"
    catalog_id_or_name: "Enterprise Catalog"

Example request (by ID):
    asset_id_or_name: "550e8400-e29b-41d4-a716-446655440000"
    project_id_or_name: "550e8400-e29b-41d4-a716-446655440001"

Example response:
    asset_id: "550e8400-e29b-41d4-a716-446655440000"
    asset_name: "customer_data"
    project_id: "550e8400-e29b-41d4-a716-446655440001"
    project_name: "Analytics Project"
    catalog_id: "550e8400-e29b-41d4-a716-446655440002"
    catalog_name: "Enterprise Catalog"
    asset_url: "https://<host>/projects/<project_id>/assets/<asset_id>"
    message: "Asset 'customer_data' successfully added to project 'Analytics Project'"

Error cases:
    - Unauthorized: caller has viewer role → "Insufficient permissions. You need 'admin' or 'editor' role on project '<name>' to add assets."
    - Asset not found: asset ID/name does not exist in any accessible catalog → "Asset with ID '<id>' not found in the specified catalog."
    - Project not found: project ID/name does not exist → "Project with ID '<id>' not found or you don't have access to it."
    - Already added: asset with that name already exists in the project → "Asset with name '<name>' already exists in this project. No need to add it again."

Example use cases:
    - Add asset customer_data from Enterprise Catalog to Customer Analytics Project
    - Add asset 550e8400-e29b-41d4-a716-446655440000 to project My Analytics Project
    - Add sales_orders from mcpbvtcatalog to mcpbvtproject""",
    annotations={
        "title": "Add Catalog Asset to Project",
        "destructiveHint": True
    }
)
@auto_context
async def add_asset_to_project(
    asset_id_or_name: Annotated[
        str,
        "The ID (UUID) or name of the catalog asset to add to the project."
    ],
    project_id_or_name: Annotated[
        str,
        "The ID or name of the target project where the asset reference will be created."
    ],
    catalog_id_or_name: Annotated[
        Optional[str],
        "Optional ID or name of the catalog containing the asset. Required when asset_id_or_name is provided as a name."
    ] = None,
) -> AddAssetToProjectResponse:
    """
    Add a catalog asset to a project.
    """
    request = AddAssetToProjectRequest(
        asset_id_or_name=asset_id_or_name,
        project_id_or_name=project_id_or_name,
        catalog_id_or_name=catalog_id_or_name
    )
    
    return await _add_asset_to_project(request)

# Made with Bob
