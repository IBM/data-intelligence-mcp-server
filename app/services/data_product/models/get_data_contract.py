# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Literal


class GetDataContractRequest(BaseModel):
    data_product_id: str = Field(..., description="The ID of the data product for which we need to get the data contract. Can be a draft or published data product.")
    data_product_state: Literal["draft", "available"] = Field(..., description="The state of the data product - should be one of 'draft' or 'available'")


class GetDataContractResponse(BaseResponseModel):
    data_contract: str = Field(..., description="Data contract of the data product.")