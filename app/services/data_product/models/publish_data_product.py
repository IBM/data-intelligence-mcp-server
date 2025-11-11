from pydantic import BaseModel, Field


class PublishDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft."
    )

class PublishDataProductResponse(BaseModel):
    message: str = Field(..., description="The message indicating the success publish operation.")
    url: str = Field(..., description="The URL of the published data product.")
