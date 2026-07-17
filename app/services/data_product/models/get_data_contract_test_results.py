# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Literal, Optional, List, Dict, Any


class TestSummaryItem(BaseModel):
    """Individual test summary item."""
    status: Optional[str] = Field(None, description="Status of the test check")
    check: Optional[str] = Field(None, description="Name of the check performed")
    asset_name: Optional[str] = Field(None, description="Name of the asset tested")
    records_returned: Optional[str] = Field(None, description="Number of records returned")


class ContractTest(BaseModel):
    """Contract test details."""
    status: Optional[str] = Field(None, description="Overall status of the contract test")
    last_tested_time: Optional[str] = Field(None, description="Timestamp of the last test execution")
    data_contract_id: Optional[str] = Field(None, description="ID of the data contract")
    project_id: Optional[str] = Field(None, description="ID of the project")
    message: Optional[str] = Field(None, description="Message about the test execution")
    test_run_id: Optional[str] = Field(None, description="ID of the test run")
    test_summary: Optional[List[TestSummaryItem]] = Field(None, description="Summary of test results")


class GetDataContractTestResultsRequest(BaseModel):
    """Request model for getting data contract test results."""
    data_product_version_id: str = Field(..., description="The ID of the data product version for which we need to get the contract test results. Can be a draft or published data product.")
    data_product_state: Literal["draft", "available"] = Field(..., description="The state of the data product - should be one of 'draft' or 'available'")


class GetDataContractTestResultsResponse(BaseResponseModel):
    """Response model for data contract test results."""
    contract_test: Dict[str, Any] = Field(..., description="Contract test details including status, test summary, and metadata.")

