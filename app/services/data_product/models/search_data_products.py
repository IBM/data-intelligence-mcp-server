# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Union, Literal, List, Optional


class SearchDataProductsRequest(BaseModel):
    product_search_query: Union[Literal["*"], str] = Field(
        description='The search query to search for data products and data product drafts. If the user wants to search for data products or drafts with a specific name, this is the name to search for. If user wants to search for all data products or drafts, this value should be "*".'
    )
    domain: Optional[str] = Field(
        default=None,
        description='Filter by business domain name (e.g., "Finance", "Business Management").'
    )
    created_date_after: Optional[str] = Field(
        default=None,
        description='Filter products created on or after this date. Format: YYYY-MM-DD (e.g., "2026-01-15").'
    )
    created_date_before: Optional[str] = Field(
        default=None,
        description='Filter products created on or before this date. Format: YYYY-MM-DD (e.g., "2026-01-31").'
    )
    state_filter: Optional[Union[Literal["draft"], Literal["published"]]] = Field(
        default=None,
        description='Filter by data product state. Options: "draft" (unpublished products), "published" (published products). If None, searches both draft and published products.'
    )


class DataProduct(BaseModel):
    data_product_id: str
    data_product_version_id: str
    url: str
    name: str
    description: str
    created_on: str
    domain: str
    data_asset_items: List
    state: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[List[str]] = None


class SearchDataProductsResponse(BaseResponseModel):
    message: str = "Only maximum 20 products sorted by last updated are returned."
    count: int = Field(default=0, description="The number of data products found. This can be more than 20, but maximum data products returnable is 20.")
    data_products: List[DataProduct] = Field(default_factory=list, description="List of data products found.")
