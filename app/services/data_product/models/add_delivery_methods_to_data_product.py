# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import List

class AddDeliveryMethodsToDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(..., description="The ID of the data product draft.")
    data_asset_name: str = Field(..., description="The name of the data asset in the data product draft for which we need to add delivery methods.")
    delivery_method_ids: List[str] = Field(..., description="The list of IDs of delivery methods selected by the user.")


