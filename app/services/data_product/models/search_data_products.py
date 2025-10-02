from pydantic import BaseModel, Field
from typing import Union, Literal, List


class SearchDataProductsRequest(BaseModel):
    product_search_query: Union[Literal["*"], str] = Field(
        description='The search query to search for data products. If the user wants to search for data products with a specific name, this is the name to search for. If user wants to search for all data products, this value should be "*".'
    )
    search_filter_type: Literal["None", "Domain"] = Field(
        default="None",
        description="Specify what to filter by. It can be one of the following: None, Domain. If the user wants to filter by domain, then this value should be Domain otherwise None.",
    )
    search_filter_value: str = Field(
        description="The value to filter by. For example, if search_filter_type is Domain, then this is the domain name to filter by."
    )


class DataProduct(BaseModel):
    name: str
    description: str
    created_on: str
    domain: str
    data_asset_items: List


class SearchDataProductsResponse(BaseModel):
    count: int = Field(description="The number of data products found.")
    data_products: List[DataProduct]
