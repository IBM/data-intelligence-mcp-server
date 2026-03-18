# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""
Central constants for all services.
All service-specific endpoints and IDs live here.
"""

# ---- Search Endpoints ----
SEARCH_PATH = "/v3/search"

# ---- service/tools specific endpoints go here ----
PROJECTS_BASE_ENDPOINT = "/v2/projects"
CONNECTIONS_BASE_ENDPOINT = "/v2/connections"
CAMS_ASSETS_BASE_ENDPOINT = "/v2/assets"
DATA_PRODUCT_ENDPOINT = "/data_product_exchange/v1/data_products"
GS_BASE_ENDPOINT = "/v3/search"
GLOSSARY_API_ENDPOINT = "/v3/glossary_terms/api"
DATA_QUALITY_BASE_ENDPOINT = "/data_quality/v4"
DATA_QUALITY_BASE_ENDPOINT_V3 = "/data_quality/v3"
LINEAGE_BASE_ENDPOINT = "/gov_lineage/v2"
LINEAGE_UI_BASE_ENDPOINT = "/lineage"
TEXT_TO_SQL_BASE_ENDPOINT = "/semantic_automation/v1/text_to_sql"
GET_SCHEMA = "/semantic_automation/v1/get_schema_assets"
TEXT_TO_QUERY_BASE_ENDPOINT = "/semantic_automation/v1/generate_queries"
GEN_AI_ONBOARD_API = "/semantic_automation/v1/gen_ai/onboard"
GEN_AI_SETTINGS_BASE_ENDPOINT = "/semantic_automation/v1/gen_ai_settings"
JOBS_BASE_ENDPOINT = "/v2/jobs"
CATALOGS_BASE_ENDPOINT = "/v2/catalogs"
SPACES_BASE_ENDPOINT = "/v2/spaces"
ASSET_TYPE_BASE_ENDPOINT = "/v2/asset_types"
DATASOURCE_TYPES_BASE_ENDPOINT = "/v2/datasource_types"
USER_PROFILES_BASE_ENDPOINT = "/v2/user_profiles"
REPORTING_BASE_ENDPOINT = "/v3/reporting"
METADATA_IMPORT_BASE_ENDPOINT = "/v2/metadata_imports"
GROUPS_BASE_ENDPOINT = "/v2/groups"

DPR_RULES = "/v3/enforcement/rules"
DP_TRANSFORM = "/v4/enforcement-transform"

WORKFLOW_BASE_ENDPOINT = "/v3/workflows"
WORKFLOW_TASK_ENDPOINT = "/v3/workflow_user_tasks"

GLOSSARY_DATA_CLASS_ENDPOINT = "/v3/data_classes"
GLOSSARY_BUSINESS_TERMS_ENDPOINT = "/v3/glossary_terms"
GLOSSARY_ARTIFACT_TYPES_ENDPOINT = "/v3/governance_artifact_types"
GLOSSARY_DATA_CLASS = "data_class"
GLOSSARY_BUSINESS_TERM = "glossary_term"

CLOUD_IAM_ENDPOINT = "/identity/token"
CPD_IAM_ENDPOINT = "/icp4d-api/v1/authorize"

JSON_CONTENT_TYPE = "application/json"
JSON_PATCH_CONTENT_TYPE = "application/json-patch+json"
JSON_PLUS_UTF8_ACCEPT_TYPE = "application/json;charset=utf-8"
EN_LANGUAGE_ACCEPT_TYPE = "en-US"
AUTH_SCOPE_ALL_STR = "all"
FIELD_PREFERENCES = "fields,preferences"
