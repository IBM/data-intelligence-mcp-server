# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field


class CreateUrlDataProductRequest(BaseModel):
    name: str = Field(..., description="The name of the data product.")
    url_value: str = Field(..., description="The URL value of the data product.")
    url_name: str = Field(..., description="The URL name of the data product.")


class CreateUrlDataProductResponse(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft created."
    )
    contract_terms_id: str = Field(
        ...,
        description="The ID of the contract terms of the data product draft created.",
    )
    create_data_product_response: dict = Field(
        ..., description="The Create Data Product API response."
    )
