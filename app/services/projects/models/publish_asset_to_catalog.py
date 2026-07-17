# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Optional

from app.shared.models import BaseResponseModel


class PublishAssetToCatalogRequest(BaseModel):
    asset: str = Field(
        ...,
        description="UUID or name of the asset to publish from the source project",
    )
    project: str = Field(
        ...,
        description="Project identifier (UUID or name) containing the source asset",
    )
    catalog: str = Field(
        ...,
        description="Catalog identifier (UUID or name) where the asset will be published",
    )


class PublishAssetToCatalogResponse(BaseResponseModel):
    message: Optional[str] = Field(
        None,
        description="Success message describing the publish operation",
    )
    asset_id: Optional[str] = Field(
        None,
        description="Unique identifier of the published asset in the target catalog",
    )
    asset_name: Optional[str] = Field(
        None,
        description="Name of the published asset in the target catalog",
    )
    catalog_id: Optional[str] = Field(
        None,
        description="Resolved target catalog identifier",
    )
    source_project_id: Optional[str] = Field(
        None,
        description="Resolved source project identifier",
    )
    source_asset_id: Optional[str] = Field(
        None,
        description="Unique identifier of the source asset in the project",
    )
    url: Optional[str] = Field(
        None,
        description="URL of the published asset in the target catalog",
    )

# Made with Bob
