# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field  # noqa: I001 # Baseline
from app.shared.models import BaseResponseModel
from typing import List  # noqa: UP035 # Baseline


class FindDeliveryMethodsBasedOnConnectionRequest(BaseModel):
    container_id: str = Field(
        ...,
        description="The ID of the container (catalog or project) where the data asset is located.",
    )
    container_type: str = Field(
        ..., description="The type of the container (either 'catalog' or 'project')."
    )
    data_asset_id: str = Field(
        ...,
        description="The ID of the data asset for which delivery methods are being requested.",
    )


class DeliveryMethod(BaseModel):
    delivery_method_id: str = Field(..., description="The ID of the delivery method.")
    delivery_method_name: str = Field(
        ..., description="The name of the delivery method."
    )
    delivery_method_description: str = Field(
        ..., description="The description of the delivery method."
    )


class FindDeliveryMethodsBasedOnConnectionResponse(BaseResponseModel):
    delivery_methods: List[DeliveryMethod] = Field(  # noqa: UP006 # Baseline
        ..., description="List of delivery methods."
    )
