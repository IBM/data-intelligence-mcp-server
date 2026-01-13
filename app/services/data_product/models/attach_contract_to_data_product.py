# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from typing import Optional
from pydantic import BaseModel, Field

THE_ID_OF_THE_DATA_PRODUCT_DRAFT = "The ID of the data product draft."
THE_ID_OF_THE_CONTRACT_TERMS_ASSET = "The ID of the contract terms asset."

class AttachURLContractToDataProductRequest(BaseModel):
    data_product_draft_id: str = Field(
        ..., description=THE_ID_OF_THE_DATA_PRODUCT_DRAFT
    )
    contract_terms_id: str = Field(
        ..., description=THE_ID_OF_THE_CONTRACT_TERMS_ASSET
    )
    contract_url: str = Field(..., description="The contract URL.")
    contract_name: str = Field(..., description="The contract name.")


class ContractTemplate(BaseModel):
    contract_template_id: str = Field(
        ..., description="The ID of the contract template."
    )
    contract_template_name: str = Field(
        ..., description="The name of the contract template."
    )

class GetContractTemplateResponse(BaseModel):
    contract_templates: list[ContractTemplate] = Field(
        ..., description="The contract templates."
    )
class AttachContractTemplateToDataProductRequest(BaseModel):
    contract_template_id: str = Field(
        ..., description="The ID of the contract template."
    )
    data_product_draft_id: str = Field(
        ..., description=THE_ID_OF_THE_DATA_PRODUCT_DRAFT
    )
    contract_terms_id: str = Field(
        ..., description=THE_ID_OF_THE_CONTRACT_TERMS_ASSET
    )
    contract_terms: Optional[dict] = Field(
        None, description="Optional contract terms values to customize the template. If None, displays template defaults for review (first call). If empty dict {}, uses template defaults and attaches (second call). If provided with values, deep merges with template defaults and attaches."
    )


class CreateAndAttachCustomContractRequest(BaseModel):
    data_product_draft_id: str = Field(
        ..., description=THE_ID_OF_THE_DATA_PRODUCT_DRAFT
    )
    contract_terms_id: str = Field(
        ..., description=THE_ID_OF_THE_CONTRACT_TERMS_ASSET
    )
    contract_terms: Optional[dict] = Field(
        None, description="Custom contract terms values to create and attach to the data product. Must follow the exact nested structure from the schema. If None, the empty schema will be shown. If provided with values, the contract will be created and attached (empty dict not allowed for custom contracts)."
    )
    
    