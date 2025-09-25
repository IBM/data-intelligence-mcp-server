# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field


class AttachURLContractToDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft."
    )
    contract_terms_id: str = Field(
        ..., description="The ID of the contract terms asset."
    )
    contract_url: str = Field(..., description="The contract URL.")
    contract_name: str = Field(..., description="The contract name.")
