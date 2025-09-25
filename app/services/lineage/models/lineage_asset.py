# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.
from typing import Optional
from pydantic import BaseModel, Field


class LineageAsset(BaseModel):
    """Lineage asset model"""

    id: str = Field(..., description="Unique id of the asset")
    name: str = Field(..., description="Name of the asset")
    type: str = Field(..., description="Type of the asset")
    identity_key: Optional[str] = Field(None, description="Identity key of the asset")
    resource_key: Optional[str] = Field(None, description="Resource key of the asset")
