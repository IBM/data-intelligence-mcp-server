from pydantic import BaseModel, Field
from typing import Literal

class CreateDataProductFromAssetInContainerRequest(BaseModel):
    name: str = Field(description="The name of the data product.")
    asset_id: str = Field(
        description="The ID of the asset selected from container (catalog/project) to be added to the data product."
    )
    container_id_of_asset: str = Field(
        description="The ID of the container (catalog/project) that the asset selected is part of."
    )
    container_type: Literal["catalog", "project"] = Field(
        ..., description="Where to create data product from - either 'project' or 'catalog'. This is a mandatory field."
    )


class CreateDataProductFromAssetInContainerResponse(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft created."
    )
    contract_terms_id: str = Field(
        ...,
        description="The ID of the contract terms of the data product draft created.",
    )
    url: str = Field(..., description="The URL of the data product draft created.")