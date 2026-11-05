# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field  # noqa: I001 # Baseline
from app.shared.models import BaseResponseModel
from typing import Union, Literal, List, Optional  # noqa: UP035 # Baseline


class SearchDataProductsRequest(BaseModel):
    product_search_query: Union[Literal["*"], str] = Field(  # noqa: UP007 # Baseline
        description='The search query to search for data products and data product drafts. If the user wants to search for data products or drafts with a specific name, this is the name to search for. If user wants to search for all data products or drafts, this value should be "*".'
    )
    domain: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description='Filter by business domain name (e.g., "Finance", "Business Management").',
    )
    created_date_after: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description='Filter products created on or after this date. Format: YYYY-MM-DD (e.g., "2026-01-15").',
    )
    created_date_before: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description='Filter products created on or before this date. Format: YYYY-MM-DD (e.g., "2026-01-31").',
    )
    state_filter: Optional[Union[Literal["draft"], Literal["published"]]] = Field(  # noqa: UP007, UP045 # Baseline
        default=None,
        description='Filter by data product state. Options: "draft" (unpublished products), "published" (published products). If None, searches both draft and published products.',
    )


class DataProduct(BaseModel):
    data_product_group_id: str = Field(
        description="The identifier for the version chain/group that this data product belongs to. Multiple versions of the same product share this ID."
    )
    data_product_version_id: str = Field(
        description="The unique identifier for this specific data product version. Use this ID for most API operations and tool calls."
    )
    url: str
    name: str
    description: str
    created_on: str
    domain: str
    data_asset_items: List  # noqa: UP006 # Baseline
    state: Optional[str] = None  # noqa: UP045 # Baseline
    version: Optional[str] = None  # noqa: UP045 # Baseline
    tags: Optional[List[str]] = None  # noqa: UP006, UP045 # Baseline
    contract_test_status: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description='The result of the last contract test run. Typical values are "Queued", "Failed", or "Completed".',
    )
    contract_test_last_run_at: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="ISO 8601 timestamp of when the contract test was last executed.",
    )


class SearchDataProductsResponse(BaseResponseModel):
    message: str = "Only maximum 20 products sorted by last updated are returned."
    count: int = Field(
        default=0,
        description="The number of data products found. This can be more than 20, but maximum data products returnable is 20.",
    )
    data_products: List[DataProduct] = Field(  # noqa: UP006 # Baseline
        default_factory=list, description="List of data products found."
    )
