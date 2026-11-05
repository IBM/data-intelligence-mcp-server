# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field  # noqa: I001 # Baseline
from app.shared.models import BaseResponseModel
from typing import Optional, List  # noqa: UP035 # Baseline
from enum import Enum


class PolicyMetricsType(str, Enum):  # noqa: UP042 # Baseline
    """The type of metrics to retrieve."""

    enforcements = "enforcements"
    denials = "denials"
    operational_policies = "operational_policies"
    operational_rules = "operational_rules"


class PolicyMetricsAggregationType(str, Enum):  # noqa: UP042 # Baseline
    """The dimension to aggregate metrics by."""

    days = "days"
    months = "months"
    years = "years"
    policies = "policies"
    rules = "rules"
    users = "users"
    outcomes = "outcomes"
    governance_type = "governance_type"
    pep_host_types = "pep_host_types"
    is_pep_cache = "is_pep_cache"
    context_operations = "context_operations"
    context_locations = "context_locations"
    asset_types = "asset_types"
    asset_locations = "asset_locations"


class PolicyMetricsSortOrder(str, Enum):  # noqa: UP042 # Baseline
    """The sort order for returned metrics."""

    aggregate_asc = "aggregate"
    aggregate_desc = "-aggregate"
    count_asc = "count"
    count_desc = "-count"


class GetPolicyMetricsRequest(BaseModel):
    metrics_type: PolicyMetricsType = Field(
        description=(
            "The type of metrics to return. One of: "
            "'enforcements', 'denials', 'operational_policies', 'operational_rules'."
        )
    )
    aggregation_type: PolicyMetricsAggregationType = Field(
        description=(
            "The dimension to aggregate metrics by. One of: "
            "'days', 'months', 'years', 'policies', 'rules', 'users', 'outcomes', "
            "'governance_type', 'pep_host_types', 'is_pep_cache', 'context_operations', "
            "'context_locations', 'asset_types', 'asset_locations'."
        )
    )
    start_time: str = Field(
        description=(
            "Start of the time range for metrics. Accepts: a year ('2026'), "
            "year-month ('2026-06'), date ('2026-01-01'), ISO 8601 without millis "
            "('2026-01-01T00:00:00Z'), or ISO 8601 with millis "
            "('2026-01-01T00:00:00.000Z'). All values are treated as UTC."
        )
    )
    end_time: str = Field(
        description=(
            "End of the time range for metrics. Accepts: a year ('2026'), "
            "year-month ('2026-06'), date ('2026-12-31'), ISO 8601 without millis "
            "('2026-12-31T23:59:59Z'), or ISO 8601 with millis "
            "('2026-12-31T23:59:59.999Z'). All values are treated as UTC."
        )
    )
    policy_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific policy ID, or omit to include all policies.",
    )
    rule_id: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific rule ID, or omit to include all rules.",
    )
    user: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific user, or omit to include all users.",
    )
    governance_type: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "Filter metrics to a specific governance type (e.g. 'Access', 'Classification'), "
            "or omit to include all governance types."
        ),
    )
    outcome: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "Filter metrics to a specific enforcement outcome (e.g. 'Allow', 'Deny'), "
            "or omit to include all outcomes."
        ),
    )
    pep_host_type: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific PEP host type, or omit for all.",
    )
    is_pep_cache: Optional[bool] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "Filter metrics to decisions retrieved from cache (True) or from server (False), "
            "or omit for both."
        ),
    )
    context_operation: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific context operation, or omit for all.",
    )
    context_location: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific context location, or omit for all.",
    )
    asset_type: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific asset type, or omit for all.",
    )
    asset_location: Optional[str] = Field(  # noqa: UP045 # Baseline
        default=None,
        description="Filter metrics to a specific asset location, or omit for all.",
    )
    sort: Optional[PolicyMetricsSortOrder] = Field(  # noqa: UP045 # Baseline
        default=None,
        description=(
            "Sort order for returned metrics. One of: "
            "'aggregate' (asc), '-aggregate' (desc), 'count' (asc), '-count' (desc)."
        ),
    )


class PolicyMetric(BaseModel):
    """A single aggregated metric record returned by the policy metrics API."""

    aggregate: str = Field(
        description=(
            "The aggregated dimension value (e.g. a date string for days/months/years, "
            "a policy ID for policies, a user ID for users, an outcome name, etc.)."
        )
    )
    count: int = Field(
        description="The enforcement event count for this aggregate value over the requested time range."
    )


class GetPolicyMetricsResponse(BaseResponseModel):
    count: int = Field(description="The number of metric records returned.")
    metrics: List[PolicyMetric] = Field(  # noqa: UP006 # Baseline
        default_factory=list,
        description="List of aggregated policy metric records.",
    )
