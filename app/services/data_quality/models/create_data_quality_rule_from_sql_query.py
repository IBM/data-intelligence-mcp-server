# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Optional


class CreateDataQualityRuleFromSQLQueryRequest(BaseModel):
    """Request model for creating a data quality rule from SQL query."""
    
    project_id_or_name: str = Field(
        ...,
        description="The ID or name of the project where the data quality rule will be created. Examples: 'customer_analytics_project', 'financial_reporting_2023', 'supply_chain_optimization'"
    )
    connection_id_or_name: str = Field(
        ...,
        description="The ID or name of the connection to be used for the data quality rule. Examples: 'salesforce_connection', 'aws_redshift_connection', 'postgresql_connection'"
    )
    sql_query: str = Field(
        ...,
        description="The SQL query that defines the data quality rule. Examples: 'SELECT COUNT(*) FROM customers WHERE email IS NOT NULL', \"SELECT AVG(transaction_amount) FROM sales WHERE transaction_date > '2023-01-01'\", 'SELECT product_id, SUM(quantity) FROM inventory GROUP BY product_id HAVING SUM(quantity) < 10'"
    )
    data_quality_rule_name: str = Field(
        ...,
        description="The name of the data quality rule to be created. Examples: 'validate_customer_email_format', 'check_sales_transaction_completeness', 'verify_inventory_data_consistency'"
    )
    data_quality_dimension_name: Optional[str] = Field(
        None,
        description="The name of the data quality dimension associated with the rule. This parameter is optional. Examples: 'completeness', 'validity', 'consistency'"
    )


class CreateDataQualityRuleFromSQLQueryResponse(BaseResponseModel):
    """Response model for creating a data quality rule from SQL query."""
    
    data_quality_rule_id: str = Field(..., description="The ID of the created data quality rule")
    project_id: str = Field(..., description="The ID of the project")
    data_quality_rule_ui_url: str = Field(..., description="URL to view the data quality rule in the UI")
    data_quality_rule_name: str = Field(..., description="The name of the data quality rule")
