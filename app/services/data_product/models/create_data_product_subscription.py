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

from typing import Literal

from pydantic import BaseModel, Field

from app.services.data_product.models.subscription_items import SubscriptionItem
from app.shared.models import BaseResponseModel


class CreateDataProductSubscriptionRequest(BaseModel):
    """Request model for creating a data product subscription."""

    data_product_version_id: str = Field(
        description=(
            "UUID of the data product version to subscribe to. "
            "Obtain from get_data_product_details (the part BEFORE '@' in the top-level id, "
            "e.g. '2b0bf220-079c-11ee-be56-0242ac120002')."
        )
    )
    name: str | None = Field(
        default=None,
        description="Human-readable name for this subscription (max 256 chars).",
    )
    description: str | None = Field(
        default=None,
        description="Description of the subscription (max 4000 chars).",
    )
    business_justification: str | None = Field(
        default=None,
        description="Business justification for requesting access (max 5000 chars).",
    )
    state: Literal["submitted", "draft"] = Field(
        default="submitted",
        description=(
            "Subscription state. "
            "'submitted' — finalize immediately; all parts must have items provided. "
            "'draft' — create an empty or partial subscription to add items incrementally "
            "(required when parts use different delivery methods). "
            "Use 'draft' + add_items_to_data_product_subscription + submit_data_product_subscription "
            "for multi-part data products with mixed delivery methods."
        ),
    )
    items: list[SubscriptionItem] | None = Field(
        default=None,
        description=(
            "Typed subscription items — one per data product part. "
            "Required when state='submitted' (all parts must be covered). "
            "Optional for state='draft' (can be empty or partial). "
            "Each item's delivery_method_name discriminates the required fields."
        ),
    )


class CreateDataProductSubscriptionResponse(BaseResponseModel):
    """Response model for creating a data product subscription."""

    subscription_id: str | None = Field(
        default=None,
        description="UUID of the created subscription. Use this ID with add_items, submit, and remove_item tools.",
    )
    state: str | None = Field(
        default=None,
        description=(
            "State returned by the server. Note: a 'submitted' request returns state='received' "
            "from the server — this is expected and not an error. A 'draft' request returns 'draft'."
        ),
    )
    data_product_version_id: str | None = Field(
        default=None,
        description="The data product version ID this subscription is for.",
    )
    name: str | None = Field(default=None, description="Subscription name.")
    description: str | None = Field(default=None, description="Subscription description.")

# Made with Bob
