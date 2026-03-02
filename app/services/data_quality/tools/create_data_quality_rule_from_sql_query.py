# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Optional

from app.core.registry import service_registry
from app.shared.logging import LOGGER, auto_context

from app.services.data_quality.models.create_data_quality_rule_from_sql_query import (
    CreateDataQualityRuleFromSQLQueryRequest,
    CreateDataQualityRuleFromSQLQueryResponse,
)

from app.services.data_quality.utils.data_quality_common_utils import (
    create_data_quality_rule_from_sql_query as create_data_quality_rule_from_sql_query_util,
)


@service_registry.tool(
    name="create_data_quality_rule_from_sql_query",
    description="""Creates a new data quality rule based on a provided SQL query. This tool allows you to define a data quality rule by specifying a SQL query that will be used to evaluate data quality. The tool returns details of the created data quality rule, including its ID, project ID, UI URL, and name.

Args:
    project_id_or_name (str): The ID or name of the project where the data quality rule will be created. Examples: 'customer_analytics_project', 'financial_reporting_2023', 'supply_chain_optimization'
    connection_id_or_name (str): The ID or name of the connection to be used for the data quality rule. Examples: 'salesforce_connection', 'aws_redshift_connection', 'postgresql_connection'
    sql_query (str): The SQL query that defines the data quality rule. Examples: 'SELECT COUNT(*) FROM customers WHERE email IS NOT NULL', "SELECT AVG(transaction_amount) FROM sales WHERE transaction_date > '2023-01-01'", 'SELECT product_id, SUM(quantity) FROM inventory GROUP BY product_id HAVING SUM(quantity) < 10'
    data_quality_rule_name (str): The name of the data quality rule to be created. Examples: 'validate_customer_email_format', 'check_sales_transaction_completeness', 'verify_inventory_data_consistency'
    data_quality_dimension_name (str): The name of the data quality dimension associated with the rule. This parameter is optional. Examples: 'completeness', 'validity', 'consistency'

Returns:
    CreateDataQualityRuleFromSQLQueryResponse: The tool returns a DataQualityRule object containing the rule ID, project ID, UI URL, and name of the created data quality rule.

Raises:
    ToolProcessFailedError: If the data quality rule creation fails fails.
    ExternalServiceError: If the data quality rule service request fails.

Note:
    This tool requires confirmation before execution as it creates a new resource.""",
    tags={"create", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def create_data_quality_rule_from_sql_query(
    request: CreateDataQualityRuleFromSQLQueryRequest,
) -> CreateDataQualityRuleFromSQLQueryResponse:
    """
    Creates a new data quality rule based on a provided SQL query.
    """
    LOGGER.info(
        "Creating data quality rule from SQL query: project=%s connection=%s rule_name=%s",
        request.project_id_or_name,
        request.connection_id_or_name,
        request.data_quality_rule_name
    )

    result = await create_data_quality_rule_from_sql_query_util(
        project_id_or_name=request.project_id_or_name,
        connection_id_or_name=request.connection_id_or_name,
        sql_query=request.sql_query,
        data_quality_rule_name=request.data_quality_rule_name,
        data_quality_dimension_name=request.data_quality_dimension_name,
    )

    return CreateDataQualityRuleFromSQLQueryResponse(
        data_quality_rule_id=result.data_quality_rule_id,
        project_id=result.project_id,
        data_quality_rule_ui_url=result.data_quality_rule_ui_url,
        data_quality_rule_name=result.data_quality_rule_name,
    )


@service_registry.tool(
    name="create_data_quality_rule_from_sql_query",
    description="""Watsonx Orchestrator compatible wrapper for create_data_quality_rule_from_sql_query.

Creates a new data quality rule based on a provided SQL query.

Args:
    project_id_or_name (str): The ID or name of the project where the data quality rule will be created.
    connection_id_or_name (str): The ID or name of the connection to be used for the data quality rule.
    sql_query (str): The SQL query that defines the data quality rule.
    data_quality_rule_name (str): The name of the data quality rule to be created.
    data_quality_dimension_name (Optional[str]): The name of the data quality dimension associated with the rule.

Returns:
    CreateDataQualityRuleFromSQLQueryResponse: DataQualityRule object with rule details.""",
    tags={"create", "data_quality"},
    meta={"version": "1.0", "service": "data_quality"},
)
@auto_context
async def wxo_create_data_quality_rule_from_sql_query(
    project_id_or_name: str,
    connection_id_or_name: str,
    sql_query: str,
    data_quality_rule_name: str,
    data_quality_dimension_name: Optional[str] = None,
) -> CreateDataQualityRuleFromSQLQueryResponse:
    """
    Watsonx Orchestrator wrapper: builds request model and delegates to main tool.
    """
    request = CreateDataQualityRuleFromSQLQueryRequest(
        project_id_or_name=project_id_or_name,
        connection_id_or_name=connection_id_or_name,
        sql_query=sql_query,
        data_quality_rule_name=data_quality_rule_name,
        data_quality_dimension_name=data_quality_dimension_name,
    )
    return await create_data_quality_rule_from_sql_query(request)
