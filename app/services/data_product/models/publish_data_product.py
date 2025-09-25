from pydantic import BaseModel, Field


class PublishDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft."
    )
