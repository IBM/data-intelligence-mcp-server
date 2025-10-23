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
GS_BASE_ENDPOINT = "/v3/search"
DATA_QUALITY_BASE_ENDPOINT = "/data_quality/v4"
LINEAGE_BASE_ENDPOINT = "/gov_lineage/v2"
LINEAGE_UI_BASE_ENDPOINT = "/lineage"
TEXT_TO_SQL_BASE_ENDPOINT = "/semantic_automation/v1/text_to_sql"
GEN_AI_ONBOARD_API = "/semantic_automation/v1/gen_ai/onboard"
GEN_AI_SETTINGS_BASE_ENDPOINT = "/semantic_automation/v1/gen_ai_settings"
JOBS_BASE_ENDPOINT = "/v2/jobs"

DPR_RULES = "/v3/enforcement/rules"

CLOUD_IAM_ENDPOINT = "/identity/token"
CPD_IAM_ENDPOINT = "/icp4d-api/v1/authorize"

JSON_CONTENT_TYPE = "application/json"
JSON_PATCH_CONTENT_TYPE = "application/json-patch+json"
