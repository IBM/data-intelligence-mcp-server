# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import re

from difflib import get_close_matches
from typing import Any, Dict, List, Optional

from app.services.lineage.models.lineage_asset import LineageAsset, QualityScore
from app.services.lineage.models.search_lineage_assets import (
    SearchLineageAssetsRequest,
    SearchLineageAssetsResponse,
    SENTINEL_NO_QUALITY_VALUE,
)

from app.core.registry import service_registry
from app.services.constants import LINEAGE_BASE_ENDPOINT
from app.services.stubs import caller_context, trigger_interrupt_with_ui
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.helpers import verify_dates
from app.shared.ui_message.ui_message_context import ui_message_context


def _has_quality_value(value: Optional[float]) -> bool:
    """
    Check if a data quality value was explicitly provided by the user.
    
    Args:
        value: The data quality value to check
        
    Returns:
        bool: True if a valid quality value was provided, False if it's the sentinel value
    """
    return value is not None and value != SENTINEL_NO_QUALITY_VALUE


def _check_input_parameters(
    name_query,
    is_operational,
    tag,
    data_quality_operator,
    data_quality_value,
    business_term,
    business_classification,
    technology_name,
    asset_type,
) -> bool:
    """
    Checks if at least one parameter is added and does an interrupt.
    Args:
        name_query (str): Search text for asset names - exact matches appear first, followed by partial matches
        is_operational (Optional[bool]): Filters assets based on whether the asset has asset type which belongs to the operational asset types.
        tag (Optional[str]): Filters assets by tags.
        data_quality_operator (Optional): a comparison operator for quality score (greater, lesser, or symbols like >, <, <=). The accepted values are:
            1) equals
            2) greater_than
            3) greater_than_or_equal
            4) less_than
            5) less_than_or_equal
        data_quality_value (Optional[float]): a numerical value assotiated with quality score.
        business_term (Optional[str]): Business term provided by the user.
        business_classification (Optional[str]): Business classification provided by the user.
        technology_name (str): Fill this optional value ONLY with the name of technology passed by the user.
        asset_type (str): Fill this optional value ONLY with the type of asset passed by the user.
    Returns:
        bool : true if user did not pass at least one parameter
    """
    if not _has_search_criteria(
        name_query,
        is_operational,
        tag,
        data_quality_operator,
        data_quality_value,
        business_term,
        business_classification,
        technology_name,
        asset_type,
    ):

        name_query = None
        name_query = trigger_interrupt_with_ui(
            "search_lineage_assets",
            "You have not provided anything to search for. Please provide the name of the asset you are searching for",
        )
        # Use regex to check if name_query is empty or contains only asterisks and whitespace
        return not name_query or re.match(r"^[*\s]*$", name_query) is not None

    return False


def _has_search_criteria(
    name_query: str = "*",
    is_operational: Optional[bool] = None,
    tag: Optional[str] = None,
    data_quality_operator: Optional[str] = None,
    data_quality_value: Optional[float] = None,
    business_term: Optional[str] = None,
    business_classification: Optional[str] = None,
    technology_name: str = "",
    asset_type: str = "",
) -> bool:
    """
    Check if at least one search criterion was provided by the user.
    
    This function determines whether the user has provided any meaningful search criteria
    beyond the defaults. It's used to prompt the user if they haven't specified what to search for.

    Args:
        name_query (str): Search text for asset names
        is_operational (Optional[bool]): Filters assets based on operational status
        tag (Optional[str]): Filters assets by tags
        data_quality_operator (Optional[str]): Comparison operator for quality score
        data_quality_value (Optional[float]): Numerical value for quality score
        business_term (Optional[str]): Business term filter
        business_classification (Optional[str]): Business classification filter
        technology_name (str): Technology name filter
        asset_type (str): Asset type filter

    Returns:
        bool: True if at least one search criterion is provided, False otherwise
    """
    # Check if name_query is different from default
    if name_query != "*":
        return True

    # Check if is_operational is different from default
    if is_operational is True:
        return True

    # Check if any of the optional parameters are not None
    if any(
        [
            tag is not None,
            data_quality_operator is not None,
            data_quality_value is not None,
            business_term is not None,
            business_classification is not None,
        ]
    ):
        return True

    # Check if any of the string parameters are not empty
    if any([technology_name != "", asset_type != ""]):
        return True

    # If we get here, all parameters are at their default values
    return False


def _create_asset_filter(name: str, values: list[str]):
    """
    Creates asset filter entry.

    Args:
        name (str): Name of the asset filter
        values (list[str]): List of values for the asset filter

    Returns:
        dict: Asset filter entry
    """
    return {"type": name, "values": values}


def _create_asset_filter_with_operator(name: str, values: list[str], operator: str):
    """
    Creates asset filter entry with operator.

    Args:
        name (str): Name of the asset filter
        values (list[str]): List of values for the asset filter
        operator (str): Operator for the asset filter

    Returns:
        dict: Asset filter entry
    """
    return {"type": name, "operator": operator, "values": values}


async def _call_search_lineage_assets(
    name_query: str,
    technology_names: list[str] | None,
    asset_types: list[str] | None,
    is_operational: list[bool] | None,
    tag: list[str] | None,
    data_quality: QualityScore | None,
    business_terms: list[str] | None,
    business_classifications: list[str] | None,
    dates: list[str] | None
) -> Dict[str, Any]:
    """
    This function returns search lineage assets response.

    Args:
        name_query (str): Search text for asset names - exact matches appear first, followed by partial matches
        technology_names (Optional[list[str]]): List of names of technologies.
        asset_types (Optional[list[str]]): List of types of assets.
        is_operational (Optional[list[bool]]): List with information if to filter assets based on whether the asset has asset type which belongs to the operational asset types.
        tag (Optional[list[str]]): List of tags.
        data_quality (Optional[QualityScore]): Quality score object.
        business_terms (Optional[list[str]]): List of business terms.
        business_classifications (Optional[list[str]]): List of business classifications.

    Returns:
        dict[str, Any]: Response from the lineage service.

    Raises:
        ExternalAPIError: If the call finishes unsuccessfully
    """
    filters = []
    if technology_names:
        filters.append(_create_asset_filter("technology_name", technology_names))
    if asset_types:
        filters.append(_create_asset_filter("asset_type", asset_types))
    if is_operational:
        filters.append(_create_asset_filter("is_operational", is_operational))
    if tag:
        filters.append(_create_asset_filter("tag", tag))
    if data_quality:
        filters.append(
            _create_asset_filter_with_operator(
                "data_quality_score", [data_quality.value], data_quality.operator
            )
        )
    if business_terms:
        filters.append(_create_asset_filter("business_term", business_terms))
    if business_classifications:
        filters.append(
            _create_asset_filter("business_classification", business_classifications)
        )
    payload = {
        "query": name_query,
        "filters": filters,
    }
    if dates:
        payload["lineage_version_datetimes"] = dates
    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url)
        + LINEAGE_BASE_ENDPOINT
        + "/search_lineage_assets",
        json=payload,
        tool_name="search_lineage_assets",
    )
    return response


async def _get_lineage_technology_type(technology_type: str, filters_not_found: Optional[List[str]]) -> str:
    """
    Find technology type for filtering search_lineage_asset.

    Searches for technology types using llm.

    Args:
        technology_type (str): The name of the technology type
        filters_not_found (Optional[List[str]]): List of filters that could not be used

    Returns:
        str: The mapped name of technology type.

    Raises:
        ServiceError: If technology type was not found
    """

    params = {
        "order": "-name",
        "offset": 0,
        "limit": 100,
    }
    technology_types_list = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + "/gov_lineage/v2/technologies",
        params=params,
        tool_name="search_lineage_assets",
    )
    technology_types = technology_types_list.get("technologies", [])
    if len(technology_types) == 0:
        raise ServiceError(
            f"Couldn't find any technology types with the name '{technology_type}'. No technology types available."
        )
    """
    closest_technology = chat_llm_request(
        lineage_get_proper_technology_from_list.format(list_of_technologies=technology_types,user_provided_technology=technology_type)
    )
    closest_technology_str = closest_technology.content if not isinstance(closest_technology, str) else closest_technology
    """

    closest_technology = get_close_matches(
        word=technology_type.lower(),
        possibilities=[
            tech_type.get("name", "").lower() for tech_type in technology_types
        ],
        n=1,
        cutoff=0.8,
    )

    if closest_technology:
        for words in technology_types:
            if str(words.get("name")).lower() == closest_technology[0].lower():
                return words.get("name")
    else:
        filters_not_found.append("technology_name")
    return ""


async def _get_lineage_asset_type(asset_type: str, filters_not_found: Optional[List[str]]) -> str:
    """
    Find asset type for filtering search_lineage_asset.

    Args:
        asset_type (str): The name of the asset type
        filters_not_found (Optional[List[str]]): List of filters that could not be used

    Returns:
        str: The mapped name of asset type.

    Raises:
        ServiceError: If asset type was not found
    """

    params = {
        "order": "-asset_type",
        "offset": 0,
        "limit": 100,
    }
    asset_types_list = await tool_helper_service.execute_get_request(
        url=str(tool_helper_service.base_url) + "/gov_lineage/v2/lineage_asset_types",
        params=params,
        tool_name="search_lineage_assets",
    )
    asset_types = asset_types_list.get("lineage_asset_types", [])

    if len(asset_types) == 0:
        raise ServiceError("Couldn't find any asset types to filter by")

    closest_name = get_close_matches(
        word=asset_type.lower(),
        possibilities=[name.lower() for name in asset_types],
        n=1,
        cutoff=0.8,
    )
    if closest_name:
        for asset_type_name in asset_types:
            if str(asset_type_name).lower() == closest_name[0].lower():
                return asset_type_name
        # If we found a close match but couldn't find it in asset_types (shouldn't happen, but just in case)
        raise ServiceError(
            f"Found a close match for '{asset_type}' but couldn't retrieve the asset type details"
        )
    else:
        if filters_not_found is not None:
            filters_not_found.append("asset_type")
        return ""


def _get_business_terms_or_classifications_payload(
    business: str, type: str
) -> dict[str, Any]:
    """
    Creates a payload for searching business terms or classifications.

    Args:
        business (str): The business for which to create payload.
        type (str): The type of business terms or classifications to creat payload for.

    Returns:
        dict[str, Any]: The payload for searching business terms or classifications.
    """

    payload = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"metadata.artifact_type": f"{type}"}},
                    {"gs_user_query": {"search_string": f"({business})"}},
                ]
            }
        }
    }

    return payload


async def _get_business_terms_or_classifications(business: str, type: str) -> list[str]:
    """
    Creates a list of business terms or classifications for a given business and type.

    Args:
        business (str): The business for which to retrieve the terms or classifications.
        type (str): The type of business terms or classifications to retrieve.

    Returns:
        list[str]: A list of business terms or classifications for the given business and type.
    """
    payload = _get_business_terms_or_classifications_payload(business, type)

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + "/v3/search",
        json=payload,
        tool_name="search_lineage_assets",
        params={"auth_cache": True},
    )
    name = ""
    business_id = ""
    list_of_names = [
        row["metadata"]["name"]
        for row in response["rows"]
        if "metadata" in row and "name" in row["metadata"]
    ]
    if len(list_of_names) == 0:
        # No results found
        return []
    # Always skipped as mcp has no UI and interrupts
    if len(list_of_names) > 1 and caller_context.get() != "mcp":
        printable_list = "\n".join(str(value) for value in list_of_names)
        res = trigger_interrupt_with_ui(
            "search_lineage_assets",
            f"Found more than one filter value fits the criteria. Which one did you mean?\n **{printable_list}**",
        )
    else:
        res = list_of_names[0]

    if response:
        closest_name = get_close_matches(
            word=res.lower(),
            possibilities=[name.lower() for name in list_of_names],
            n=1,
            cutoff=0.8,
        )
        for resp in response["rows"]:
            name = resp["metadata"]["name"]
            business_id = resp["entity"]["artifacts"]["global_id"]
            if name.lower() == closest_name[0].lower():
                return [business_id]

    return []


def _check_quality_filter(data_quality_operator, data_quality_value, filter_not_found_list):
    """
    Validate that data quality filter parameters are consistent.
    
    Both operator and value must be provided together, or neither should be provided.
    This is set by the model validator (search_lineage_assets.py) to work around
    MCP framework serialization of optional parameters.
    
    Args:
        data_quality_operator: Comparison operator for quality score
        data_quality_value: Numerical value for quality score
        filter_not_found_list: List to append error messages to
    """
    if bool(data_quality_operator) ^ _has_quality_value(data_quality_value):
        filter_not_found_list.append("data_quality")

def clean_str(val: Optional[str], default: str = "") -> str:
        """Converts None or 'null' (case-insensitive) to a safe string."""
        if val is None:
            return default
        if isinstance(val, str) and val.strip().lower() == "null":
            return default
        return val.strip()


def _transform_lineage_assets(
    lineage_assets: list[dict[str, Any]],
) -> list[LineageAsset]:
    """
    Transforms list of dictionaries with lineage assets to list of LineageAsset objects.

    Args:
        lineage_assets (list[dict[str, Any]]): List of dictionaries with lineage assets.

    Returns:
        list[LineageAsset]: List of LineageAsset objects.
    """
    lineage_assets_model = []
    for asset in lineage_assets:
        # Extract parent data if available
        parent_name = None
        parent_type = None
        path = None
        if "hierarchical_path" in asset and asset["hierarchical_path"]:
            path = "/".join(item.get("name", "") for item in reversed(asset["hierarchical_path"][1:]))    
            path = path.replace("|", "/")
            parent_data = asset["hierarchical_path"][-1]
            parent_name = parent_data.get("name")
            parent_type = parent_data.get("type")

        # Create LineageAsset with parent information
        lineage_asset = LineageAsset(
            id=asset.get("id", ""),
            name=asset.get("name", ""),
            type=asset.get("type", ""),
            tags=asset.get("tags", []),
            identity_key=path,
            parent_name=parent_name,
            parent_type=parent_type,
        )
        lineage_assets_model.append(lineage_asset)
    return lineage_assets_model


def _format_lineage_assets_for_table(assets: list) -> list:
    return [
        {
            "Name": item.name,
            "Type": item.type,
            "Path": item.identity_key,
        }
        for item in assets
    ]


def _handle_asset_selection_and_filters(
    response_count: int,
    lineage_assets_model: list,
    filter_not_found_list: list,
) -> list:
    """
    Handles UI table selector for asset selection and displays filter warnings.
    
    Args:
        response_count: Total count of assets found
        lineage_assets_model: List of LineageAsset objects
        filter_not_found_list: List of filters that could not be applied
    
    Returns:
        list: Selected assets if user made a selection, otherwise original list
    """
    end_lineage_list = lineage_assets_model
    
    if response_count > 0:
        selected_assets = ui_message_context.send_table_selector_msg(
            tool_name="search_lineage_assets",
            data=lineage_assets_model,
            formatted_data=_format_lineage_assets_for_table(lineage_assets_model),
            title="Assets",
            unique_keys=["Name", "Path"]
        )
        if selected_assets is not None:
            end_lineage_list = selected_assets
    
    if filter_not_found_list:
        ui_message_context.add_text_ui_message(
            tool_name="search_lineage_assets",
            text=f"We could not use filter(s): {', '.join(filter_not_found_list)}"
        )
    
    return end_lineage_list


@service_registry.tool(
    name="lineage_search_lineage_assets",
    description="""**REQUIRED FIRST STEP**: Searches for assets by name and returns their lineage IDs.
    
    **CRITICAL**: This tool MUST be called before get_lineage_graph when you have:
    - Asset names (e.g., "customer_table", "sales_data")
    - Partial asset names or search patterns
    - Any non-hexadecimal identifier
    
    This tool converts human-readable asset names into the 64-character hexadecimal
    lineage IDs required by get_lineage_graph. Results include the lineage ID in the
    'id' field of each asset.

    User can ask to compare the state of the asset between two versions returned by lineage_get_lineage_versions - use
    the dates fields then. Otherwise the dates field should be none.
    
    Workflow:
    1. Call this tool with asset name → Get lineage ID from results
    2. Pass the lineage ID to get_lineage_graph → Get lineage graph
    
    Args:
        name_query (str): Search pattern for asset names. Use "*" to match all assets.
            Exact matches are prioritized over partial matches.
        is_operational (bool): Filter for operational asset types only. Default: False
        tag (Optional[str]): Filter assets by specific tag
        data_quality_operator (Optional[str]): Comparison operator for data quality score
            ("equals", "greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal")
        data_quality_value (float): Numerical threshold for data quality filtering (valid range: 0.0-100.0).
            Used with data_quality_operator. Note: The internal sentinel value -0.01 is reserved
            and automatically set when no value is provided.
        business_term (Optional[str]): Filter by business glossary term
        business_classification (Optional[str]): Filter by business classification
        technology_name (str): Filter by technology name (e.g., "PostgreSQL"). 
            Only use when explicitly specified by user
        asset_type (str): Filter by asset type (e.g., "Table", "Column"). 
            Only use when explicitly specified by user
        dates (Optional[str]): ISO 8601 dates to validate if assets were available in that version. Used when comparing versions
    
    Returns:
        str: Search results containing:
            - lineage_assets: List of matching assets with properties:
                * id: **64-character hexadecimal lineage ID** (use this for get_lineage_graph)
                * name: Display name of the asset
                * type: Asset type classification
                * tags: Associated tags
                * identity_key: Resource identity key with parent hierarchy
                * parent_name: Name of the parent asset
                * parent_type: Type of the parent asset
            - response_is_complete: Boolean indicating whether all results are included
    
    Raises:
        ExternalServiceError: When the API request fails (non-200 status code)
        ToolProcessFailedError: When the response is missing expected data
    
    Notes:
        - Returns an empty list if no query or filters are provided
        - Returns an empty list if no matching assets are found
        - Use None or empty string for unspecified optional filters (not "null" string)
        - Apply filters only when explicitly mentioned by the user
        - **Extract the 'id' field from results to use with get_lineage_graph**
        - If user wants related assets call get_lineage_graph after this tool
    """,
)
@auto_context
async def search_lineage_assets(
    request: SearchLineageAssetsRequest,
) -> SearchLineageAssetsResponse:

    LOGGER.info(
        f"search_lineage_assets called with name_query={request.name_query}, technology_name={request.technology_name}, asset_type={request.asset_type}"
    )

    tag = clean_str(request.tag)
    data_quality_operator = clean_str(request.data_quality_operator)
    business_term = clean_str(request.business_term)
    business_classification = clean_str(request.business_classification)
    technology_name = clean_str(request.technology_name)
    asset_type = clean_str(request.asset_type)
    verified_dates = None
    if request.dates:
        verified_dates = verify_dates(dates=request.dates)
        if verified_dates and len(verified_dates) != 2:
            raise ServiceError(
                f"dates parameter must contain exactly 2 ISO 8601 dates, got {len(verified_dates)} dates"
            )

    # Check if at least one parameter is provided
    if _check_input_parameters(
        request.name_query,
        request.is_operational,
        tag,
        data_quality_operator,
        request.data_quality_value,
        business_term,
        business_classification,
        technology_name,
        asset_type,
    ):
        return SearchLineageAssetsResponse(lineage_assets=[], response_is_complete=True)
    
    filter_not_found_list = []
    _check_quality_filter(data_quality_operator, request.data_quality_value, filter_not_found_list)

    data_quality: Optional[QualityScore] = None
    if data_quality_operator and _has_quality_value(request.data_quality_value):
        data_quality = QualityScore(
            operator=data_quality_operator,
            value=str(request.data_quality_value),
        )
    technology_filter = (
        await _get_lineage_technology_type(technology_name, filter_not_found_list)
        if technology_name
        else None
    )
    technology_names = (
        [technology_filter] if technology_name and technology_filter else None
    )
    asset_types = (
        [await _get_lineage_asset_type(asset_type, filter_not_found_list)]
        if request.asset_type
        else None
    )
    is_operational_list = [request.is_operational] if request.is_operational else None
    tag_list = [tag] if tag else None
    business_terms = (
        await _get_business_terms_or_classifications(
            business_term, "glossary_term"
        )
        if business_term
        else None
    )
    business_classifications = (
        await _get_business_terms_or_classifications(
            business_classification, "classification"
        )
        if business_classification
        else None
    )
    response = await _call_search_lineage_assets(
        request.name_query,
        technology_names,
        asset_types,
        is_operational_list,
        tag_list,
        data_quality,
        business_terms,
        business_classifications,
        verified_dates
    )
    lineage_assets = response.get("lineage_assets", [])
    response_count = response.get("total_count", "")

    # Create LineageAsset objects with parent information
    lineage_assets_model = _transform_lineage_assets(lineage_assets=lineage_assets)

    response_is_complete = response_count <= 10
    
    end_lineage_list = _handle_asset_selection_and_filters(
        response_count, lineage_assets_model, filter_not_found_list
    )
    
    return SearchLineageAssetsResponse(
        lineage_assets=end_lineage_list, response_is_complete=response_is_complete
    )


@service_registry.tool(
    name="lineage_search_lineage_assets",
    description="""Searches for assets in the Lineage system based on name and optional filters.
    
    This tool finds lineage assets matching the provided name query, with filtering
    by technology name and asset type. Results are sorted by relevance, with exact matches first.
    Use filters only if user mentions them. Try to find the best match for filters.
    Do not shorten the results. Returnes an empty list if no query or filters are given.
    Method can return an empty list if no assets where found or if user has input no data.
    If user did not specify a filter do not send 'null' as string - use None or '' instead.""",
)
@auto_context
async def wxo_search_lineage_assets(
    name_query: str,
    is_operational: Optional[bool] = None,
    tag: Optional[str] = None,
    data_quality_operator: Optional[str] = None,
    data_quality_value: Optional[float] = None,
    business_term: Optional[str] = None,
    business_classification: Optional[str] = None,
    technology_name: Optional[str] = None,
    asset_type: Optional[str] = None,
    dates: Optional[str] = None,
) -> SearchLineageAssetsResponse:
    """Watsonx Orchestrator compatible version of search_lineage_assets."""

    request = SearchLineageAssetsRequest(
        name_query=name_query,
        is_operational=is_operational,
        tag=tag,
        data_quality_operator=data_quality_operator,
        data_quality_value=data_quality_value,
        business_term=business_term,
        business_classification=business_classification,
        technology_name=technology_name,
        asset_type=asset_type,
        dates=dates
    )

    # Call the original search_lineage_assets function
    return await search_lineage_assets(request)
