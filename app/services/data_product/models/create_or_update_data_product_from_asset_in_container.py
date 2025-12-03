from pydantic import BaseModel, Field
from typing import Literal

class CreateOrUpdateDataProductFromAssetInContainerRequest(BaseModel):
    name: str | None = Field(
        default=None,
        description="The name of the data product. Read the value from user."
    )
    description: str | None = Field(
        default=None,
        description="The description of the data product. Read the value from user."
    )
    asset_id: str = Field(
        description="The ID of the asset selected from container (catalog/project) to be added to the data product."
    )
    container_id_of_asset: str = Field(
        description="The ID of the container (catalog/project) that the asset belongs to."
    )
    container_type: Literal["catalog", "project"] = Field(
        ..., description="Where to create data product from - either 'project' or 'catalog'. This is a mandatory field."
    )
    existing_data_product_draft_id: str | None = Field(
        default=None,   
        description="The ID of the existing data product draft. This field is populated only if we are adding a data asset item to an existing draft, otherwise this field value is None."
    )


class CreateOrUpdateDataProductFromAssetInContainerResponse(BaseModel):
    message: str = Field(..., description="Success message of the create/update operation.")
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft created."
    )
    contract_terms_id: str = Field(
        ...,
        description="The ID of the contract terms of the data product draft created.",
    )
    url: str = Field(..., description="The URL of the data product draft created.")