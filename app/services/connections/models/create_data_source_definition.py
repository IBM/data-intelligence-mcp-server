# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Optional

class CreateDataSourceDefinitionRequest(BaseModel):
    name: str = Field(..., description="Name of the data source definition.")
    datasource_type: str = Field(..., description="Datasource type name or UUID.")
    hostname: str = Field(..., description="Hostname/IP address of the data source definition.")
    port: str = Field(..., description="Connection port number of the hostname of the data source definition.")
    physical_collection: Optional[str] = Field(default=None, description="Database name or bucket name")
    description: Optional[str] = Field(default=None, description="Purpose and owner information")
    tags: Optional[list[str]] = Field(default=None, description="Tags for categorization")

class CreateDataSourceDefinitionResponse(BaseResponseModel):
    dsd_id: str = Field(..., description="Unique id of the newly created data source definition")
    name: str = Field(..., description="Name of the newly created data source definition")
    datasource_type_name: str = Field(default=..., description="Name of the data source type of data source definition")
    endpoint: dict = Field(..., description="Endpoint information for accessing the data source definition")
    url: str = Field(..., description="URL to access the data source definition in the UI")
