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


class SearchDataProductSubscriptionsRequest(BaseModel):
    """Request model for searching data product subscriptions."""
    
    query: Optional[str] = Field(
        default=None,
        description=(
            "Optional CEL query to filter subscriptions. The filter type==\"order\" is automatically appended. "
            "IMPORTANT: To find subscriptions for a specific data product, extract the asset.id from GetDataProductDetails "
            "(NOT the catalog ID!) and use: asset.id==\"<asset_id>\". "
            "Example: asset.id==\"6d80d7d4-ca55-4fb0-8b70-bb799a2881dd\". "
            "Other examples: name==\"My data product\", state==\"succeeded\", created_at>=\"2025-10-08T23:00:00Z\". "
            "Leave empty to retrieve all subscriptions."
        )
    )
    limit: Optional[int] = Field(
        default=None,
        description="Maximum number of results to return (1-200). Use None to not apply limit, 0 to only get total_count."
    )
    start: Optional[str] = Field(
        default=None,
        description="Pagination start token from previous response. Leave empty to start from beginning."
    )
    sort: Optional[str] = Field(
        default=None,
        description="Comma-separated sort fields (e.g., 'created_at,-last_updated_at'). Prefix with '-' for descending."
    )


class Subscription(BaseModel):
    """Model representing a single subscription."""
    
    id: str = Field(description="Subscription ID")
    name: Optional[str] = Field(default=None, description="Subscription name")
    description: Optional[str] = Field(default=None, description="Subscription description")
    state: Optional[str] = Field(default=None, description="Subscription state (e.g., succeeded, delivered, failed)")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    last_updated_at: Optional[str] = Field(default=None, description="Last update timestamp")
    asset: Optional[Dict[str, Any]] = Field(default=None, description="Associated asset information")
    access_control: Optional[Dict[str, Any]] = Field(default=None, description="Access control information")


class SearchDataProductSubscriptionsResponse(BaseResponseModel):
    """Response model for searching data product subscriptions."""
    
    subscriptions: List[Subscription] = Field(
        default_factory=list,
        description="List of subscriptions matching the search criteria"
    )
    total_count: int = Field(
        default=0,
        description="Total number of subscriptions matching the query"
    )
    limit: Optional[int] = Field(
        default=None,
        description="Limit applied to the results"
    )
    next: Optional[str] = Field(
        default=None,
        description="URL for next page of results (if available)"
    )
    first: Optional[str] = Field(
        default=None,
        description="URL for first page of results"
    )

# Made with Bob
