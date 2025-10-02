from pydantic import BaseModel, Field
from typing import List


class FindDeliveryMethodsBasedOnConnectionRequest(BaseModel):
    data_product_draft_id: str = Field(...,
        description="The ID of the data product draft for which we need to find the delivery method options."
    )


class DeliveryMethod(BaseModel):
    delivery_method_id: str = Field(..., description="The ID of the delivery method.")
    delivery_method_name: str = Field(..., description="The name of the delivery method.")


class FindDeliveryMethodsBasedOnConnectionResponse(BaseModel):
    delivery_methods: List[DeliveryMethod] = Field(..., description="List of delivery methods.")
