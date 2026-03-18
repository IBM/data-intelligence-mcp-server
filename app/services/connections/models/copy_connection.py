# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.shared.models import BaseResponseModel

class CopyConnectionRequest(BaseModel):
    connection_name: str = Field(..., description="Name of the existing connection to copy.")
    source_container: Optional[str] = Field(None, description="Name or UUID of the project or catalog that contains the connection to copy.")
    source_container_type: Optional[Literal["catalog", "project"]] = Field(None, description="The container type of the source container.")
    target_container: str = Field(..., description="Name or UUID of the project or catalog to copy the connection to.")
    target_container_type: Optional[Literal["catalog", "project"]] = Field(None, description="The container type of the target container.")

class CopyConnectionResponse(BaseResponseModel):
    id: str = Field(..., description="Unique id of the new connection.")
    name: str = Field(..., description="Name of the new connection.")
    create_time: str = Field(..., description="Time the connection was created at or copied.")
    creator_id: str = Field(..., description="Id of the user who copied the connection.")
