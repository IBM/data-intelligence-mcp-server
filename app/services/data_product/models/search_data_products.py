# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Union, Literal, List


class SearchDataProductsRequest(BaseModel):
    product_search_query: Union[Literal["*"], str] = Field(
        description='The search query to search for data products and data product drafts. If the user wants to search for data products or drafts with a specific name, this is the name to search for. If user wants to search for all data products or drafts, this value should be "*".'
    )
    search_filter_type: Literal["None", "Domain"] = Field(
        default="None",
        description="Specify what to filter by. It can be one of the following: None, Domain. If the user wants to filter by domain, then this value should be Domain otherwise None.",
    )
    search_filter_value: str = Field(
        default="None",
        description="The value to filter by. For example, if search_filter_type is Domain, then this is the domain name to filter by. Use 'None' when search_filter_type is 'None'."
    )


class DataProduct(BaseModel):
    data_product_id: str
    name: str
    description: str
    created_on: str
    domain: str
    data_asset_items: List


class SearchDataProductsResponse(BaseResponseModel):
    message: str = "Only maximum 20 products sorted by last updated are returned."
    count: int = Field(default=0, description="The number of data products found. This can be more than 20, but maximum data products returnable is 20.")
    data_products: List[DataProduct] = Field(default_factory=list, description="List of data products found.")
