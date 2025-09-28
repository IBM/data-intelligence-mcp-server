from pydantic import BaseModel, Field
from typing import Optional, List

class SearchAssetRequest(BaseModel):
    """Request model for searching assets."""

    search_prompt: str = Field(..., description="The search prompt from the user about data assets potentially with additional searching details")
    container_type: Optional[str] = Field(
        default="catalog",
        description="The container type in which to search assets, defaults to catalog",
        examples=["catalog", "project"]
    )

class SearchAssetResponse(BaseModel):
    """Search assets response model"""
    id: str = Field(..., description="Unique id of the asset")
    name: str = Field(..., description="Name of the asset")
    catalog_id: Optional[str] = Field(None, description="Catalog identifier in which the asset resides")
    project_id: Optional[str] = Field(None, description="Project identifier in which the asset resides")
    url: str = Field(...,description="URL of the asset")

class SearchAssetListResponse(BaseModel):
    assets: List[SearchAssetResponse]
    total_count: int
    search_prompt: str
    container_type: str = "catalog"
