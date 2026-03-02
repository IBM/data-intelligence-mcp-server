# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Optional, List


class DataQualityRuleInfo(BaseModel):
    """Model for a single data quality rule information."""
    
    data_quality_rule_id: str = Field(..., description="The ID of the data quality rule")
    project_id: str = Field(..., description="The ID of the project")
    data_quality_rule_ui_url: str = Field(..., description="URL to view the data quality rule in the UI")
    data_quality_rule_name: Optional[str] = Field(None, description="The name of the data quality rule")


class FindDataQualityRulesRequest(BaseModel):
    """Request model for finding data quality rules."""
    
    project_id_or_name: str = Field(
        ...,
        description="The ID or name of the project. Examples: 'customer_analytics_project', 'financial_reporting_2023', 'supply_chain_optimization'"
    )
    data_quality_rule_name: Optional[str] = Field(
        None,
        description="The name of the data quality rule to find. If this is not provided, return all the data quality rules. This parameter is optional. Examples: 'validate_customer_email_format', 'check_sales_transaction_completeness', 'verify_inventory_data_consistency'"
    )


class FindDataQualityRulesResponse(BaseResponseModel):
    """Response model for finding data quality rules."""
    
    rules: List[DataQualityRuleInfo] = Field(
        ...,
        description="List of DataQualityRule objects, each containing the rule ID, project ID, UI URL, and name"
    )
    message: Optional[str] = Field(
        None,
        description="Message if no rules found"
    )
