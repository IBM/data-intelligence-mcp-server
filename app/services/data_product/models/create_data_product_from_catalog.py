from pydantic import BaseModel, Field


class CreateDataProductFromCatalogRequest(BaseModel):
    name: str = Field(description="The name of the data product.")
    asset_id: str = Field(
        description="The ID of the asset selected from catalog to be added to the data product."
    )
    catalog_id_of_asset_id: str = Field(
        description="The ID of the catalog that the asset selected is part of."
    )


class CreateDataProductFromCatalogResponse(BaseModel):
    data_product_draft_id: str = Field(
        ..., description="The ID of the data product draft created."
    )
    contract_terms_id: str = Field(
        ...,
        description="The ID of the contract terms of the data product draft created.",
    )
    create_data_product_response: dict = Field(
        ..., description="The Create Data Product API response."
    )