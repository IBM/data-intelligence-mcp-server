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
    tags: list[str] = Field([], description="List of tags")
    identity_key: Optional[str] = Field(..., description="Asset identity key")
    parent_name: Optional[str] = Field(None, description="Name of the parent asset")
    parent_type: Optional[str] = Field(None, description="Type of the parent asset")


class QualityScore(BaseModel):
    """Quality score model"""

    operator: str
    value: str
