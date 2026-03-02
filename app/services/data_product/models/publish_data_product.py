# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel


class PublishDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft."
    )

class PublishDataProductResponse(BaseResponseModel):
    message: str = Field(..., description="The message indicating the success publish operation.")
    url: str = Field(..., description="The URL of the published data product.")
