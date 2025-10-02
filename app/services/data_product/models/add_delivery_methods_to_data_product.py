from pydantic import BaseModel, Field
from typing import List

class AddDeliveryMethodsToDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(..., description="The ID of the data product draft.")
    delivery_method_ids: List[str] = Field(..., description="The list of IDs of delivery methods selected by the user.")


