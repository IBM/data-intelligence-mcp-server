from pydantic import BaseModel, Field
from typing import Optional, List

# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

class CreateProjectRequest(BaseModel):
    """Request model for creating a new project"""

    name: Optional[str] = Field(
        default=None, description="The name of the new project"
    )
    description: Optional[str] = Field(
        default="MCP generated project", description="A description for the new project"
    )
    type: Optional[str] = Field(
        default="df",
        description="The project type where the project is generated",
        examples=[
            "cpd: IBM Cloud Pak for Data (CPD) projects",
            "wx,df: IBM watsonx projects (wx) or Data Fabric (df)",
        ],
    )
    storage: Optional[str] = Field(
        default=None,
        description="Storage where the project stores",
        examples=[
            "Cloud Object Storage instance or resource crn value (bmcos_object_storage)",
            "assetfiles",
        ],
    )
    tags: Optional[List] = Field(
        default=[],
        description="List of user defined tags that are attached to the project",
    )


class CreateProjectResponse(BaseModel):
    name: str = Field(..., description="The project name which is created")
    location: str = Field(..., description="API to access the newly created project.")
