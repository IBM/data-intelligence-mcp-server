# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import List


class FindDeliveryMethodsBasedOnConnectionRequest(BaseModel):
    data_product_draft_id: str = Field(...,
        description="The ID of the data product draft."
    )
    data_asset_name: str = Field(...,
        description="The name of the data asset for which we need to find the delivery method options."
    )


class DeliveryMethod(BaseModel):
    delivery_method_id: str = Field(..., description="The ID of the delivery method.")
    delivery_method_name: str = Field(..., description="The name of the delivery method.")


class FindDeliveryMethodsBasedOnConnectionResponse(BaseResponseModel):
    delivery_methods: List[DeliveryMethod] = Field(..., description="List of delivery methods.")
