# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.core.registry import service_registry
from app.services.constants import LINEAGE_BASE_ENDPOINT
from app.services.lineage.models.convert_to_lineage_id import (
    ConvertToLineageIdRequest,
    ConvertToLineageIdResponse,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import is_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


@service_registry.tool(
    name="lineage_convert_to_lineage_id",
    description="Converts asset IDs from container scope into a unique lineage identifier required by other lineage tools.",
)
@auto_context
async def convert_to_lineage_id(
    input: ConvertToLineageIdRequest,
) -> ConvertToLineageIdResponse:
    is_uuid(input.container_id)
    is_uuid(input.asset_id)

    LOGGER.info(
        "convert_to_lineage_id called with container_id: %s and asset_id: %s",
        input.container_id,
        input.asset_id,
    )

    params = {
        "container_id": input.container_id,
        "asset_id": input.asset_id,
        "validate_lineage_entity": True,
    }

    response = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + LINEAGE_BASE_ENDPOINT + "/entities",
        params=params,
    )

    entities = response.get("entities")
    if not entities:
        raise ServiceError(
            "Tool convert_to_lineage_id finished successfully but no entities were found."
        )

    return ConvertToLineageIdResponse(
        lineage_id=response.get("entities", [])[0].get("id")
    )


@service_registry.tool(
    name="lineage_convert_to_lineage_id",
    description="Converts asset IDs from container scope into a unique lineage identifier required by other lineage tools.",
)
@auto_context
async def wxo_convert_to_lineage_id(
    container_id: str, asset_id: str
) -> ConvertToLineageIdResponse:
    """Watsonx Orchestrator compatible version that expands ConvertToLineageIdRequest object into individual parameters."""

    request = ConvertToLineageIdRequest(container_id=container_id, asset_id=asset_id)

    # Call the original convert_to_lineage_id function
    return await convert_to_lineage_id(request)
