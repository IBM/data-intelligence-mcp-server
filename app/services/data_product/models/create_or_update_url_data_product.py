# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field


class CreateOrUpdateUrlDataProductRequest(BaseModel):
    name: str | None = Field(
        default=None,
        description="The name of the data product. Read the value from user."
    )
    description: str | None = Field(
        default=None,
        description="The description of the data product. Read the value from user."
    )
    url_value: str = Field(..., description="The URL value of the data product. Read the value from user.")
    url_name: str = Field(..., description="The URL name of the data product. Read the value from user.")
    existing_data_product_draft_id: str | None = Field(
        default=None,
        description="The ID of the existing data product draft. This field is populated only if we are adding a URL asset item to an existing draft, otherwise this field value is None."
    )


class CreateOrUpdateUrlDataProductResponse(BaseModel):
    message: str = Field(..., description="Success message of the create/update operation.")
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft created."
    )
    contract_terms_id: str = Field(
        ...,
        description="The ID of the contract terms of the data product draft created.",
    )
    url: str = Field(..., description="The URL of the data product draft created.")
