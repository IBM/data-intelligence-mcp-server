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