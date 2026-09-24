# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import re
from datetime import datetime, timezone
from typing import Annotated, Optional
from pydantic import Field
from app.core.registry import service_registry
from app.services.data_protection_rules.models.get_policy_metrics import (
    GetPolicyMetricsRequest,
    GetPolicyMetricsResponse,
    PolicyMetric,
    PolicyMetricsType,
    PolicyMetricsAggregationType,
    PolicyMetricsSortOrder,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.services.constants import DPS_POLICY_METRICS_ENDPOINT
from app.shared.utils.tool_helper_service import tool_helper_service

# DPS API requires: yyyy-MM-dd'T'HH:mm:ss.SSSX  (milliseconds mandatory)
_DPS_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def normalize_dps_timestamp(value: str, end_of_period: bool = False) -> str:
    """Normalize a user-supplied date/time string to the format required by the
    DPS policy metrics API: ``yyyy-MM-dd'T'HH:mm:ss.SSSZ``.

    Accepted input patterns (all interpreted as UTC):
    - Year only:              ``"2026"``            → start: ``2026-01-01T00:00:00.000Z``
                                                      end:   ``2026-12-31T23:59:59.999Z``
    - Year-month:             ``"2026-06"``          → start: ``2026-06-01T00:00:00.000Z``
                                                      end:   ``2026-06-30T23:59:59.999Z``
    - Date only:              ``"2026-01-01"``       → start: ``2026-01-01T00:00:00.000Z``
                                                      end:   ``2026-01-01T23:59:59.999Z``
    - ISO without millis + Z: ``"2026-01-01T00:00:00Z"``   → ``2026-01-01T00:00:00.000Z``
    - ISO without millis + offset: ``"2026-01-01T00:00:00+00:00"``
    - ISO with millis + Z:    ``"2026-01-01T00:00:00.000Z"`` (already valid, returned as-is)

    Args:
        value:          The user-supplied date/time string.
        end_of_period:  When True and the input has no time component, set the
                        time to 23:59:59.999 instead of 00:00:00.000.

    Returns:
        A date/time string in the format ``2026-01-01T00:00:00.000Z``.

    Raises:
        ValueError: If the input cannot be parsed into a recognized format.
    """
    value = value.strip()

    # Already fully valid: yyyy-MM-ddTHH:mm:ss.mmmZ
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", value):
        # Normalize milliseconds to exactly 3 digits
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _to_dps_format(dt)

    # ISO with offset but no millis: 2026-01-01T00:00:00Z or 2026-01-01T00:00:00+00:00
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:?\d{2})", value):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _to_dps_format(dt)

    # ISO with millis and offset: 2026-01-01T00:00:00.000+00:00
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[+-]\d{2}:?\d{2}", value):
        dt = datetime.fromisoformat(value)
        return _to_dps_format(dt.astimezone(timezone.utc))

    # Date only: 2026-01-01
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        dt = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        return _to_dps_format(_apply_end_of_period_date(dt, end_of_period))

    # Year-month only: 2026-06
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return _to_dps_format(_build_year_month_dt(value, end_of_period))

    # Year only: 2026
    if re.fullmatch(r"\d{4}", value):
        return _to_dps_format(_build_year_dt(int(value), end_of_period))

    raise ValueError(
        f"Cannot parse date/time value '{value}'. "
        "Expected formats: '2026', '2026-06', '2026-01-01', "
        "'2026-01-01T00:00:00Z', or '2026-01-01T00:00:00.000Z'."
    )


def _apply_end_of_period_date(dt: datetime, end_of_period: bool) -> datetime:
    """Return dt unchanged, or with time set to 23:59:59.999 when end_of_period is True."""
    if end_of_period:
        return dt.replace(hour=23, minute=59, second=59, microsecond=999000)
    return dt


def _build_year_month_dt(value: str, end_of_period: bool) -> datetime:
    """Build a UTC datetime for a year-month string (e.g. '2026-06')."""
    import calendar
    year, month = int(value[:4]), int(value[5:7])
    if end_of_period:
        last_day = calendar.monthrange(year, month)[1]
        return datetime(year, month, last_day, 23, 59, 59, 999000, tzinfo=timezone.utc)
    return datetime(year, month, 1, 0, 0, 0, 0, tzinfo=timezone.utc)


def _build_year_dt(year: int, end_of_period: bool) -> datetime:
    """Build a UTC datetime for a year integer."""
    if end_of_period:
        return datetime(year, 12, 31, 23, 59, 59, 999000, tzinfo=timezone.utc)
    return datetime(year, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)


def _to_dps_format(dt: datetime) -> str:
    """Format a datetime as ``yyyy-MM-ddTHH:mm:ss.mmmZ`` (always UTC, 3-digit millis)."""
    utc_dt = dt.astimezone(timezone.utc)
    millis = utc_dt.microsecond // 1000
    return utc_dt.strftime(f"%Y-%m-%dT%H:%M:%S.{millis:03d}Z")


def _add_optional_params(params: dict, request: GetPolicyMetricsRequest) -> None:
    """Populate optional filter params into the query dict, omitting None values."""
    optional_str_fields = [
        ("policy_id", request.policy_id),
        ("rule_id", request.rule_id),
        ("user", request.user),
        ("governance_type", request.governance_type),
        ("outcome", request.outcome),
        ("pep_host_type", request.pep_host_type),
        ("context_operation", request.context_operation),
        ("context_location", request.context_location),
        ("asset_type", request.asset_type),
        ("asset_location", request.asset_location),
    ]
    for key, val in optional_str_fields:
        if val is not None:
            params[key] = val
    if request.is_pep_cache is not None:
        params["is_pep_cache"] = str(request.is_pep_cache).lower()
    if request.sort is not None:
        params["sort"] = request.sort.value



async def _get_policy_metrics(
    request: GetPolicyMetricsRequest,
) -> GetPolicyMetricsResponse:
    # Normalize user-supplied timestamps to the format the DPS API requires
    # (yyyy-MM-dd'T'HH:mm:ss.SSSZ).  This handles natural inputs like "2026",
    # "2026-01", "2026-01-01", or ISO strings without milliseconds.
    try:
        start_time = normalize_dps_timestamp(request.start_time, end_of_period=False)
        end_time = normalize_dps_timestamp(request.end_time, end_of_period=True)
    except ValueError as e:
        raise ServiceError(str(e)) from e

    LOGGER.info(
        f"In the get_policy_metrics tool, querying '{request.metrics_type.value}' metrics "
        f"aggregated by '{request.aggregation_type.value}' "
        f"from {start_time} to {end_time}."
    )

    params: dict = {
        "metrics_type": request.metrics_type.value,
        "aggregation_type": request.aggregation_type.value,
        "start_time": start_time,
        "end_time": end_time,
    }
    _add_optional_params(params, request)

    try:
        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}{DPS_POLICY_METRICS_ENDPOINT}",
            params=params,
            tool_name="get_policy_metrics",
        )
    except ExternalAPIError:
        raise
    except Exception as e:
        raise ServiceError(
            f"Failed to retrieve policy metrics: {str(e)}",
            service="data_protection_rules",
            tool="get_policy_metrics",
        ) from e

    # Response shape: { "entity": { "metrics": [ { "aggregate": str, "count": int } ] } }
    entity = response.get("entity", {})
    metrics_list = entity.get("metrics", [])

    if not metrics_list:
        LOGGER.info("In the get_policy_metrics tool, no policy metrics found.")
        return GetPolicyMetricsResponse(count=0, metrics=[])

    LOGGER.info(f"Found {len(metrics_list)} policy metric records.")
    metrics = [
        PolicyMetric(
            aggregate=item.get("aggregate", ""),
            count=item.get("count", 0),
        )
        for item in metrics_list
    ]

    return GetPolicyMetricsResponse(count=len(metrics), metrics=metrics)


@service_registry.tool(
    name="get_policy_metrics",
    annotations={
        "readOnlyHint": True,
        "title": "Get DPS Policy Enforcement Metrics for a Time Period",
    },
    description="""
    Use this tool to retrieve and aggregate DPS (Data Privacy and Security) policy
    enforcement metrics for a specified time period.
    You must specify what type of metrics to retrieve (metrics_type) and how to aggregate
    them (aggregation_type). Optional filters let you scope the results to a specific
    policy, rule, user, governance type, outcome, or other dimensions.
    Example: 'Show me enforcement counts grouped by policy for 2024'
    In this case metrics_type is 'enforcements' and aggregation_type is 'policies'.
    Returns: A list of metric records, each containing an aggregate dimension value and
    its corresponding enforcement count, plus the total number of records returned.
    """,
    tags={"data_protection_rules", "metrics","metadata_management_and_governance"},
    meta={"version": "1.0", "service": "data_protection_rules"},
)
@auto_context
async def get_policy_metrics(
    metrics_type: Annotated[
        PolicyMetricsType,
        Field(
            description=(
                "The type of metrics to return. One of: "
                "'enforcements', 'denials', 'operational_policies', 'operational_rules'."
            )
        ),
    ],
    aggregation_type: Annotated[
        PolicyMetricsAggregationType,
        Field(
            description=(
                "The dimension to aggregate metrics by. One of: "
                "'days', 'months', 'years', 'policies', 'rules', 'users', 'outcomes', "
                "'governance_type', 'pep_host_types', 'is_pep_cache', 'context_operations', "
                "'context_locations', 'asset_types', 'asset_locations'."
            )
        ),
    ],
    start_time: Annotated[
        str,
        Field(
            description=(
                "ISO 8601 start of the time range (e.g. '2024-01-01T00:00:00Z')."
            )
        ),
    ],
    end_time: Annotated[
        str,
        Field(
            description=(
                "ISO 8601 end of the time range (e.g. '2024-12-31T23:59:59Z')."
            )
        ),
    ],
    policy_id: Annotated[
        Optional[str],
        Field(default=None, description="Filter to a specific policy ID, or omit for all."),
    ] = None,
    rule_id: Annotated[
        Optional[str],
        Field(default=None, description="Filter to a specific rule ID, or omit for all."),
    ] = None,
    user: Annotated[
        Optional[str],
        Field(default=None, description="Filter to a specific user, or omit for all."),
    ] = None,
    governance_type: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Filter to a specific governance type (e.g. 'Access'), or omit for all.",
        ),
    ] = None,
    outcome: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Filter to a specific outcome (e.g. 'Allow', 'Deny'), or omit for all.",
        ),
    ] = None,
    pep_host_type: Annotated[
        Optional[str],
        Field(default=None, description="Filter to a specific PEP host type, or omit for all."),
    ] = None,
    is_pep_cache: Annotated[
        Optional[bool],
        Field(
            default=None,
            description="Filter to cache decisions (True) or server decisions (False), or omit for both.",
        ),
    ] = None,
    context_operation: Annotated[
        Optional[str],
        Field(default=None, description="Filter to a specific context operation, or omit for all."),
    ] = None,
    sort: Annotated[
        Optional[PolicyMetricsSortOrder],
        Field(
            default=None,
            description=(
                "Comma-separated sort fields (e.g., 'created_at,-last_updated_at'). Prefix with '-' for descending."
            ),
        ),
    ] = None,
) -> GetPolicyMetricsResponse:
    """Wrapper that builds a GetPolicyMetricsRequest and delegates to the internal function."""
    request = GetPolicyMetricsRequest(
        metrics_type=metrics_type,
        aggregation_type=aggregation_type,
        start_time=start_time,
        end_time=end_time,
        policy_id=policy_id,
        rule_id=rule_id,
        user=user,
        governance_type=governance_type,
        outcome=outcome,
        pep_host_type=pep_host_type,
        is_pep_cache=is_pep_cache,
        context_operation=context_operation,
        sort=sort,
    )
    return await _get_policy_metrics(request)
