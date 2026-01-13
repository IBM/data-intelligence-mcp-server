from pydantic import BaseModel, Field
from typing import Optional, Literal

class SearchConnectionRequest(BaseModel):
    container: Optional[str] = Field(None, description="Name or UUID of the project or catalog to search the connection within.")
    container_type: Optional[Literal["catalog", "project"]] = Field(None, description="The container type in which to search connections")
    connection_name: Optional[str] = Field(None, description="Name of the connection to filter the connections by.")
    datasource_type: Optional[str] = Field(None, description="Datasource type name or UUID to filter connections by.")
    creator: Optional[str] = Field(None, description="Name, username, or ID of the creator of connection to filter connections by.")

class SearchConnectionResponse(BaseModel):
    id: str = Field(..., description="Unique id of the connection.")
    name: str = Field(..., description="Name of the connection.")
    url: str = Field(..., description="URL pointing to the connection.")
    create_time: str = Field(..., description="Time the connection was created at.")
    creator_id: str = Field(..., description="Id of the user who created the connection.")
    datasource_type_id: str = Field(..., description="Unique id of the data source type of the connection.")
    datasource_type_name: str = Field(..., description="Name of the data source type of the connection.")
    container_id: str = Field(..., description="Unique id of the container in which the connection resides in.")
    container_type: str = Field(..., description="Type of the container in which the connection resides in.")
