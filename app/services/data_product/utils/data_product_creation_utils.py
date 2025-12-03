# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.services.data_product.utils.common_utils import get_dph_catalog_id_for_user
from app.shared.exceptions.base import ServiceError


def is_data_product_draft_create(request) -> bool:
    return not request.existing_data_product_draft_id and request.existing_data_product_draft_id != "None"


@auto_context
def validate_inputs_for_draft_create(request, *additional_fields_to_validate):
    required_fields = ("name",) + additional_fields_to_validate

    for field in required_fields:
        value = getattr(request, field, None)
        if not value:
            msg = f"{field.capitalize()} of the data product is mandatory to create a data product draft."
            LOGGER.error(msg)
            raise ServiceError(msg)


@auto_context
async def create_part_asset_and_set_relationship(
    asset_name: str, target_asset_id: str
) -> None:
    """This common method can be called from create data product tools to:
    1. Create a part asset.
    2. Set relationship between the part asset and the target asset.
    """
    LOGGER.info("Creating ibm_data_product_part asset and setting relationship.")
    dph_catalog_id = await get_dph_catalog_id_for_user()
    payload = {
        "metadata": {
            "name": asset_name,
            "asset_type": "ibm_data_product_part",
            "rov": {"mode": 0},
        },
        "entity": {"ibm_data_product_part": {"dataset": True}},
    }
    response = await tool_helper_service.execute_post_request(
        url=f"{tool_helper_service.base_url}/v2/assets?catalog_id={dph_catalog_id}&hide_deprecated_response_fields=false",
        json=payload,
    )
    data_product_part_asset_id = response["metadata"]["asset_id"]

    LOGGER.info(
        f"Created ibm_data_product_part asset with id {data_product_part_asset_id}."
    )
    # creating relationship
    await create_relationship(dph_catalog_id, target_asset_id, data_product_part_asset_id)


async def create_relationship(
    dph_catalog_id: str, target_asset_id: str, data_product_part_asset_id: str
):
    payload = {
        "relationships": [
            {
                "relationship_name": "has_part",
                "source": {"catalog_id": dph_catalog_id, "asset_id": target_asset_id},
                "target": {
                    "catalog_id": dph_catalog_id,
                    "asset_id": data_product_part_asset_id,
                },
            }
        ]
    }

    await tool_helper_service.execute_post_request(
        f"{tool_helper_service.base_url}/v2/assets/set_relationships", json=payload
    )
    LOGGER.info(
        f"Created relationship between {target_asset_id} and {data_product_part_asset_id}."
    )
