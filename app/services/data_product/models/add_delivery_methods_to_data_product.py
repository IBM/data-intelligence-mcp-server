from pydantic import BaseModel, Field
from typing import List

class AddDeliveryMethodsToDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(..., description="The ID of the data product draft.")
    data_asset_name: str = Field(..., description="The name of the data asset in the data product draft for which we need to add delivery methods.")
    delivery_method_ids: List[str] = Field(..., description="The list of IDs of delivery methods selected by the user.")


