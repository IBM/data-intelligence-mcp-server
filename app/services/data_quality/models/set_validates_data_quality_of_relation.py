# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Optional


class SetValidatesDataQualityOfRelationRequest(BaseModel):
    """Request model for setting validates data quality of relation."""
    
    project_id_or_name: str = Field(
        ...,
        description="The ID or name of the project containing the data quality rule. Examples: 'customer_analytics_project', 'financial_reporting_2023', 'supply_chain_optimization'"
    )
    data_quality_rule_id_or_name: str = Field(
        ...,
        description="The ID or name of the data quality rule to execute. Examples: 'validate_customer_email_format', 'check_sales_transaction_completeness', 'verify_inventory_data_consistency'"
    )
    data_asset_id_or_name: str = Field(
        ...,
        description="The ID or name of the data asset. Examples: 'customer_data_2023', 'sales_records_q2', 'inventory_management'"
    )
    column_name: str = Field(
        ...,
        description="The name of column. Examples: 'customer_id', 'transaction_date', 'product_category'"
    )


class SetValidatesDataQualityOfRelationResponse(BaseResponseModel):
    """Response model for setting validates data quality of relation."""
    
    data_quality_rule_id: str = Field(..., description="The ID of the data quality rule")
    project_id: str = Field(..., description="The ID of the project")
    data_quality_rule_ui_url: str = Field(..., description="URL to view the data quality rule in the UI")
    data_quality_rule_name: Optional[str] = Field(None, description="The name of the data quality rule")
