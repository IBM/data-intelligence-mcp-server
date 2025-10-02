from pydantic import BaseModel, Field
from typing import List


class AssetFromCatalog(BaseModel):
    name: str = Field(..., description="The name of the asset from catalog.")
    asset_id: str = Field(..., description="The ID of the asset from catalog.")
    catalog_id_of_asset_id: str = Field(
        ..., description="The catalog ID of the asset from catalog."
    )


class GetAssetsFromCatalogResponse(BaseModel):
    message: str = Field(
        ..., description="A message showing the number of assets found in the catalog."
    )
    assets: List[AssetFromCatalog] = Field(
        ..., description="A List of assets from the catalog."
    )
