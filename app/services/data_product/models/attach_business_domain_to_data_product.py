# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from pydantic import BaseModel, Field


class AttachBusinessDomainToDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft to which the business domain is to be attached."
    )
    domain: str = Field(..., description="The business domain to be attached to the data product draft.")
