# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Constants for glossary service."""

from enum import StrEnum
from typing import TypeAlias, Optional

Elicitable: TypeAlias = Optional[str]
ELICIT_PLACEHOLDER = "default_value_for_elicitation"
NOT_SPECIFIED_PLACEHOLDER = "default_value_for_placeholder"


class ContainerType(StrEnum):
    CATALOG = "catalog"
    PROJECT = "project"
    SPACE = "space"
    ALL = "all"
    CATALOG_AND_PROJECT = "catalog,project"


class ArtifactType(StrEnum):
    DATA_ASSET = "data_asset"
    CONNECTION = "connection"
    DATA_SOURCE = "ibm_data_source"
    GLOSSARY_TERM = "glossary_term"
    DATA_ASSET_COLUMN = "data_asset_column"
    DATA_RULE = "data_rule"
    DATA_RULE_DEFINITION = "data_rule_definition"
    CATEGORY = "category"
    CLASSIFICATION = "classification"


METADATA_NAME = "metadata.name"

ARTIFACT_TYPE_MAPPING = {
    "classification": "classifications",
    "data_class": "data_classes",
    "glossary_term": "glossary_terms",
    "policy": "policies",
    "rule": "rules",
    "category": "categories",
    "reference_data_set": "reference_data_sets",
}

UNUSED_KEYS = {
    "last_updated_at",
    "modified_on",
    "created_on",
    "updated_on",
    "tenant_id",
    "state",
    "enabled",
    "provider_type_id",
    "_score",
    "steward_ids",
    "steward_group_ids",
}

ERROR_CODE_INVALID_HEADER = "GIM00013E"
ERROR_CODE_INVALID_ARTIFACT_TYPE = "GIM00006E"
ERROR_CODE_MISSING_CATEGORY = "GIM00010E"

IMPORT_STATUS_SUCCEEDED = "SUCCEEDED"
IMPORT_STATUS_FAILED = "FAILED"
IMPORT_STATUS_COMPLETED = "COMPLETED"
IMPORT_STATUS_ERROR = "ERROR"
IMPORT_STATUS_TIMEOUT = "TIMEOUT"
IMPORT_STATUS_UNKNOWN = "UNKNOWN"

IMPORT_COMPLETION_STATUSES = [
    IMPORT_STATUS_SUCCEEDED,
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_COMPLETED,
    IMPORT_STATUS_ERROR,
]

# Import endpoints are now built dynamically per artifact type
# Format: /v3/governance_artifact_types/{artifact_type}/import
GLOSSARY_IMPORT_STATUS_ENDPOINT = "/v3/governance_artifact_types/import/status"

DEFAULT_POLL_MAX_WAIT_SECONDS = 45
DEFAULT_POLL_INTERVAL_SECONDS = 2.0
# Max wait time for newly imported categories to become searchable before importing terms
CATEGORY_PROPAGATION_DELAY_SECONDS = 30.0

CSV_FILENAME = "glossary_import.csv"
CSV_CONTENT_TYPE = "text/csv"

MERGE_OPTION_ALL = "all"
MERGE_OPTION_SPECIFIED = "specified"
MERGE_OPTION_EMPTY = "empty"

OPERATION_IMPORT_CREATE = "IMPORT_CREATE"
OPERATION_IMPORT_MODIFY = "IMPORT_MODIFY"

ARTIFACT_TYPE_GLOSSARY_TERM = "glossary_term"
ARTIFACT_TYPE_CATEGORY = "category"

CSV_COLUMN_ARTIFACT_TYPE = "Artifact Type"