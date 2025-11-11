from pydantic import BaseModel, Field
from typing import Literal, Optional, List


class RequestNewDataProductRequest(BaseModel):
    name: str = Field(..., description="The name of the request.")
    overview: str = Field(
        ..., description="A brief overview of the data product you are requesting."
    )
    business_justification: str = Field(
        ...,
        description="The business justification for the data product you are requesting. Reasons why this data is required.",
    )
    key_features: str = Field(
        ...,
        description="The key features you expect in the data product you are requesting.",
    )
    privacy: Literal[
        "Yes - I need access to the sensitive information.",
        "No - I do not require access to sensitive information.",
        "No - I cannot use the data if it contains sensitive information.",
        "N/A",
    ] = Field(
        ...,
        description="If you need access to the sensitive information in the data product.",
    )
    due_date: str | None = Field(
        default=None,
        description="[Optional] The due date for the data product request. This should be a date value in the format 'YYYY-MM-DD'.",
    )
    domain: str | None = Field(
        default=None, description="[Optional] The business domain for the data product."
    )
    sample: str | None = Field(
        default=None,
        description="[Optional] URL or description of sample of the requested data product.",
    )
    delivery_methods: List[str] | None = Field(
        default=None,
        description="[Optional] List of delivery methods of the requested new data product.",
    )
    sharing_requirements: (
        List[
            Literal[
                "Yes - I need to share this data with users who are internal to my organization.",
                "Yes - I need to share this data with users who are external to my organization.",
            ]
        ]
        | None
    ) = Field(
        default=None,
        description="[Optional] Sharing requirements for the requested data product.",
    )
    data_quality: str | None = Field(
        default=None,
        description="[Optional] Data quality expectations for the requested data product.",
    )
    refresh_frequency: str | None = Field(
        default=None,
        description="[Optional] Frequency to refresh the requested data product.",
    )


class RequestNewDataProductResponse(BaseModel):
    message: str = Field(
        ..., description="Message indicating the status of the data product request."
    )
    url: str = Field(
        ..., description="URL to access the status of the data product requests."
    )
