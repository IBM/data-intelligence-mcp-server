# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Annotated
from pydantic import Field

from app.core.registry import service_registry
from app.services.constants import LINEAGE_BASE_ENDPOINT
from app.services.lineage.models.convert_to_lineage_id import (
    ConvertToLineageIdRequest,
    ConvertToLineageIdResponse,
)
from app.shared.exceptions.base import ValidationError
from app.shared.logging.generate_context import auto_context
from app.shared.logging.utils import LOGGER
from app.shared.utils.helpers import is_uuid
from app.shared.utils.tool_helper_service import tool_helper_service


async def _convert_to_lineage_id(
    input: ConvertToLineageIdRequest,
) -> ConvertToLineageIdResponse:
    is_uuid(input.container_id)
    is_uuid(input.asset_id)

    LOGGER.info(
        "convert_asset_to_lineage_id called with container_id: %s and asset_id: %s",
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
        raise ValidationError(
            "Tool convert_asset_to_lineage_id finished successfully but no entities were found.",
            remediation_steps="Verify if lineage is enabled, reimport this asset or try different one."
        )

    return ConvertToLineageIdResponse(
        lineage_id=response.get("entities", [])[0].get("id")
    )


@service_registry.tool(
    name="convert_asset_to_lineage_id",
    annotations={
        "readOnlyHint": True,
        "title": "Convert Asset and Container IDs to Lineage Identifier"
    },
    description="Use this tool when you converts asset IDs from container scope into a unique lineage identifier required by other lineage tools."
    "This is an alternative to search_lineage_assets when you already know the exact container and asset IDs. " \
    "Return: A unique 64-character hexadecimal lineage identifier that can be used with other lineage tools.",
)
@auto_context
async def convert_asset_to_lineage_id(
    container_id: Annotated[str, Field(description="The container identifier - can be either a catalog ID or project ID (must be valid UUID)")],
    asset_id: Annotated[str, Field(description="The asset identifier within the container (must be valid UUID)")]
) -> ConvertToLineageIdResponse:
    """Wrapper that expands ConvertToLineageIdRequest object into individual parameters."""

    request = ConvertToLineageIdRequest(container_id=container_id, asset_id=asset_id)

    # Call the original convert_asset_to_lineage_id function
    return await _convert_to_lineage_id(request)
