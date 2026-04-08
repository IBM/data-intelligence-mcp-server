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

from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel


class GetDataProductSubscriptionDetailsRequest(BaseModel):
    """Request model for getting data product subscription details."""
    
    subscription_id: str = Field(
        description=(
            "The ID of the subscription (asset list) to retrieve items from. "
            "This is a UUID obtained from search_data_product_subscriptions."
        )
    )


class SubscriptionItem(BaseModel):
    """Model representing a single item in a subscription."""
    
    id: Optional[str] = Field(default=None, description="Item ID")
    asset: Optional[Dict[str, Any]] = Field(default=None, description="Asset information including ID and type")
    properties: Optional[Dict[str, Any]] = Field(default=None, description="Item properties including delivery details")
    state: Optional[str] = Field(default=None, description="Item delivery state (e.g., succeeded, failed, in_progress)")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    last_updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class GetDataProductSubscriptionDetailsResponse(BaseResponseModel):
    """Response model for getting data product subscription details."""
    
    items: List[SubscriptionItem] = Field(
        default_factory=list,
        description="List of items in the subscription with delivery details"
    )
    total_count: int = Field(
        default=0,
        description="Total number of items in the subscription"
    )
    subscription_id: str = Field(
        description="The subscription ID that was queried"
    )

# Made with Bob
