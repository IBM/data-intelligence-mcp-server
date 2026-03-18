# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from pydantic import BaseModel, Field
from app.shared.models import BaseResponseModel
from typing import Optional

class SearchDataSourceDefinitionRequest(BaseModel):
    name: Optional[str] = Field(None, description="Name of the data source definition to search for.")
    datasource_type: Optional[str] = Field(None, description="Datasource type name or UUID to filter data source definitions by.")
    hostname: Optional[str] = Field(None, description="Hostname/IP address of the data source to filter data source definitions by.")
    port: Optional[str] = Field(None, description="Port number of the hostname of the data source to filter data source definitions by.")
    physical_collection: Optional[str] = Field(None, description="Database name, bucket name, or project ID of the data source to filter data source definitions by.")

class SearchDataSourceDefinitionResponse(BaseResponseModel):
    id: str = Field(..., description="Unique id of the data source definition")
    name: str = Field(..., description="Name of the data source definition")
    create_time: str = Field(..., description="Time data source definition was created at")
    creator_id: str = Field(..., description="Id of the user who created the data source definition")
    datasource_type_id: str = Field(..., description="Unique id of the data source type of data source definition")
    datasource_type_name: str = Field(..., description="Name of the data source type of data source definition")
