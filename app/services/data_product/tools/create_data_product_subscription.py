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

from typing import Annotated, Any, Literal

from pydantic import Field

from app.core.registry import service_registry
from app.services.data_product.models.create_data_product_subscription import (
    CreateDataProductSubscriptionRequest,
    CreateDataProductSubscriptionResponse,
)
from app.services.data_product.models.subscription_items import (
    DataExtractItem,
    NoConsumerInputItem,
    SubscriptionItem,
    WxdIngestItem,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service

# ---------------------------------------------------------------------------
# Item → item_properties payload conversion
# ---------------------------------------------------------------------------

def _build_item_properties(item: SubscriptionItem) -> dict[str, Any]:
    """
    Convert a typed SubscriptionItem into the item_properties dict expected by
    POST /data_product_exchange/v1/subscriptions.

    The Java API expects:
      {
        "data_product_part_id": "<part-uuid>",
        "delivery_method": {"id": "<dm-uuid>"},
        "consumer_input": { ... delivery-method-specific fields ... }
      }
    """
    props: dict[str, Any] = {
        "data_product_part_id": item.data_product_part_id,
        "delivery_method": {"id": item.delivery_method_id},
    }

    consumer_input: dict[str, Any] = {}

    # query_values are common across all item types (parameterized query assets)
    if item.query_values:
        consumer_input["query_values"] = [
            {"name": qv.name, "type": qv.type, "value": qv.value}
            for qv in item.query_values
        ]

    if isinstance(item, NoConsumerInputItem):
        # No delivery-method-specific consumer_input beyond optional query_values
        pass

    elif isinstance(item, DataExtractItem):
        consumer_input["format"] = item.format

    elif isinstance(item, WxdIngestItem):
        consumer_input["catalog"] = item.wxd_catalog
        consumer_input["schema"] = item.wxd_schema
        consumer_input["table"] = item.wxd_table
        consumer_input["target_connection"] = {
            "id": item.target_connection_id,
            "container": {
                "id": item.target_connection_container_id,
                "type": item.target_connection_container_type,
            },
        }
        consumer_input["source_connection"] = {
            "id": item.source_connection_id,
            "container": {
                "id": item.source_connection_container_id,
                "type": item.source_connection_container_type,
            },
        }

    # Always send consumer_input (even if empty): the API dereferences it
    # unconditionally and returns 500 (NPE) when it is missing.
    props["consumer_input"] = consumer_input

    return props


def _build_request_payload(request: CreateDataProductSubscriptionRequest) -> dict[str, Any]:
    """Build the full JSON payload for POST /data_product_exchange/v1/subscriptions."""
    payload: dict[str, Any] = {
        "data_product_version_id": request.data_product_version_id,
        "state": request.state,
    }
    if request.name:
        payload["name"] = request.name
    if request.description:
        payload["description"] = request.description
    if request.business_justification:
        payload["business_justification"] = request.business_justification
    if request.items:
        payload["item_properties"] = [
            _build_item_properties(item) for item in request.items
        ]
    return payload


# ---------------------------------------------------------------------------
# Core async function
# ---------------------------------------------------------------------------

async def _create_data_product_subscription(
    request: CreateDataProductSubscriptionRequest,
) -> CreateDataProductSubscriptionResponse:
    """
    Create a data product subscription.

    For state='submitted': all parts must have items; subscription is finalized immediately.
    For state='draft':     items are optional; use add_items + submit to finalize.

    Note: the server maps 'submitted' → CAMS state 'received'.
    A response with state='received' after a submitted request is expected and correct.
    """
    LOGGER.info(
        f"In create_data_product_subscription, "
        f"data_product_version_id={request.data_product_version_id}, "
        f"state={request.state}, "
        f"items={len(request.items) if request.items else 0}"
    )

    # Validate: submitted state requires at least one item
    if request.state == "submitted" and not request.items:
        raise ServiceError(
            "state='submitted' requires at least one item in the items list. "
            "Every data product part must have a corresponding subscription item.",
            remediation_steps=(
                "Call get_data_product_details to list all parts_out for the data product, "
                "then provide one typed item per part. "
                "Alternatively use state='draft' to build the subscription incrementally."
            ),
        )

    url = f"{tool_helper_service.base_url}/data_product_exchange/v1/subscriptions"
    payload = _build_request_payload(request)

    LOGGER.debug(f"POST {url} payload keys: {list(payload.keys())}")

    try:
        response_data = await tool_helper_service.execute_post_request(
            url=url,
            json=payload,
            tool_name="create_data_product_subscription",
        )
    except ServiceError:
        raise
    except Exception as e:
        raise ServiceError(
            f"Failed to create data product subscription: {e!s}",
            remediation_steps=(
                "Verify the data_product_version_id is a valid UUID of an 'available' data product. "
                "Ensure all delivery_method_ids are valid and match the parts. "
                "For direct-access delivery methods, check that your CAMS connection credentials are valid — "
                "invalid credentials result in a 403 Forbidden response."
            ),
        ) from e

    if not isinstance(response_data, dict):
        raise ServiceError(
            "Unexpected response format from subscription API.",
            remediation_steps="Retry the operation. If the problem persists, contact support.",
        )

    subscription_id = response_data.get("id")
    LOGGER.info(f"Subscription created successfully: id={subscription_id}, state={response_data.get('state')}")

    return CreateDataProductSubscriptionResponse(
        subscription_id=subscription_id,
        state=response_data.get("state"),
        data_product_version_id=response_data.get("data_product_version_id"),
        name=response_data.get("name"),
        description=response_data.get("description"),
    )


# ---------------------------------------------------------------------------
# Registered tool
# ---------------------------------------------------------------------------

@service_registry.tool(
    name="create_data_product_subscription",
    description="""Use this tool to subscribe to a data product on IBM Cloud Data Product Hub.

**PREREQUISITES — always call this first:**
`get_data_product_details` — get the data product version ID, the list of parts (parts_out[].asset.id),
and the delivery methods ENABLED for each part (parts_out[].delivery_methods, with id and name).
Only use a delivery method listed there for that part — each part can have a different set.
Do NOT use `list_data_product_delivery_methods` for subscriptions: it lists every method compatible with
the asset's connection (used when authoring a draft), not the ones enabled on the published product.

**Choosing the right state:**

Use state='submitted' (default) when all parts share the same delivery method type and you
have all required connection details — the subscription is finalized in one call.

Use state='draft' when:
- The data product has parts that use DIFFERENT delivery method types
  (e.g. Part 1 uses 'Use Flight service', Part 2 uses 'Watsonx.data-ingest')
- You want the user to review before finalizing

Draft flow for mixed delivery methods:
  1. create_data_product_subscription(state='draft')          → get subscription_id
  2. add_items_to_data_product_subscription(subscription_id, items=[...])  ← repeat per delivery method type
  3. submit_data_product_subscription(subscription_id)        → finalize

**Items — delivery_method_name discriminates required fields:**

Each item in `items` must have a `delivery_method_name` matching one of the SUPPORTED methods:
- 'Use Flight service'   → IBM Flight service data access; no consumer input needed; add query_values for parameterized query assets
- 'Open URL'             → URL asset parts (ibm_url_definition type); no consumer input needed
- 'Download'             → file download; no consumer input needed
- 'Download Data Extract'→ format only (ask the user: avro, csv, delimited, excel, json, parquet, orc, sav, xml).
    No target connection needed — the API writes to the catalog-level default output connection automatically.
- 'Watsonx.data-ingest'  → wxd_catalog/schema/table + target_connection_id + source_connection_id (pre-existing CAMS connections)
    Ask the user only for: storage connection NAME, watsonx.data connector (connection) NAME, catalog, schema, table.
    Then call `search_connection` for each name to get the connection ID and its container_id
    (use these for the *_connection_id, *_connection_container_id and *_connection_container_type fields). Never ask the user for IDs.
    Always search in the catalog that holds the data product: call `search_connection` with
    container=<parts_out[].asset.container.id from get_data_product_details>, container_type='catalog',
    connection_name=<name>. The name filter requires container + container_type, and the same name can
    exist in other catalogs — only use the connection from the data product's catalog.

**NOT SUPPORTED via this tool (require raw credentials — unsafe in chat):**
'WatsonxData-DirectAccess', 'Snowflake-DirectAccess', 'Azure-Databricks-DirectAccess',
'AWS-Databricks-DirectAccess', 'AWS-Glue-Catalog-DirectAccess'
→ Direct the user to subscribe via the IBM Data Product Hub UI for these delivery methods.

**IMPORTANT — response state mapping:**
After a state='submitted' request, the server returns state='received' — this is correct, not an error.
After a state='draft' request, the server returns state='draft'.

Returns: subscription_id (save this for add_items / submit / remove_item tools), state, and subscription metadata.
""",
    tags={"create", "data_product", "subscriptions"},
    meta={"version": "1.0", "service": "data_product"},
    annotations={
        "title": "Create a Data Product Subscription",
        "destructiveHint": False,
    },
)
@auto_context
async def create_data_product_subscription(  # noqa: PLR0913 # Baseline
    data_product_version_id: Annotated[
        str,
        Field(
            description=(
                "UUID of the data product version to subscribe to. "
                "From get_data_product_details: use the part BEFORE '@' in the top-level id field, "
                "e.g. '2b0bf220-079c-11ee-be56-0242ac120002'."
            )
        ),
    ],
    state: Annotated[
        Literal["submitted", "draft"],
        Field(
            description=(
                "'submitted' — finalize immediately (all parts must have items). "
                "'draft' — create empty/partial subscription; use add_items + submit to complete. "
                "Use 'draft' when parts have different delivery method types."
            )
        ),
    ] = "submitted",
    items: Annotated[
        list[SubscriptionItem] | None,
        Field(
            description=(
                "List of typed subscription items, one per data product part. "
                "Set delivery_method_name to select the item type and its required fields. "
                "Required for state='submitted'. Optional for state='draft'."
            )
        ),
    ] = None,
    name: Annotated[
        str | None,
        Field(description="Subscription name (max 256 chars)."),
    ] = None,
    description: Annotated[
        str | None,
        Field(description="Subscription description (max 4000 chars)."),
    ] = None,
    business_justification: Annotated[
        str | None,
        Field(description="Business justification for requesting access (max 5000 chars)."),
    ] = None,
) -> CreateDataProductSubscriptionResponse:
    """Wrapper that expands individual parameters into CreateDataProductSubscriptionRequest."""

    request = CreateDataProductSubscriptionRequest(
        data_product_version_id=data_product_version_id,
        state=state,
        items=items,
        name=name,
        description=description,
        business_justification=business_justification,
    )
    return await _create_data_product_subscription(request)

# Made with Bob
