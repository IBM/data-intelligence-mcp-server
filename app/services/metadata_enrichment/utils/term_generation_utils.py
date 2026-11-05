# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
#
# Term Generation Utilities for MDE v3 API Support
# This module contains utilities specific to term generation with v3 MDE APIs

from typing import Optional, Dict, List, Any, Tuple  # noqa: I001, UP035 # Baseline

from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import is_uuid_bool
from app.shared.utils.tool_helper_service import tool_helper_service

# SQ: avoid duplicating string literals
BYTES_RESPONSE_ERROR_MSG = "Received bytes response instead of dict"
# Key name used by Global Search to surface the category UUID inside each row's entity.artifacts object
ARTIFACT_ID_KEY = "artifact_id"

# Source fields requested from Global Search for category queries
_GS_CATEGORY_SOURCE = [
    "artifact_id",
    "metadata.name",
    "metadata.description",
    "metadata.modified_by",
    "categories",
    "entity.artifacts.artifact_id",
]


async def _fetch_mde_v3_asset(mde_id: str, project_id: str) -> Optional[Dict[str, Any]]:  # noqa: UP006, UP045 # Baseline
    """
    Fetch raw v3 MDE asset response. Returns None when a bytes response is received.

    Callers should treat None as an invalid/unreadable response and handle accordingly.
    This helper eliminates the duplicated GET + bytes-check block shared by
    `is_mde_v3` and `get_mde_jobs`.
    """
    response = await tool_helper_service.execute_get_request(
        url=f"{tool_helper_service.base_url}/metadata_enrichment/v3/metadata_enrichment_assets/{mde_id}",
        params={"project_id": project_id},
    )
    if isinstance(response, bytes):
        LOGGER.error(BYTES_RESPONSE_ERROR_MSG)
        return None
    return response


def _build_category_search_payload(
    filter_field: str, filter_value: str
) -> Dict[str, Any]:  # noqa: UP006 # Baseline
    """
    Build a Global Search payload to find categories by a single filter term.

    Eliminates the duplicated payload structure used in `validate_category_exists`
    for the name-search and UUID-search calls (which differ only in `filter_field`).

    Args:
        filter_field: The ES field to filter on (e.g. ``"metadata.name.keyword"``
                      or ``"entity.artifacts.artifact_id"``).
        filter_value: The value to match against that field.
    """
    return {
        "size": 100,
        "from": 0,
        "_source": _GS_CATEGORY_SOURCE,
        "query": {
            "bool": {
                "filter": {
                    "bool": {
                        "must": [
                            {"term": {"metadata.artifact_type": "category"}},
                            {"term": {filter_field: filter_value}},
                        ]
                    }
                }
            }
        },
    }


async def is_mde_v3(mde_id: str, project_id: str) -> bool:
    """
    Detect if MDE is v3 by checking for 'version' field.

    Uses v3 API endpoint to get MDE details and checks for version field.

    Args:
        mde_id: MDE asset ID
        project_id: Project ID

    Returns:
        True if MDE is v3, False if legacy

    Raises:
        ServiceError: If the MDE API call fails for any reason other than 404.
    """
    try:
        response = await _fetch_mde_v3_asset(mde_id, project_id)
        if response is None:
            return False

        is_v3 = response.get("version") == "v3"
        LOGGER.info(
            f"MDE {mde_id} version: {'v3' if is_v3 else 'legacy (v2 or unversioned)'}"
        )
        return is_v3

    except ServiceError as e:
        # tool_helper_service converts HTTP 404 GET errors into ServiceError.
        # A 404 on the v3 endpoint means the MDE only exists on the legacy endpoint → treat as legacy.
        if "404" in str(e):
            LOGGER.info(
                f"MDE {mde_id} not found on v3 endpoint (404) — treating as legacy"
            )
            return False
        # Any other ServiceError (403, 500, etc.) is a real failure — propagate it.
        raise

    except ExternalAPIError as e:
        # Non-404 HTTP errors surface as ExternalAPIError — always a real failure.
        raise ServiceError(f"Failed to detect MDE version for {mde_id}: {e}") from e

    except Exception as e:
        raise ServiceError(f"Failed to detect MDE version for {mde_id}: {e}") from e


async def get_mde_jobs(mde_id: str, project_id: str) -> Dict[str, Dict[str, Any]]:  # noqa: UP006 # Baseline
    """
    Get all jobs for a v3 MDE.

    Jobs are stored in enrichment_jobs dict at root level of v3 MDE response.

    Args:
        mde_id: MDE asset ID
        project_id: Project ID

    Returns:
        Dictionary mapping job_id to job info {id, name, href}
    """
    try:
        response = await _fetch_mde_v3_asset(mde_id, project_id)
        if response is None:
            raise ServiceError(
                f"Failed to retrieve jobs for MDE {mde_id}: Invalid response format"
            )

        enrichment_jobs = response.get("enrichment_jobs", {})
        LOGGER.info(f"Found {len(enrichment_jobs)} jobs in MDE {mde_id}")
        return enrichment_jobs

    except Exception as e:
        LOGGER.error(f"Error getting MDE jobs: {e}")
        raise ServiceError(f"Failed to retrieve jobs for MDE {mde_id}: {e!s}")  # noqa: B904 # Baseline


async def get_job_details(mde_id: str, job_id: str, project_id: str) -> Dict[str, Any]:  # noqa: UP006 # Baseline
    """
    Get detailed configuration for a specific job.

    Uses v3 API endpoint to get job details including term_generation_target_category_id.

    Args:
        mde_id: MDE asset ID
        job_id: Job ID
        project_id: Project ID

    Returns:
        Job details including term_generation_target_category_id
    """
    try:
        # Get job details using v3 API
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}/metadata_enrichment/v3/metadata_enrichment_assets/{mde_id}/jobs/{job_id}",
            params={"project_id": project_id},
        )

        # Handle bytes response
        if isinstance(response, bytes):
            LOGGER.error(BYTES_RESPONSE_ERROR_MSG)
            raise ServiceError(
                f"Failed to retrieve details for job {job_id}: Invalid response format"
            )

        LOGGER.info(f"Retrieved details for job {job_id}")
        return response

    except Exception as e:
        LOGGER.error(f"Error getting job details: {e}")
        raise ServiceError(f"Failed to retrieve details for job {job_id}: {e!s}")  # noqa: B904 # Baseline


async def resolve_job_identifier(
    mde_id: str, project_id: str, job_name: str
) -> Optional[str]:  # noqa: UP045 # Baseline
    """
    Resolve job name to job UUID.

    Args:
        mde_id: MDE asset ID
        project_id: Project ID
        job_name: Job name to resolve

    Returns:
        Job UUID or None if not found
    """
    jobs_map = await get_mde_jobs(mde_id, project_id)

    # Search for job by name (case-insensitive)
    for job_id, job_info in jobs_map.items():
        if job_info.get("name", "").lower() == job_name.lower():
            LOGGER.info(f"Resolved job name '{job_name}' to ID: {job_id}")
            return job_id

    LOGGER.warning(f"Job '{job_name}' not found in MDE {mde_id}")
    return None


async def validate_category_exists(  # noqa: PLR0911 # Baseline
    category_identifier: str,
) -> Tuple[bool, Optional[str], Optional[str], Optional[List[Dict[str, Any]]]]:  # noqa: UP006, UP045 # Baseline
    """
    Validate that a category exists using global search.

    Tries to find category by name first, then by ID if name search fails.
    Detects duplicate category names and returns all matches with parent hierarchy.
    Uses correct global search payload format as per API examples.

    Args:
        category_identifier: Category name or UUID

    Returns:
        Tuple of (exists, category_id, category_name, duplicates)
        - If unique: (True, id, name, None)
        - If duplicates: (False, None, None, [list of dicts with parent_path])
        - If not found: (False, None, None, None)

    Example duplicate dict:
        {
            "category_id": "abc-123",
            "category_name": "subcat_3",
            "parent_path": "Finance >> Risk Management >> subcat_3"
        }
    """
    try:
        _gs_params = {"tenant_scope": "true", "auth_scope": "category"}
        _gs_url = f"{tool_helper_service.base_url}/v3/search"

        # Search by name first
        search_response = await tool_helper_service.execute_post_request(
            url=_gs_url,
            params=_gs_params,
            json=_build_category_search_payload(
                "metadata.name.keyword", category_identifier
            ),
        )

        if isinstance(search_response, bytes):
            LOGGER.error(BYTES_RESPONSE_ERROR_MSG)
            return False, None, None, None

        rows = search_response.get("rows", [])

        if rows:
            if len(rows) > 1:
                # Multiple categories with same name — return all with parent hierarchy
                duplicates = []
                for row in rows:
                    category_id = (
                        row.get("entity", {}).get("artifacts", {}).get(ARTIFACT_ID_KEY)
                    )
                    category_name = row.get("metadata", {}).get("name")
                    primary_category_name = row.get("categories", {}).get(
                        "primary_category_name", ""
                    )
                    if primary_category_name:
                        parent_path = f"{primary_category_name} >> {category_name}"
                    else:
                        parent_path = f"[Top Level] >> {category_name}"
                    duplicates.append(
                        {
                            "category_id": category_id,
                            "category_name": category_name,
                            "parent_path": parent_path,
                        }
                    )
                LOGGER.warning(
                    f"Found {len(rows)} categories with name '{category_identifier}'. "
                    f"User selection required."
                )
                return False, None, None, duplicates

            # Unique category found
            category = rows[0]
            category_id = (
                category.get("entity", {}).get("artifacts", {}).get(ARTIFACT_ID_KEY)
            )
            category_name = category.get("metadata", {}).get("name")
            LOGGER.info(
                f"Category '{category_identifier}' found by name: {category_id}"
            )
            return True, category_id, category_name, None

        # Fall back: search by UUID (artifact_id field)
        search_response_by_id = await tool_helper_service.execute_post_request(
            url=_gs_url,
            params=_gs_params,
            json=_build_category_search_payload(
                "entity.artifacts.artifact_id", category_identifier
            ),
        )

        if isinstance(search_response_by_id, bytes):
            LOGGER.error(BYTES_RESPONSE_ERROR_MSG)
            return False, None, None, None

        rows_by_id = search_response_by_id.get("rows", [])

        if rows_by_id:
            category = rows_by_id[0]
            category_id = (
                category.get("entity", {}).get("artifacts", {}).get(ARTIFACT_ID_KEY)
            )
            category_name = category.get("metadata", {}).get("name")
            LOGGER.info(f"Category UUID '{category_identifier}' found: {category_name}")
            return True, category_id, category_name, None

        LOGGER.warning(f"Category '{category_identifier}' not found")
        return False, None, None, None

    except Exception as e:
        LOGGER.error(f"Error validating category: {e}")
        return False, None, None, None


async def get_category_by_id_direct(
    category_id: str,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:  # noqa: UP006, UP045 # Baseline
    """
    Get category details using direct API (5-10x faster than Global Search).

    Use this function when you have a category ID/UUID and need to:
    - Validate the category exists
    - Get the category name
    - Get full category details

    This is significantly faster than Global Search for ID-based lookups:
    - Direct API: ~50-150ms
    - Global Search: ~500-1000ms

    Use Global Search (validate_category_exists) when:
    - User provides a category NAME (not ID)
    - Need to search for categories by name

    Args:
        category_id: Category UUID

    Returns:
        Tuple of (exists, category_name, category_details)
        - exists: True if category found, False otherwise
        - category_name: Category name from metadata.name field
        - category_details: Full category response dict (metadata + entity)

    Example:
        # Validate category ID from job config
        exists, name, details = await get_category_by_id_direct("abc-123")
        if exists:
            print(f"Category: {name}")
        else:
            raise ServiceError("Category not found")
    """
    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}/v3/categories/{category_id}"
        )

        # Handle bytes response
        if isinstance(response, bytes):
            LOGGER.error(BYTES_RESPONSE_ERROR_MSG)
            return False, None, None

        # Extract name from metadata.name field (per API spec)
        category_name = response.get("metadata", {}).get("name")

        if not category_name:
            LOGGER.warning(f"Category {category_id} has no name in metadata")
            return False, None, None

        LOGGER.info(f"Category '{category_id}' found: {category_name}")
        return True, category_name, response

    except Exception as e:
        error_msg = str(e)
        # 404 means category doesn't exist (expected for validation)
        if "404" in error_msg:
            LOGGER.info(f"Category '{category_id}' not found (404)")
            return False, None, None
        # Other errors are unexpected
        LOGGER.error(f"Error getting category by ID: {e}")
        return False, None, None


async def get_category_name_by_id(category_id: str) -> Optional[str]:  # noqa: UP045 # Baseline
    """
    Get category name from category ID using global search.

    DEPRECATED: Use get_category_by_id_direct() for better performance (5-10x faster).
    This function is kept for backward compatibility.

    Args:
        category_id: Category UUID

    Returns:
        Category name or None if not found
    """
    exists, _, category_name, _ = await validate_category_exists(category_id)
    return category_name if exists else None


async def get_category_id_by_name(category_name: str) -> Optional[str]:  # noqa: UP045 # Baseline
    """
    Get category ID from category name using global search.

    Args:
        category_name: Category name

    Returns:
        Category UUID or None if not found
    """
    exists, category_id, _, _ = await validate_category_exists(category_name)
    return category_id if exists else None


async def get_jobs_with_target_categories(
    mde_id: str, project_id: str
) -> List[Dict[str, Any]]:  # noqa: UP006 # Baseline
    """
    Get all jobs that have term_generation_target_category_id configured.

    PERFORMANCE OPTIMIZATION: Uses fast direct API (GET /v3/categories/{id}) instead
    of slow Global Search for category validation. This provides:
    - 5-10x faster response time (50-150ms vs 500-1000ms per category)
    - Category name for user-friendly display
    - Validation that category exists

    Retrieves job details for each job, extracts target category ID, and validates
    category using the fast direct API to get category name.

    Args:
        mde_id: MDE asset ID
        project_id: Project ID

    Returns:
        List of dicts with job_id, job_name, target_category_id, target_category_name
    """
    jobs_map = await get_mde_jobs(mde_id, project_id)
    jobs_with_categories = []

    for job_id, job_info in jobs_map.items():
        try:
            job_details = await get_job_details(mde_id, job_id, project_id)

            # Extract target category ID from nested structure
            # Path: delegate_configuration.enrichment_objective.term_assignment.term_generation_target_category_id
            target_category_id = (
                job_details.get("delegate_configuration", {})
                .get("enrichment_objective", {})
                .get("term_assignment", {})
                .get("term_generation_target_category_id")
            )

            if target_category_id:
                # Use fast direct API instead of Global Search for category name lookup.
                # Always include the job — even if the category no longer exists — so
                # the user can see it and decide what to do.  A deleted/stale category
                # should not silently hide the job from the selection list.
                exists, category_name, _ = await get_category_by_id_direct(
                    target_category_id
                )

                if exists and category_name:
                    display_name = category_name
                    LOGGER.info(
                        f"Job '{job_info.get('name')}' has target category: "
                        f"{category_name} ({target_category_id})"
                    )
                else:
                    # Category not found — surface the ID so the user is aware
                    display_name = target_category_id
                    LOGGER.warning(
                        f"Job '{job_info.get('name')}' references category "
                        f"'{target_category_id}' which was not found — including job anyway"
                    )

                jobs_with_categories.append(
                    {
                        "job_id": job_id,
                        "job_name": job_info.get("name", job_id),
                        "target_category_id": target_category_id,
                        "target_category_name": display_name,
                    }
                )
        except Exception as e:
            LOGGER.warning(f"Failed to get details for job {job_id}: {e}")
            continue

    return jobs_with_categories


async def extract_and_validate_legacy_mde_category(
    project_id: str, metadata_enrichment_id: str
) -> Tuple[Optional[str], Optional[str]]:  # noqa: UP006, UP045 # Baseline
    """
    Extract and validate target category from legacy MDE asset.

    Legacy MDEs store the target category at:
    entity.metadata_enrichment_area.objective.term_assignment.term_generation_target_category_id

    This function:
    1. Extracts category ID from MDE asset
    2. Validates category exists using fast direct API (GET /v3/categories/{id})
    3. Returns both category ID and name

    Args:
        project_id: Project ID
        metadata_enrichment_id: MDE asset ID

    Returns:
        Tuple of (category_id, category_name) if found and valid, (None, None) otherwise

    Raises:
        ServiceError: If category is configured but doesn't exist in glossary
    """
    try:
        # Step 1: Extract category ID from MDE asset
        mde_response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}/v2/assets/{metadata_enrichment_id}",
            params={"project_id": project_id},
        )

        # Handle bytes response
        if isinstance(mde_response, bytes):
            LOGGER.error("Received bytes response when fetching MDE asset")
            return None, None

        # Extract category from nested structure
        category_id = (
            mde_response.get("entity", {})
            .get("metadata_enrichment_area", {})
            .get("objective", {})
            .get("term_assignment", {})
            .get("term_generation_target_category_id")
        )

        if not category_id:
            LOGGER.info("No target category configured in legacy MDE")
            return None, None

        LOGGER.info(f"Found target category in legacy MDE: {category_id}")

        # Step 2: Validate category exists using fast direct API
        exists, category_name, _ = await get_category_by_id_direct(category_id)

        if not exists:
            raise ServiceError(
                f"Target category '{category_id}' is configured in the MDE but does not exist in the glossary. "
                f"Please update the MDE configuration with a valid category or create the category in the glossary first."
            )

        LOGGER.info(f"Validated target category: {category_name} ({category_id})")
        return category_id, category_name

    except ServiceError:
        # Re-raise ServiceError (category validation failure)
        raise
    except Exception as e:
        LOGGER.warning(
            f"Failed to extract/validate target category from legacy MDE: {e}"
        )
        return None, None


async def execute_term_generation_legacy(
    project_id: str,
    metadata_enrichment_id: str,
    data_asset_ids: List[str],  # noqa: UP006 # Baseline
) -> Tuple[Any, int, Optional[str], Optional[str]]:  # noqa: UP006, UP045 # Baseline
    """
    Execute term generation using legacy API with optional category targeting.

    This function encapsulates the legacy term generation flow:
    1. Extract and validate target category from MDE asset (if configured)
    2. Count draft terms before
    3. Run term generation on all data assets with category
    4. Count draft terms after
    5. Calculate delta

    Args:
        project_id: Project ID
        metadata_enrichment_id: MDE asset ID
        data_asset_ids: List of data asset IDs to process

    Returns:
        Tuple of (term_generation_responses, count_of_draft_terms_from_term_generation, category_id, category_name)

    Raises:
        ServiceError: If target category is configured but doesn't exist
    """
    from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (  # noqa: I001 # Baseline
        get_workflow_ids_from_project_id,
        get_draft_terms_from_workflow_ids,
        call_term_generation_on_metadata_enrichment_asset,
    )

    LOGGER.info("Executing legacy term generation flow")

    # Step 1: Extract and validate target category from legacy MDE asset
    # This uses fast direct API for validation (5-10x faster than Global Search)
    category_id, category_name = await extract_and_validate_legacy_mde_category(
        project_id, metadata_enrichment_id
    )

    if category_id and category_name:
        LOGGER.info(f"Using target category from MDE: {category_name} ({category_id})")
    else:
        LOGGER.info("No target category configured in legacy MDE")

    # Count draft terms before
    workflow_ids_before = await get_workflow_ids_from_project_id(project_id)
    draft_terms_before = await get_draft_terms_from_workflow_ids(workflow_ids_before)
    LOGGER.info(f"Draft terms before term generation: {len(draft_terms_before)}")

    # Run term generation with category (if available)
    term_generation_responses = await call_term_generation_on_metadata_enrichment_asset(
        project_id, metadata_enrichment_id, data_asset_ids, category_id=category_id
    )
    LOGGER.info(
        f"Term generation completed: {len(term_generation_responses.successes)} successes, "
        f"{len(term_generation_responses.failures)} failures"
    )

    # Count draft terms after
    workflow_ids_after = await get_workflow_ids_from_project_id(project_id)
    draft_terms_after = await get_draft_terms_from_workflow_ids(workflow_ids_after)
    LOGGER.info(f"Draft terms after term generation: {len(draft_terms_after)}")

    # Calculate delta
    count_of_draft_terms = len(draft_terms_after) - len(draft_terms_before)
    LOGGER.info(f"New draft terms generated (delta): {count_of_draft_terms}")

    return term_generation_responses, count_of_draft_terms, category_id, category_name


async def execute_term_generation_v3(
    project_id: str,
    metadata_enrichment_id: str,
    data_asset_ids: List[str],  # noqa: UP006 # Baseline
    category_id: str,
) -> Tuple[Any, int]:  # noqa: UP006 # Baseline
    """
    Execute term generation using v3 API with category targeting.

    This function encapsulates the v3 term generation flow:
    1. Count draft terms before
    2. Run term generation with category_id
    3. Count draft terms after
    4. Return responses and delta

    Args:
        project_id: Project ID
        metadata_enrichment_id: MDE asset ID
        data_asset_ids: List of data asset IDs to process
        category_id: Target category UUID for generated terms

    Returns:
        Tuple of (term_generation_responses, count_of_draft_terms_from_term_generation)
    """
    from app.services.metadata_enrichment.utils.metadata_enrichment_common_utils import (  # noqa: I001 # Baseline
        get_workflow_ids_from_project_id,
        get_draft_terms_from_workflow_ids,
        call_term_generation_on_metadata_enrichment_asset_v3,
    )

    LOGGER.info(f"Executing v3 term generation flow with category: {category_id}")

    # Count draft terms before
    workflow_ids_before = await get_workflow_ids_from_project_id(project_id)
    draft_terms_before = await get_draft_terms_from_workflow_ids(workflow_ids_before)
    LOGGER.info(f"Draft terms before term generation: {len(draft_terms_before)}")

    # Run term generation with category
    term_generation_responses = (
        await call_term_generation_on_metadata_enrichment_asset_v3(
            project_id, metadata_enrichment_id, data_asset_ids, category_id
        )
    )
    LOGGER.info(
        f"Term generation completed: {len(term_generation_responses.successes)} successes, "
        f"{len(term_generation_responses.failures)} failures"
    )

    # Count draft terms after
    workflow_ids_after = await get_workflow_ids_from_project_id(project_id)
    draft_terms_after = await get_draft_terms_from_workflow_ids(workflow_ids_after)
    LOGGER.info(f"Draft terms after term generation: {len(draft_terms_after)}")

    # Calculate delta
    count_of_draft_terms = len(draft_terms_after) - len(draft_terms_before)
    LOGGER.info(f"New draft terms generated (delta): {count_of_draft_terms}")

    return term_generation_responses, count_of_draft_terms


def _build_category_selection_result(
    category_name: str,
    duplicates: List[Dict[str, Any]],  # noqa: UP006 # Baseline
    mde_name: str,
    project_name: str,
) -> Any:
    """
    Build a CategorySelectionResult for duplicate category names.

    Returns a result prompting the user to select one category UUID when
    multiple categories share the same name.
    """
    from app.services.metadata_enrichment.models.metadata_enrichment import (  # noqa: I001 # Baseline
        CategorySelectionResult,
        CategoryOption,
    )

    duplicate_count = len(duplicates)

    if duplicate_count <= 5:  # noqa: PLR2004 # Baseline
        category_options = [
            CategoryOption(
                category_id=cat["category_id"],
                category_name=cat["category_name"],
                parent_path=cat["parent_path"],
            )
            for cat in duplicates
        ]
        return CategorySelectionResult(
            message=(
                f"{duplicate_count} categories found with name '{category_name}'. "  # noqa: S608 # Baseline
                f"Select ONE category from the available_categories list below and re-run the tool "
                f"with category_name parameter set to the selected Category UUID.\n\n"
                f"**PRESENTATION**: Display available_categories as a markdown table with columns: "
                f"Parent Category Path | Category Name | Category UUID"
            ),
            available_categories=category_options,
            request_uuid=False,
            category_name=category_name,
            duplicate_count=duplicate_count,
            mde_name=mde_name,
            project_name=project_name,
        )

    # Too many duplicates — ask for UUID instead of listing them all
    return CategorySelectionResult(
        message=(
            f"{duplicate_count} categories found with name '{category_name}'. "
            f"Too many to display in a table. Please re-run the tool with category_name parameter "
            f"set to the UUID of the target category for term generation."
        ),
        available_categories=[],
        request_uuid=True,
        category_name=category_name,
        duplicate_count=duplicate_count,
        mde_name=mde_name,
        project_name=project_name,
    )


async def _resolve_category_name_v3(
    category_name: str,
    mde_name: str,
    project_name: str,
) -> Tuple[Optional[str], Optional[str], Optional[Any]]:  # noqa: UP006, UP045 # Baseline
    """
    Resolve a user-supplied category name (or UUID) to (category_id, resolved_name, selection_result).

    Returns (category_id, resolved_name, None) when resolved successfully.
    Returns (None, None, CategorySelectionResult) when the user must disambiguate.
    Raises ServiceError when the category does not exist.
    """
    LOGGER.info(f"Direct mode: Using provided category name '{category_name}'")

    if is_uuid_bool(category_name):
        LOGGER.info("category_name is a UUID — using direct API to skip Global Search")
        exists, resolved_name, _ = await get_category_by_id_direct(category_name)
        if not exists:
            raise ServiceError(
                f"Category '{category_name}' does not exist in the glossary. "
                f"Please check the category UUID or create it first."
            )
        LOGGER.info(
            f"Category validated via direct API: {resolved_name} ({category_name})"
        )
        return category_name, resolved_name, None

    exists, category_id, resolved_name, duplicates = await validate_category_exists(
        category_name
    )

    if duplicates:
        selection_result = _build_category_selection_result(
            category_name, duplicates, mde_name, project_name
        )
        LOGGER.info(
            f"Returning category selection result with {len(duplicates)} duplicates"
        )
        return None, None, selection_result

    if not exists or not category_id or not resolved_name:
        raise ServiceError(
            f"Category '{category_name}' does not exist in the glossary. "
            f"Please check the category name or create it first."
        )

    LOGGER.info(f"Category validated: {resolved_name} ({category_id})")
    return category_id, resolved_name, None


async def _resolve_job_name_v3(
    mde_id: str,
    project_id: str,
    job_name: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:  # noqa: UP006, UP045 # Baseline
    """
    Resolve a user-supplied job name to (category_id, category_name, job_id).

    Raises ServiceError when the job is not found, has no category configured,
    or the configured category no longer exists.
    """
    LOGGER.info(f"Direct mode: Using provided job name '{job_name}'")

    job_id = await resolve_job_identifier(mde_id, project_id, job_name)
    if not job_id:
        raise ServiceError(
            f"Job '{job_name}' not found in MDE. "
            f"Please check the job name or use a different job."
        )

    job_details = await get_job_details(mde_id, job_id, project_id)
    # Path: delegate_configuration.enrichment_objective.term_assignment.term_generation_target_category_id
    target_category_id = (
        job_details.get("delegate_configuration", {})
        .get("enrichment_objective", {})
        .get("term_assignment", {})
        .get("term_generation_target_category_id")
    )

    if not target_category_id:
        raise ServiceError(
            f"Job '{job_name}' does not have a target category configured. "
            f"Please configure term_generation_target_category_id in the job settings."
        )

    # target_category_id is always a UUID from job config — use direct API
    exists, category_name_resolved, _ = await get_category_by_id_direct(
        target_category_id
    )

    if not exists or not category_name_resolved:
        raise ServiceError(
            f"Job '{job_name}' references category '{target_category_id}' which does not exist. "
            f"Please update the job configuration with a valid category."
        )

    LOGGER.info(
        f"Job '{job_name}' resolved to category: {category_name_resolved} ({target_category_id})"
    )
    return target_category_id, category_name_resolved, job_id


async def resolve_target_category_v3(  # noqa: PLR0913 # Baseline
    mde_id: str,
    project_id: str,
    mde_name: str,
    project_name: str,
    job_name: Optional[str] = None,  # noqa: UP045 # Baseline
    category_name: Optional[str] = None,  # noqa: UP045 # Baseline
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[Any]]:  # noqa: UP006, UP045 # Baseline
    """
    Resolve target category for v3 term generation.

    Handles two modes:
    1. Direct Mode: User provides job_name or category_name
    2. Interactive Mode: List jobs and prompt user to select

    Args:
        mde_id: MDE asset ID
        project_id: Project ID
        mde_name: MDE name (for job selection response)
        project_name: Project name (for job selection response)
        job_name: Optional job name provided by user
        category_name: Optional category name provided by user

    Returns:
        Tuple of (category_id, category_name, job_id, job_selection_result)
        - If resolved: (category_id, category_name, job_id, None)
        - If needs selection: (None, None, None, TermGenerationJobSelectionResult)

    Raises:
        ServiceError: If category cannot be resolved or doesn't exist
    """
    LOGGER.info("Resolving target category for v3 term generation")

    if category_name:
        cat_id, resolved_name, selection_result = await _resolve_category_name_v3(
            category_name, mde_name, project_name
        )
        if selection_result is not None:
            return None, None, None, selection_result
        return cat_id, resolved_name, None, None

    if job_name:
        cat_id, cat_name, job_id = await _resolve_job_name_v3(
            mde_id, project_id, job_name
        )
        return cat_id, cat_name, job_id, None

    # Interactive Mode: No job_name or category_name provided
    LOGGER.info("Interactive mode: Listing jobs with target categories")
    jobs_with_categories = await get_jobs_with_target_categories(mde_id, project_id)

    if not jobs_with_categories:
        raise ServiceError(
            "No jobs with target categories found in this MDE. "
            "Please configure term_generation_target_category_id in at least one job, "
            "or provide a category_name parameter directly."
        )

    # If only one job, use it automatically
    if len(jobs_with_categories) == 1:
        job = jobs_with_categories[0]
        LOGGER.info(
            f"Only one job with target category found, using: "
            f"{job['job_name']} -> {job['target_category_name']}"
        )
        return (
            job["target_category_id"],
            job["target_category_name"],
            job["job_id"],
            None,
        )

    # Multiple jobs — return job selection result for user to choose
    from app.services.metadata_enrichment.models.metadata_enrichment import (  # noqa: I001 # Baseline
        TermGenerationJobSelectionResult,
        JobOption,
    )

    job_options = [
        JobOption(
            job_id=job["job_id"],
            job_name=job["job_name"],
            target_category_id=job["target_category_id"],
            target_category_name=job["target_category_name"],
        )
        for job in jobs_with_categories
    ]

    selection_result = TermGenerationJobSelectionResult(
        message=(
            f"Multiple jobs with target categories found in MDE '{mde_name}'. "  # noqa: S608 # Baseline
            f"Select ONE job from the available_jobs list and re-run the tool with job_name parameter. "
            f"Alternatively, provide category_name parameter to use a different custom category. "
            f"DO NOT run on multiple jobs simultaneously - only ONE job can be selected per execution."
        ),
        available_jobs=job_options,
        mde_name=mde_name,
        project_name=project_name,
    )

    LOGGER.info(f"Returning job selection result with {len(job_options)} options")
    return None, None, None, selection_result


# Made with Bob
