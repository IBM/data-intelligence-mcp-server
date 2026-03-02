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
Constants for data product service.
Contains API field names, property keys, and other string literals used across data product tools.
"""

# ---- Asset Types ----
ASSET_TYPE_IBM_URL_DEFINITION = "ibm_url_definition"
ASSET_TYPE_DATA_ASSET = "data_asset"

# ---- API Response Fields ----
# Common fields
FIELD_ASSET = "asset"
FIELD_TYPE = "type"
FIELD_ID = "id"
FIELD_NAME = "name"
FIELD_DESCRIPTION = "description"
FIELD_METADATA = "metadata"
FIELD_ENTITY = "entity"
FIELD_STATE = "state"
FIELD_VERSION = "version"
FIELD_ITEMS = "items"

# Asset-related fields
FIELD_ASSET_ID = "asset_id"
FIELD_PROPERTIES = "properties"
FIELD_OUTPUT = "output"
FIELD_ASSETS_OUT = "assets_out"
FIELD_PARTS_OUT = "parts_out"

# URL-related fields
FIELD_OPEN_URL = "Open URL"
FIELD_VALUE = "value"

# Data asset fields
FIELD_DATA_ASSET = "data_asset"
FIELD_COLUMNS = "columns"
FIELD_COLUMN_INFO = "column_info"
FIELD_KEY_ANALYSES = "key_analyses"
FIELD_PRIMARY_KEYS = "primary_keys"

# ---- Column Schema Fields ----
FIELD_DATA_TYPE = "data_type"
FIELD_LENGTH = "length"
FIELD_NULLABLE = "nullable"
FIELD_NATIVE_TYPE = "native_type"
FIELD_IS_PRIMARY_KEY = "is_primary_key"

# ---- Column Metadata Fields ----
# Data classification
FIELD_SELECTED_DATA_CLASS = "selected_data_class"
FIELD_DATA_CLASS_NAME = "data_class_name"
FIELD_DATA_CLASS_CONFIDENCE = "data_class_confidence"
FIELD_CONFIDENCE = "confidence"

# Semantic naming
FIELD_SEMANTIC_NAME = "semantic_name"
FIELD_SEMANTIC_NAME_CONFIDENCE = "semantic_name_confidence"
FIELD_SEMANTIC_NAME_STATUS = "semantic_name_status"
FIELD_STATUS = "status"

# Descriptions
FIELD_COLUMN_DESCRIPTION = "column_description"
FIELD_SEMANTIC_DESCRIPTION = "semantic_description"
FIELD_SEMANTIC_DESCRIPTION_CONFIDENCE = "semantic_description_confidence"
FIELD_SEMANTIC_DESCRIPTION_STATUS = "semantic_description_status"

# ---- Subscription Fields ----
FIELD_ASSET_LISTS = "asset_lists"
FIELD_FLIGHT_ASSET_ID = "flight_asset_id"
FIELD_URL = "url"

# ---- API Query Parameters ----
PARAM_CATALOG_ID = "catalog_id"
PARAM_LIMIT = "limit"
PARAM_QUERY = "query"

# Field name for catalog_id (used in dict keys)
FIELD_CATALOG_ID = "catalog_id"
FIELD_TYPE = "type"

# ---- Data Product States ----
STATE_SUCCEEDED = "succeeded"
STATE_AVAILABLE = "available"