# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.constants import LINEAGE_BASE_ENDPOINT
from app.services.lineage.models.get_lineage_versions import GetLineageVersionsRequest, GetLineageVersionsResponse
from app.shared.exceptions.base import ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import is_valid_iso_date
from app.shared.utils.tool_helper_service import tool_helper_service


@service_registry.tool(
    name="lineage_get_lineage_versions",

    description="""
    Returns a list of versions of lineage that user can use for comparison.
    
    This tool takes two dates as input and returns a list of lineage versions that are available between the two dates.
    Data returned by this tool is used by the lineage_comparison tool and lineage_get_lineage_graph tool.

    Args:
        since (str): starting date in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ) Other ISO-8601 formats are also supported,
            notably: single year ("2025Z"), month ("2025-03Z"), week date format ("2025-W13Z", a week starts with Monday and ends with Sunday)

        until (str): ending date in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ) Other ISO-8601 formats are also supported,
            notably: single year ("2025Z"), month ("2025-03Z"), week date format ("2025-W13Z", a week starts with Monday and ends with Sunday)

    Returns:
        GetLineageVersionsResponse: An object containing a list of lineage versions that are available between the two dates.

    Raises:
        ExternalServiceError: If the API request fails (status code != 200)
        ToolProcessFailedError: If no entities are found for the given IDs
    """,
)
@auto_context
async def get_lineage_versions(
    input: GetLineageVersionsRequest,
) -> GetLineageVersionsResponse:
    # Validate input dates
    if not is_valid_iso_date(input.since):
        raise ServiceError(f"Invalid ISO-8601 date format for 'since': {input.since}")
    if not is_valid_iso_date(input.until):
        raise ServiceError(f"Invalid ISO-8601 date format for 'until': {input.until}")

    LOGGER.info(
        "get_lineage_versions called with dates since: %s until: %s",
        input.since,
        input.until,
    )

    params = {
        "since": input.since,
        "until": input.until,
        "order": "-datetime",
        "offset": 0,
        "limit": 1000,
    }
    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + LINEAGE_BASE_ENDPOINT + "/lineage_versions",
        params=params,
    )

    lineage_versions = response.get("lineage_versions", [])
    if not lineage_versions:
        return GetLineageVersionsResponse(dates=[])

    dates = [version.get("datetime") for version in lineage_versions if version.get("datetime")]

    return GetLineageVersionsResponse(dates=dates)

@service_registry.tool(
    name="lineage_get_lineage_versions",
    description="Returns a list of versions of lineage that user can use for comparison.",
)
@auto_context
async def wxo_get_lineage_versions(
    since: str, until: str
) -> GetLineageVersionsResponse:
    """Watsonx Orchestrator compatible version that expands GetLineageVersionsRequest object into individual parameters."""

    request = GetLineageVersionsRequest(since=since, until=until)

    # Call the original get_lineage_versions function
    return await get_lineage_versions(request)