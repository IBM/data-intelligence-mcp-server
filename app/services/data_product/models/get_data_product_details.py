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

from pydantic import BaseModel
from pydantic import Field
from app.shared.models import BaseResponseModel
from typing import Optional, List, Dict, Any


class GetDataProductDetailsRequest(BaseModel):
    data_product_id: Optional[str] = Field(
        default=None,
        description="Optional ID of the data product for which to get the details. Provide either data_product_id or data_product_name."
    )
    data_product_name: Optional[str] = Field(
        default=None,
        description="Optional name of the data product for which to get the details. Provide either data_product_id or data_product_name."
    )


class ColumnInfo(BaseModel):
    """Column information including schema and metadata."""
    name: str
    data_type: Optional[str] = None
    length: Optional[int] = None
    nullable: Optional[bool] = None
    native_type: Optional[str] = None
    is_primary_key: Optional[bool] = False
    column_info: Optional[Dict[str, Any]] = None


class PartOut(BaseModel):
    """Data product part/asset information."""
    name: str
    description: Optional[str] = None
    asset: Dict[str, Any]
    columns: Optional[List[ColumnInfo]] = None
    primary_keys: Optional[List[List[str]]] = None


class SubscribedAsset(BaseModel):
    """Subscribed asset information."""
    name: str
    flight_asset_id: Optional[str] = None
    url: Optional[str] = None


class DataProductDetails(BaseModel):
    """Complete data product details."""
    id: str
    version: Optional[str] = None
    state: Optional[str] = None
    description: Optional[str] = None
    parts_out: List[PartOut] = []


class GetDataProductDetailsResponse(BaseResponseModel):
    """Response containing data product details and subscription information."""
    data_product_details: Optional[DataProductDetails] = None
    data_product_subscription_details: List[SubscribedAsset] = Field(
        default_factory=list,
        description="List of subscribed assets with flight_asset_id or url for data access"
    )
