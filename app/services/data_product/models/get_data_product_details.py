# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pydantic import BaseModel  # noqa: I001 # Baseline
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import Optional, List, Dict, Any  # noqa: UP035 # Baseline


class GetDataProductDetailsRequest(BaseModel):
    data_product_version_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Optional ID of the data product version for which to get the details. Provide either data_product_version_id or data_product_name.",
    )
    data_product_name: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Optional name of the data product for which to get the details. Provide either data_product_version_id or data_product_name.",
    )


class ColumnInfo(BaseModel):
    """Column information including schema and metadata."""

    name: str
    data_type: Optional[str] = None  # noqa: UP045 # Baseline
    length: Optional[int] = None  # noqa: UP045 # Baseline
    nullable: Optional[bool] = None  # noqa: UP045 # Baseline
    native_type: Optional[str] = None  # noqa: UP045 # Baseline
    is_primary_key: Optional[bool] = False  # noqa: UP045 # Baseline
    column_info: Optional[Dict[str, Any]] = None  # noqa: UP006, UP045 # Baseline


class DeliveryMethodInfo(BaseModel):
    """A delivery method enabled by the publisher for a data product part."""
    id: str = Field(description="Delivery method asset ID. Use as delivery_method_id when subscribing.")
    name: str | None = Field(
        default=None,
        description="Delivery method name. Use as delivery_method_name when subscribing.",
    )


class PartOut(BaseModel):
    """Data product part/asset information."""

    name: str
    description: Optional[str] = None  # noqa: UP045 # Baseline
    asset: Dict[str, Any]  # noqa: UP006 # Baseline
    columns: Optional[List[ColumnInfo]] = None  # noqa: UP006, UP045 # Baseline
    primary_keys: Optional[List[List[str]]] = None  # noqa: UP006, UP045 # Baseline
    delivery_methods: list[DeliveryMethodInfo] | None = Field(
        default=None,
        description=(
            "Delivery methods enabled by the publisher for this part. "
            "Only these can be used when subscribing to the data product."
        ),
    )


class SubscribedAsset(BaseModel):
    """Subscribed asset information."""

    name: str
    flight_asset_id: Optional[str] = None  # noqa: UP045 # Baseline
    url: Optional[str] = None  # noqa: UP045 # Baseline
    flight_client_url: Optional[str] = None  # noqa: UP045 # Baseline


class DataProductDetails(BaseModel):
    """Complete data product details."""

    id: str
    url: str
    version: Optional[str] = None  # noqa: UP045 # Baseline
    state: Optional[str] = None  # noqa: UP045 # Baseline
    description: Optional[str] = None  # noqa: UP045 # Baseline
    parts_out: List[PartOut] = []  # noqa: UP006 # Baseline


class GetDataProductDetailsResponse(BaseResponseModel):
    """Response containing data product details and subscription information."""

    data_product_details: DataProductDetails = Field(
        default_factory=lambda: DataProductDetails(id="", url="", parts_out=[]),
        description="The data product details including version, state, description, and parts/assets information.",
    )
    data_product_subscription_details: List[SubscribedAsset] = Field(  # noqa: UP006 # Baseline
        default_factory=list,
        description="The details of the latest successfully delivered subscription including assets with flight_asset_id or url for data access. Only includes the latest subscription with 'succeeded' state - failed subscription deliveries are not returned.",
    )
