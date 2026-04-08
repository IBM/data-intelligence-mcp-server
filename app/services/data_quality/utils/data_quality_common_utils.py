# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import re
import sys
import uuid
from functools import partial
from typing import Callable, Dict, List, Literal, Optional

from tenacity import RetryError

from app.services.constants import (
    CAMS_ASSETS_BASE_ENDPOINT,
    DATA_QUALITY_BASE_ENDPOINT,
    DATA_QUALITY_BASE_ENDPOINT_V3,
    GS_BASE_ENDPOINT,
)
from app.services.data_quality.models.create_data_quality_rule_from_sql_query import (
    CreateDataQualityRuleFromSQLQueryRequest,
    CreateDataQualityRuleFromSQLQueryResponse,
)
from app.services.data_quality.models.data_quality import DataQuality, DataQualityRule
from app.services.data_quality.models.find_data_quality_rules import (
    FindDataQualityRulesRequest,
    FindDataQualityRulesResponse,
)
from app.services.data_quality.models.get_data_quality_for_asset import (
    GetDataQualityForAssetRequest,
    GetDataQualityForAssetResponse,
)
from app.services.data_quality.models.run_data_quality_rule import (
    RunDataQualityRuleRequest,
    RunDataQualityRuleResponse,
)
from app.services.data_quality.models.set_validates_data_quality_of_relation import (
    SetValidatesDataQualityOfRelationRequest,
    SetValidatesDataQualityOfRelationResponse,
)
from app.services.tool_utils import (
    ENTITY_ASSETS_PROJECT_ID,
    METADATA_ARTIFACT_TYPE,
    find_asset_id,
    find_catalog_id,
    find_connection_id,
    find_project_id,
)
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging import LOGGER, auto_context
from app.shared.utils.helpers import append_context_to_url, confirm_uuid, is_uuid
from app.shared.utils.tool_helper_service import tool_helper_service

DATA_QUALITY_V3_BASE_URL = str(tool_helper_service.base_url) + DATA_QUALITY_BASE_ENDPOINT_V3
DATA_QUALITY_V4_BASE_URL = str(tool_helper_service.base_url) + DATA_QUALITY_BASE_ENDPOINT


async def get_data_quality_rule_ui_url(project_id: str, data_quality_rule_id: str) -> str:
    """
    Constructs the UI URL for a data quality rule.
    
    Args:
        project_id (str): The ID of the project containing the data quality rule.
        data_quality_rule_id (str): The ID of the data quality rule.
    
    Returns:
        str: The UI URL for the data quality rule with context appended.
    """
    base_url = f"{tool_helper_service.ui_base_url}/data-quality/data-quality-rule/display/{data_quality_rule_id}?project_id={project_id}"
    return append_context_to_url(base_url)

GET_RELATIONSHIPS_URL = (
    str(tool_helper_service.base_url) + CAMS_ASSETS_BASE_ENDPOINT + "/get_relationships"
)
SET_RELATIONSHIPS_URL = (
    str(tool_helper_service.base_url) + CAMS_ASSETS_BASE_ENDPOINT + "/set_relationships"
)


async def _find_data_quality_rules(
    project_id: str,
    data_quality_rule_name: Optional[str] = None,
    exact_match: Optional[bool] = False,
) -> List[DataQualityRule]:
    """
    Finds and returns the data quality rules within a project. The response is filtered by name if it is provided.

    Args:
        project_id (str): The ID of the project
        data_quality_rule_name (Optional[str]): The name of the data quality rule to search for.
        exact_match (Optional[bool]): If true, the exact match of the data quality rule name is done.

    Returns:
        List[DataQualityRule]: The list of the DataQualityRule objects.

    Raises:
        ToolProcessFailedError: If no data quality rule with the specified name is found in the project.
        ExternalServiceError: If the search service request fails.
    """

    params = {"auth_scope": "project", "auth_cache": True}
    payload = None
    if data_quality_rule_name:
        if exact_match:
            payload = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"metadata.name.keyword": data_quality_rule_name}},
                            {"term": {METADATA_ARTIFACT_TYPE: "data_rule"}},
                            {"term": {ENTITY_ASSETS_PROJECT_ID: project_id}},
                        ]
                    }
                }
            }
        else:
            payload = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": {
                                    "metadata.name": {"query": data_quality_rule_name}
                                }
                            },
                            {"term": {METADATA_ARTIFACT_TYPE: "data_rule"}},
                            {"term": {ENTITY_ASSETS_PROJECT_ID: project_id}},
                        ]
                    }
                }
            }
    else:
        payload = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {METADATA_ARTIFACT_TYPE: "data_rule"}},
                        {"term": {ENTITY_ASSETS_PROJECT_ID: project_id}},
                    ]
                }
            }
        }
    try:
        response = await tool_helper_service.execute_post_request(
            url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
            json=payload,
            params=params,
        )
    except ExternalAPIError as ese:
        LOGGER.error(
            "An unexpected exception occurs during finding data quality rules. (Cause=%s)",
            str(ese),
        )
        raise ServiceError(
            f"Finding data quality rules failed due to: {str(ese)}"
        )

    rows = response.get("rows", [])
    data_quality_rules = []

    for row in rows:
        data_quality_rule_id = row.get("artifact_id")
        data_quality_rules.append(
            DataQualityRule(
                data_quality_rule_id=data_quality_rule_id,
                project_id=project_id,
                data_quality_rule_ui_url=await get_data_quality_rule_ui_url(
                    project_id=project_id, data_quality_rule_id=data_quality_rule_id
                ),
                data_quality_rule_name=row["metadata"]["name"],
            )
        )

    return data_quality_rules


async def _find_data_quality_rule_id(data_quality_rule_name: str, project_id: str) -> str:
    """
    Finds and returns the UUID of a data quality rule by searching for its name within a project.

    Args:
        data_quality_rule_name (str): The name of the data quality rule to search for.
        project_id (str): The unique identifier of the project

    Returns:
        str: The UUID of the found data quality rule.

    Raises:
        ToolProcessFailedError: If no data quality rule with the specified name is found in the project.
        ExternalServiceError: If the search service request fails.
    """

    data_quality_rules = await _find_data_quality_rules(project_id, data_quality_rule_name)
    if not data_quality_rules:
        raise ServiceError(
            f"Couldn't find any data quality rules with the name '{data_quality_rule_name}' in project with id '{project_id}'."
        )
    return data_quality_rules[0].data_quality_rule_id


async def _retrieve_data_quality_id_for_asset(
    asset_id: str, container_id: str, container_type: Literal["project", "catalog"]
) -> str:
    """
    Find id of data quality for data asset

    Args:
        asset_id: str: Asset id
        container_id: str: Container id
        container_type: str: Container type (project or catalog)

    Returns:
        uuid.UUID: Unique identifier of the data quality asset.
    """

    params = {"wkc_asset_id": asset_id, f"{container_type.lower()}_id": container_id}

    LOGGER.info(
        "[DQ] Searching DQ asset for wkc_asset_id=%s, container_id=%s, type=%s",
        asset_id,
        container_id,
        container_type,
    )

    try:
        response = await tool_helper_service.execute_post_request(
            str(tool_helper_service.base_url)
            + DATA_QUALITY_BASE_ENDPOINT
            + "/search_dq_asset",
            params=params,
        )
    except ExternalAPIError:
        raise ServiceError(
            f"Tool get_data_quality_for_asset call finishes unsuccessfully. Asset {asset_id} from {container_type} {container_id} has no data quality information."
        )
    dq_id = response.get("id")
    if dq_id:
        return dq_id
    else:
        raise ServiceError(
            f"Tool get_data_quality_for_asset call finishes unsuccessfully. Invalid data: '{response}'"
        )


def _ratio_to_percentage(ratio_str):
    """
    Convert a ratio (0.0-1.0) to a percentage string with smart decimal formatting.
    
    Shows 1 decimal place if the hundredths place is 0 (e.g., 95.0, 98.5),
    otherwise shows 2 decimal places (e.g., 95.84, 83.38).
    This provides cleaner output while maintaining precision when needed.
    """
    value = float(ratio_str)
    percentage = value * 100
    # Round to 2 decimal places first to handle floating point precision
    rounded_percentage = round(percentage, 2)
    # Check if the value has a non-zero hundredths place
    # by checking if multiplying by 100 and taking modulo 10 gives a non-zero result
    if abs(rounded_percentage * 10 % 10) < 0.01:
        return f"{rounded_percentage:.1f}"  # show up to 1 decimal
    else:
        return f"{rounded_percentage:.2f}"  # show up to 2 decimals


async def _retrieve_data_quality(
    data_quality_id: str,
    asset_id: str,
    container_id: str,
    container_type: Literal["project", "catalog"],
) -> DataQuality:
    """
    Retrieve data quality scores for a given data quality asset.

    Args:
        data_quality_id: str: Data quality asset id
        asset_id: str: Asset id
        container_id: str: Container id
        container_type: str: Container type (project or catalog)

    Returns:
        DataQuality: Data quality asset object
    """

    params = {"asset_id": data_quality_id, f"{container_type.lower()}_id": container_id}
    response = await tool_helper_service.execute_get_request(
        str(tool_helper_service.base_url) + DATA_QUALITY_BASE_ENDPOINT + "/scores",
        params=params,
    )
    scores = [
        score
        for score in response.get("scores", [])
        if score.get("status", "").lower() == "actual"
    ]
    if len(scores) == 0:
        raise ServiceError(
            "Tool get_data_quality_for_asset call finishes unsuccessfully. Data quality score not found."
        )
    score = scores[0]

    dimension_scores = score.get("dimension_scores", [])

    consistency_list = [
        dimension
        for dimension in dimension_scores
        if dimension["dimension"].get("name", "").lower() == "consistency"
    ]
    consistency = (
        _ratio_to_percentage(consistency_list[0]["score"])
        if len(consistency_list) > 0
        else None
    )

    validity_list = [
        dimension
        for dimension in dimension_scores
        if dimension["dimension"].get("name", "").lower() == "validity"
    ]
    validity = (
        _ratio_to_percentage(validity_list[0]["score"])
        if len(validity_list) > 0
        else None
    )

    completeness_list = [
        dimension
        for dimension in dimension_scores
        if dimension["dimension"].get("name", "").lower() == "completeness"
    ]
    completeness = (
        _ratio_to_percentage(completeness_list[0]["score"])
        if len(completeness_list) > 0
        else None
    )

    report_url = (
        f"{tool_helper_service.ui_base_url}/data/catalogs/{container_id}/asset/{asset_id}/data-quality"
        if container_type == "catalog"
        else f"{tool_helper_service.ui_base_url}/projects/{container_id}/data-assets/{asset_id}/data-quality"
    )

    return DataQuality(
        overall=_ratio_to_percentage(score["score"]),
        consistency=consistency,
        validity=validity,
        completeness=completeness,
        report_url=report_url,
    )

async def get_data_quality_for_asset(
    asset_id_or_name: str,
    container_id_or_name: str,
    container_type: Literal["catalog", "project"],
) -> DataQuality:
    """
    Retrieve data quality metrics and information for a specific asset.

    REQUIRED: ALL THREE parameters are mandatory. Ask for any missing information:
    1. asset_id_or_name - The specific data asset name/ID (e.g., "CustomerTable") - REQUIRED
    2. container_id_or_name - The project or catalog name/ID (e.g., "AgentsDemo") - REQUIRED
    3. container_type - Either "project" or "catalog" - REQUIRED

    When asking for missing information:
    - If asset name is missing: Ask "Which asset would you like to check?"
    - If container is missing: Ask "Which project or catalog contains this asset?"
    - If container type is missing: Ask "Is this in a project or catalog?"
    - If user mentions "project" or "catalog", use that value directly

    Args:
        asset_id_or_name (str): The asset's UUID or name.
        container_id_or_name (str): The project or catalog's UUID or name.
        container_type (Literal["project", "catalog"]): Either "project" or "catalog".

    Returns:
        DataQuality: Quality metrics including overall, consistency, validity, completeness scores and report URL.

    Raises:
        ToolProcessFailedError: If the asset has no data quality information or data quality scores cannot be retrieved.
    """

    LOGGER.info(
        "[DQ] Calling get_data_quality_for_asset with asset_id_or_name=%s, container_id_or_name=%s, container_type=%s",
        asset_id_or_name,
        container_id_or_name,
        container_type,
    )
    # Resolve container ID
    container_id = await confirm_uuid(
        container_id_or_name,
        find_project_id if container_type == "project" else find_catalog_id,
    )
    # Resolve data asset ID
    asset_id = await confirm_uuid(
        asset_id_or_name,
        partial(
            find_asset_id, container_id=container_id, container_type=container_type
        ),
    )

    LOGGER.info("[DQ] Fetching data_quality_id for asset_id=%s", asset_id)
    data_quality_id = await _retrieve_data_quality_id_for_asset(
        asset_id=asset_id,
        container_id=container_id,
        container_type=container_type,
    )

    data_quality = await _retrieve_data_quality(
        data_quality_id=data_quality_id,
        asset_id=asset_id,
        container_id=container_id,
        container_type=container_type,
    )

    data_quality_model = DataQuality.model_validate(data_quality)
    
    return data_quality_model

async def find_data_quality_rules(
    project_id_or_name: str, data_quality_rule_name: Optional[str] = None
) -> List[DataQualityRule]:
    """
    Find data quality rules in the given project id or name. If data quality rule name is not provided,
    then return all the data quality rules from this project. This is typically used when the user asks to view, describe, inspect, or reference
    existing data quality rules. We shout not use this When the user is asking to execute/run a rule (use the run tool instead) or When the user wants to create/update/delete a rule

    Args:
        project_id_or_name (str): The ID or name of the project.
        data_quality_rule_name (Optional[str]): The name of the data quality rule to find. If this is not provided, return all the data quality rules.

    Returns:
        List[DataQualityRule]: The list of the DataQualityRule objects. Returns empty list if no rules found.
            Each DataQualityRule contains:
                - data_quality_rule_id: The ID of the data quality rule
                - project_id: The ID of the project
                - data_quality_rule_ui_url: URL to view the data quality rule in the UI
                - data_quality_rule_name: The name of the data quality rule

    Raises:
        ToolProcessFailedError: If the data quality rule find fails.
        ExternalServiceError: If the data quality rule find service request fails.
    """

    LOGGER.info(
        "Calling find_data_quality_rules, data_quality_rule_name: %s, project_id_or_name: %s",
        data_quality_rule_name,
        project_id_or_name,
    )

    project_id = await confirm_uuid(project_id_or_name, find_project_id)
    dq_rules = await _find_data_quality_rules(project_id, data_quality_rule_name)
    return dq_rules  # Returns empty list if no rules found


async def run_data_quality_rule(
    project_id_or_name: str, data_quality_rule_id_or_name: str
) -> DataQualityRule:
    """
       Executes a specific data quality rule and returns details about the execution. Use when the user wants to re-run a rule.
       Do NOT use when the user only wants to view rule. Do NOT use for creating, updating, or deleting rules. Do NOT call this tool for descibe data quality rules.
       Do NOT use when required parameters (project_id, rule_id) are missing.

       Args:
           project_id_or_name (str): The ID or name of the project containing the data quality rule.
           data_quality_rule_id_or_name (str): The ID or name of the data quality rule to execute.

       Returns:
           DataQualityRule: An object containing complete information about the data quality rule:
               - data_quality_rule_id: The ID of the data quality rule
               - project_id: The ID of the project
               - data_quality_rule_ui_url: URL to view the data quality rule in the UI
               - data_quality_rule_name: The name of the data quality rule

       Raises:
           ToolProcessFailedError: If the data quality rule run fails.
           ExternalServiceError: If the data quality rule service request fails.
    """

    LOGGER.info(
        "Calling run_data_quality_rule, project_id_or_name: %s, data_quality_rule_id_or_name: %s",
        project_id_or_name,
        data_quality_rule_id_or_name,
    )

    project_id = await confirm_uuid(project_id_or_name, find_project_id)
    
    data_quality_rule_id = await confirm_uuid(
        data_quality_rule_id_or_name,
        partial(_find_data_quality_rule_id, project_id=project_id),
    )

    url = f"{DATA_QUALITY_V3_BASE_URL}/projects/{project_id}/rules/{data_quality_rule_id}/execute"

    try:
        await tool_helper_service.execute_post_request(
            url=url, tool_name="run_data_quality_rule"
        )

    except ExternalAPIError as ese:
        LOGGER.error(
            "An unexpected exception occurs during running data quality rule. (Cause=%s)",
            str(ese),
        )
        raise ServiceError(
            f"The execution of data quality rule '{data_quality_rule_id}' failed due to: {str(ese)}"
        )
    
    # Get the rule name if it was provided as a name (not UUID)
    rule_name = None
    if data_quality_rule_id_or_name != data_quality_rule_id:
        rule_name = data_quality_rule_id_or_name
    
    return DataQualityRule(
        data_quality_rule_id=data_quality_rule_id,
        project_id=project_id,
        data_quality_rule_ui_url=await get_data_quality_rule_ui_url(
            project_id=project_id, data_quality_rule_id=data_quality_rule_id
        ),
        data_quality_rule_name=rule_name,
    )


async def set_validates_data_quality_of_relation(
    project_id_or_name: str,
    data_quality_rule_id_or_name: str,
    data_asset_id_or_name: str,
    column_name: str,
) -> DataQualityRule:
    """
    Sets a validates data quality of relationship from a data quality rule to a column from a data asset in a project.
    This relationship is used to report data quality score for the given column using logic present in data quality rule.

    Args:
        project_id_or_name (str): The ID or name of the project containing the data quality rule.
        data_quality_rule_id_or_name (str): The ID or name of the data quality rule to execute.
        data_asset_id_or_name (str): The ID or name of the data asset.
        column_name (str): The name of column.

    Returns:
        DataQualityRule: An object containing complete information about the data quality rule:
            - data_quality_rule_id: The ID of the data quality rule
            - project_id: The ID of the project
            - data_quality_rule_ui_url: URL to view the data quality rule in the UI
            - data_quality_rule_name: The name of the data quality rule

    Raises:
        ToolProcessFailedError: If the data quality rule relation set operation fails.
        ExternalServiceError: If the data quality rule service request fails.
    """

    LOGGER.info(
        "Calling set_data_quality_of_relation, project_id_or_name: %s, data_quality_rule_id_or_name: %s, data_asset_id_or_name: %s, column_name: %s",
        project_id_or_name,
        data_quality_rule_id_or_name,
        data_asset_id_or_name,
        column_name,
    )

    project_id = await confirm_uuid(project_id_or_name, find_project_id)
    data_quality_rule_name = None
    data_quality_rule_id = await confirm_uuid(
        data_quality_rule_id_or_name,
        partial(_find_data_quality_rule_id, project_id=project_id),
    )
    if data_quality_rule_id_or_name != data_quality_rule_id:
        data_quality_rule_name = data_quality_rule_id_or_name
    data_asset_id = await confirm_uuid(
        data_asset_id_or_name, partial(find_asset_id, container_id=project_id, container_type="project")
    )
    found_column_name = await find_dataset_column(column_name, data_asset_id, project_id)

    url = GET_RELATIONSHIPS_URL
    query_params = {
        "asset_id": data_quality_rule_id,
        "project_id": project_id,
        "related_asset_types": "data_asset#_column",
        "relationship_names": "validates_data_quality_of",
        "include_target_columns": True,
    }
    try:
        response = await tool_helper_service.execute_post_request(
            url=url,
            params=query_params,
            tool_name="set_validates_data_quality_of_relation",
        )
    except ExternalAPIError as ese:
        LOGGER.error(
            "An unexpected exception occurs during setting validates_data_quality_of relation data quality rule. (Cause=%s)",
            str(ese),
        )
        raise ServiceError(
            f"setting validates_data_quality_of relation failed due to {str(ese)}."
        )
    existing_relationship_found = False
    target_asset_id = data_asset_id + "#COLUMN#" + found_column_name
    for resource in response.get("resources", []):
        if project_id == resource.get("project_id") and target_asset_id == resource.get(
            "asset_id"
        ):
            existing_relationship_found = True
            break

    if not existing_relationship_found:
        url = SET_RELATIONSHIPS_URL
        payload = {
            "relationships": [
                {
                    "relationship_name": "validates_data_quality_of",
                    "source": {
                        "asset_id": data_quality_rule_id,
                        "project_id": project_id,
                    },
                    "target": {"asset_id": target_asset_id, "project_id": project_id},
                }
            ]
        }
        await tool_helper_service.execute_post_request(
            url=url, json=payload, tool_name="set_validates_data_quality_of_relation"
        )
    else:
        LOGGER.info(
            "A relationship of type 'validates_data_quality_of' from data quality rule %s to column %s already exists.",
            data_quality_rule_name if data_quality_rule_name else data_quality_rule_id,
            found_column_name,
        )

    return DataQualityRule(
        data_quality_rule_id=data_quality_rule_id,
        project_id=project_id,
        data_quality_rule_ui_url=await get_data_quality_rule_ui_url(
            project_id=project_id, data_quality_rule_id=data_quality_rule_id
        ),
        data_quality_rule_name=data_quality_rule_name,
    )


async def find_data_quality_dimension_id(data_quality_dimension_name: str) -> str:
    """
    Find id of data quality dimension based on data quality dimension name.

    Args:
        data_quality_dimension_name (str): The name of the data quality dimension.

    Returns:
        str: Unique identifier of the data quality dimension.
    """
    from app.shared.utils.helpers import get_closest_match
    
    response = await tool_helper_service.execute_get_request(
        str(tool_helper_service.base_url) + DATA_QUALITY_BASE_ENDPOINT + "/dimensions",
    )
    dimensions = [
        {"name": dimension["name"], "id": dimension["id"]}
        for dimension in response.get("dimensions", [])
    ]
    result_id = get_closest_match(dimensions, data_quality_dimension_name)
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"Couldn't find any data quality dimension with the name '{data_quality_dimension_name}'"
        )


async def find_dataset_column(column_name: str, dataset_id: str, project_id: str) -> str:
    """
    Find closest matching column name from dataset in specified project.

    Args:
        column_name (str): The name of the column.
        dataset_id (str): The ID of the data asset.
        project_id (str): The unique identifier of the project.

    Returns:
        str: The matching column name
    """
    from app.shared.utils.helpers import get_closest_match
    
    params = {"auth_scope": "project", "auth_cache": True}
    payload = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"artifact_id": dataset_id}},
                    {"term": {METADATA_ARTIFACT_TYPE: "data_asset"}},
                    {"term": {ENTITY_ASSETS_PROJECT_ID: project_id}},
                ]
            }
        }
    }

    response = await tool_helper_service.execute_post_request(
        url=str(tool_helper_service.base_url) + GS_BASE_ENDPOINT,
        json=payload,
        params=params
    )

    columns = []
    for row in response.get("rows", []):
        columns = [
            {"name": column, "id": column}
            for column in row.get("entity").get("assets").get("column_names", [])
        ]
    result_id = get_closest_match(columns, column_name)
    if result_id:
        return result_id
    else:
        raise ServiceError(
            f"Couldn't find any matching column with the name '{column_name}' in data asset '{dataset_id}' in project '{project_id}'"
        )


def unescape_sql_quotes(input_str: str) -> str:
    """
    Unescape SQL quotes in the input string.
    
    Args:
        input_str (str): The input string with escaped quotes.
        
    Returns:
        str: The string with unescaped quotes.
    """
    return input_str.replace("\\'", "'").replace('\\"', '"')


def get_data_quality_rule_payload(
    rule_name: str,
    connection_id: str,
    sql_query: str,
    dimension_id: Optional[str] = None
) -> Dict:
    """
    Build the payload for creating a data quality rule.
    
    Args:
        rule_name (str): The name of the data quality rule.
        connection_id (str): The ID of the connection.
        sql_query (str): The SQL query for the rule.
        dimension_id (Optional[str]): The ID of the data quality dimension.
        
    Returns:
        Dict: The payload for creating the rule.
    """
    # Build payload with correct structure based on semantic-agent-service
    if dimension_id:
        return {
            "name": rule_name,
            "dimension": {
                "id": dimension_id
            },
            "input": {
                "sql": {
                    "connection": {
                        "id": connection_id
                    },
                    "select_statement": sql_query
                }
            },
            "apply_all_present_dimensions": False
        }
    
    return {
        "name": rule_name,
        "input": {
            "sql": {
                "connection": {
                    "id": connection_id
                },
                "select_statement": sql_query
            }
        }
    }


async def create_data_quality_rule_from_sql_query(
    project_id_or_name: str,
    connection_id_or_name: str,
    sql_query: str,
    data_quality_rule_name: str,
    data_quality_dimension_name: Optional[str] = None,
) -> DataQualityRule:
    """
    Create a new data quality rule in a project using the provided SQL.
    Create or configure a Data Quality Rule using SQL query.
    This tool creates a data quality rule in the specified project using the provided SQL query.

    Args:
        project_id_or_name (str): ID or name of the project where the data quality rule will be created.
        connection_id_or_name (str): ID or name of the connection to associate with the SQL query.
        sql_query (str): The SQL query to save in the data quality rule.
        data_quality_rule_name (str): The name of the data quality rule.
        data_quality_dimension_name (Optional[str]): The name of the data quality dimension.

    Returns:
        DataQualityRule: An object containing complete information about the newly created data quality rule:
            - data_quality_rule_id: The ID of the data quality rule
            - project_id: The ID of the project
            - data_quality_rule_ui_url: URL to view the data quality rule in the UI
            - data_quality_rule_name: The name of the data quality rule

    Raises:
        ToolProcessFailedError: If the data quality rule creation fails fails.
        ExternalServiceError: If the data quality rule service request fails.

    Note:
        This tool requires confirmation before execution as it creates a new resource.
    """

    LOGGER.info(
        "Calling create_data_quality_rule_from_sql_query, project_id_or_name: %s, connection_id_or_name: %s, sql_query: %s, data_quality_rule_name: %s",
        project_id_or_name,
        connection_id_or_name,
        sql_query,
        data_quality_rule_name,
    )

    project_id = await confirm_uuid(project_id_or_name, find_project_id)
    connection_id = await confirm_uuid(
        connection_id_or_name,
        partial(find_connection_id, container_id=project_id, container_type="project"),
    )

    if await _find_data_quality_rules(project_id, data_quality_rule_name, True):
        raise ServiceError(
            f"A data quality rule with name '{data_quality_rule_name}' already exists in project with '{project_id_or_name}'. Please provide a different name."
        )

    data_quality_dimension_id = None
    if data_quality_dimension_name:
        data_quality_dimension_id = await find_data_quality_dimension_id(
            data_quality_dimension_name
        )

    sql_query = unescape_sql_quotes(sql_query)
    payload = get_data_quality_rule_payload(
        data_quality_rule_name, connection_id, sql_query, data_quality_dimension_id
    )

    url = f"{DATA_QUALITY_V3_BASE_URL}/projects/{project_id}/rules"
    try:
        response = await tool_helper_service.execute_post_request(
            url=url,
            json=payload,
            tool_name="create_data_quality_rule_from_sql_query",
        )
    except ExternalAPIError as ese:
        LOGGER.error(
            "An unexpected exception occurs during creating data quality rule. (Cause=%s)",
            str(ese),
        )
        raise ServiceError(
            f"Creation of data quality rule: '{data_quality_rule_name}' failed due to {str(ese)}."
        )

    data_quality_rule_id = response.get("id")
    
    if not data_quality_rule_id:
        raise ServiceError(
            f"Failed to create data quality rule: '{data_quality_rule_name}'. No rule ID returned."
        )

    return DataQualityRule(
        data_quality_rule_id=data_quality_rule_id,
        project_id=project_id,
        data_quality_rule_ui_url=await get_data_quality_rule_ui_url(
            project_id=project_id, data_quality_rule_id=data_quality_rule_id
        ),
        data_quality_rule_name=data_quality_rule_name,
    )
