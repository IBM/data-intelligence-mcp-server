from pydantic import BaseModel, Field
from typing import List, Literal


class Asset(BaseModel):
    id: str = Field(..., description="The ID of the asset.")
    name: str = Field(..., description="The name of the asset.")
    catalog_id: str | None = Field(
        default=None, description="The catalog ID of the asset."
    )
    project_id: str | None = Field(
        default=None, description="The project ID of the asset."
    )

class GetAssetsFromContainerRequest(BaseModel):
    container_type: Literal["catalog", "project"] = Field(
        ..., description="Where to search - either 'project' or 'catalog'. This is a mandatory field."
    )

class GetAssetsFromContainerResponse(BaseModel):
    message: str = Field(
        ..., description="A message showing the number of assets found in the catalog."
    )
    assets: List[Asset] = Field(
        ..., description="A List of assets from the catalog."
    )
