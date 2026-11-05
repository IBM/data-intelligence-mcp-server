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

"""
Typed subscription item models — one per supported delivery method shape.

These are shared between create_data_product_subscription and
add_items_to_data_product_subscription. The discriminator field
`delivery_method_name` drives which set of parameters the LLM
must supply, giving full type safety without a generic Dict.

SUPPORTED delivery methods (safe for agent — no raw credentials required):
  "Use Flight service"   — IBM Flight service query access; no consumer_input (NoConsumerInputItem)
  "Open URL"             — URL asset (ibm_url_definition); no consumer_input (NoConsumerInputItem)
  "Download"             — File download; no consumer_input (NoConsumerInputItem)
  "Download Data Extract"— CSV extract via pre-existing target CAMS connection (DataExtractItem)
  "Watsonx.data-ingest"  — WxD ingest via pre-existing CAMS connection IDs (WxdIngestItem)

NOT SUPPORTED via agent (require raw credentials inline — unsafe in chat):
  "WatsonxData-DirectAccess"      — needs api_key or username+password inline
  "Snowflake-DirectAccess"        — needs account credentials inline
  "Azure-Databricks-DirectAccess" — needs Entra ID token or client secret inline
  "AWS-Databricks-DirectAccess"   — needs PAT token or username+password inline
  "AWS-Glue-Catalog-DirectAccess" — needs AWS access_key_id + secret_access_key inline

  For unsupported delivery methods, instruct the user to subscribe via the
  IBM Data Product Hub UI where credentials are handled securely.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 1. No consumer_input delivery methods
#    Use for:
#      "Use Flight service"  — IBM Flight service query access
#      "Open URL"            — URL asset (ibm_url_definition); no connection needed
#      "Download"            — File download from data asset
#    These three share the same shape: no consumer credentials or connection
#    details required. The `query_values` field covers parameterized query
#    assets — add it when get_data_product_details shows the part is a
#    parameterized query asset.
# ---------------------------------------------------------------------------

class QueryValue(BaseModel):
    """A single parameter value for a parameterized query asset."""
    name: str = Field(description="Parameter name (without # delimiters, e.g. 'CITY')")
    type: str = Field(description="Parameter type: string | int64 | sfloat | timestamp | time | path")
    value: str = Field(description="Parameter value as a string (e.g. 'chicago', '26884.62')")


class NoConsumerInputItem(BaseModel):
    """
    Subscription item for delivery methods that need no consumer connection
    or credentials: 'Use Flight service', 'Open URL', and 'Download'.

    Use 'Open URL' for URL asset parts (ibm_url_definition type) — these have
    no underlying database connection. list_data_product_delivery_methods
    automatically returns 'Open URL' for such parts.

    Use 'Use Flight service' for IBM Flight service / standard data asset access.

    Use 'Download' for file-download delivery.

    The optional query_values field is only needed when the part is a
    parameterized query asset (get_data_product_details will show query
    parameters in the asset).
    """
    delivery_method_name: Literal["Use Flight service", "Open URL", "Download"] = Field(
        description=(
            "Must be one of: 'Use Flight service' (IBM Flight service — data asset access), "
            "'Open URL' (URL assets — ibm_url_definition type), "
            "'Download' (file download). "
            "Use 'Open URL' when the data product part is a URL asset."
        )
    )
    data_product_part_id: str = Field(
        description="UUID of the data product part (from get_data_product_details parts_out[].asset.id)."
    )
    delivery_method_id: str = Field(
        description="UUID of the delivery method asset (from list_data_product_delivery_methods)."
    )
    query_values: list[QueryValue] | None = Field(
        default=None,
        description=(
            "Required only when the data product part is a parameterized query asset. "
            "Each entry maps a named parameter (e.g. CITY) to a typed value. "
            "Leave None for non-parameterized assets and for URL assets."
        ),
    )


# ---------------------------------------------------------------------------
# 2. Download Data Extract (CSV)
#    Delivery method name: "Download Data Extract"
#    Requires: format + a pre-existing CAMS connection ID as the output target.
#    No raw credentials — the connection asset already holds them securely.
# ---------------------------------------------------------------------------

# Supported output formats for the 'Download Data Extract' delivery method.
# These map 1-to-1 to DataExtractFormatEnum in the Java API.
DataExtractFormat = Literal[
    "avro",
    "csv",
    "delimited",
    "excel",
    "json",
    "parquet",
    "orc",
    "sav",
    "xml",
]


class DataExtractItem(BaseModel):
    """
    Subscription item for the 'Download Data Extract' delivery method.
    The server writes the extracted data to the catalog-level default output connection
    configured by the DPH admin — no target connection is required from the consumer.
    """
    delivery_method_name: Literal["Download Data Extract"] = Field(
        description="Must be 'Download Data Extract' to select this item type."
    )
    data_product_part_id: str = Field(
        description="UUID of the data product part."
    )
    delivery_method_id: str = Field(
        description="UUID of the delivery method asset."
    )
    format: DataExtractFormat = Field(
        description=(
            "Output format for the extracted data. "
            "Supported values: 'avro', 'csv', 'delimited', 'excel', 'json', 'parquet', 'orc', 'sav', 'xml'. "
            "Always ask the user which format they want."
        ),
    )
    query_values: list[QueryValue] | None = Field(
        default=None,
        description="Parameterized query values. Required only when the part is a parameterized query asset.",
    )


# ---------------------------------------------------------------------------
# 3. Watsonx.data Ingest
#    Delivery method name: "Watsonx.data-ingest"
#    Requires: destination catalog/schema/table + two pre-existing CAMS connection IDs.
#    Server calls PUT /v2/connections/{id}/actions/test on both connections
#    to validate they work — no raw credentials are passed by the consumer.
# ---------------------------------------------------------------------------

class WxdIngestItem(BaseModel):
    """
    Subscription item for the 'Watsonx.data-ingest' delivery method.
    Data is ingested into the consumer's watsonx.data lakehouse table.

    Both target_connection and source_connection must be pre-existing CAMS
    connection assets — the consumer supplies their IDs only, not raw credentials.
    The server tests both connections live before accepting the subscription.

    What to ask the user (the same fields the Data Product Hub UI asks for):
      - Storage connection name        → source_connection_id (+ container id)
      - Watsonx.data connector name    → target_connection_id (+ container id)
      - Catalog name, schema name, table name

    Do NOT ask the user for connection IDs or container IDs. Resolve the two
    connection names with search_connection, which returns each connection's
    asset id and its container_id (catalog or project). Always search within the
    catalog that holds the data product part (parts_out[].asset.container.id from
    get_data_product_details): call search_connection with container=<that id>,
    container_type='catalog', connection_name=<name>. The same connection name can
    exist in several catalogs; only use the one in the data product's catalog.
    """
    delivery_method_name: Literal["Watsonx.data-ingest"] = Field(
        description="Must be 'Watsonx.data-ingest' to select this item type."
    )
    data_product_part_id: str = Field(description="UUID of the data product part.")
    delivery_method_id: str = Field(description="UUID of the delivery method asset.")
    wxd_catalog: str = Field(description="Target watsonx.data catalog name (e.g. 'iceberg_data').")
    wxd_schema: str = Field(description="Target schema name within the watsonx.data catalog.")
    wxd_table: str = Field(description="Target table name to ingest data into.")
    target_connection_id: str = Field(
        description=(
            "UUID of the consumer's pre-existing CAMS connection asset pointing to their "
            "watsonx.data instance (the 'Watsonx.data Connector' in the UI). Resolve it from the "
            "connection name the user gives via search_connection; do not ask the user for the ID. "
            "Server will test this connection — must be valid."
        )
    )
    target_connection_container_id: str = Field(
        description=(
            "UUID of the catalog or project that owns the target (WxD) connection. "
            "Taken from the container_id returned by search_connection; do not ask the user for it."
        )
    )
    target_connection_container_type: Literal["catalog", "project"] = Field(
        default="catalog",
        description=(
            "Type of the container that owns the target (WxD) connection. "
            "Taken from the container_type returned by search_connection."
        ),
    )
    source_connection_id: str = Field(
        description=(
            "UUID of the consumer's pre-existing CAMS connection asset pointing to the "
            "data-extract storage bucket, e.g. COS/S3 (the 'Storage connection' in the UI). "
            "Resolve it from the connection name the user gives via search_connection; do not ask "
            "the user for the ID. Server will test this — must be valid."
        )
    )
    source_connection_container_id: str = Field(
        description=(
            "UUID of the catalog or project that owns the source (storage) connection. "
            "Taken from the container_id returned by search_connection; do not ask the user for it."
        )
    )
    source_connection_container_type: Literal["catalog", "project"] = Field(
        default="catalog",
        description=(
            "Type of the container that owns the source (storage) connection. "
            "Taken from the container_type returned by search_connection."
        ),
    )
    query_values: list[QueryValue] | None = Field(
        default=None,
        description="Parameterized query values. Required only when the part is a parameterized query asset.",
    )


# ---------------------------------------------------------------------------
# Discriminated union — the single type used by both create and add_items tools.
# Only the 3 safe delivery method shapes are included here.
# ---------------------------------------------------------------------------

SubscriptionItem = Annotated[
    NoConsumerInputItem | DataExtractItem | WxdIngestItem,
    Field(discriminator="delivery_method_name"),
]

# Made with Bob
