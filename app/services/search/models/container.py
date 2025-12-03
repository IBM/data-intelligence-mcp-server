# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

from enum import StrEnum
from pydantic import BaseModel, Field
from typing import Optional, List


class ContainerType(StrEnum):
    """Enum for container types"""
    CATALOG = "catalog"
    PROJECT = "project"
    SPACE = "space"
    ALL = "all"
    CATALOG_AND_PROJECT = "catalog,project"
    PROJECT_AND_CATALOG = "project,catalog"


class Container(BaseModel):
    """Container model representing a catalog, project, or space"""
    id: str = Field(..., description="Unique identifier of the container")
    name: str = Field(..., description="Name of the container")
    type: ContainerType = Field(..., description="Type of the container (catalog, project, or space)")
    url: Optional[str] = Field(None, description="URL to access the container in the UI")


class ListContainersRequest(BaseModel):
    """Request model for listing containers"""
    container_type: ContainerType = Field(
        default=ContainerType.ALL,
        description="Type of container to list - 'project', 'catalog', 'space', or 'all'. Defaults to 'all'."
    )


class ListContainersResponse(BaseModel):
    """Response model for listing containers"""
    containers: List[Container] = Field(..., description="List of containers")
    total_count: int = Field(..., description="Total number of containers returned")
    container_type: ContainerType = Field(..., description="Type of containers listed")


class FindContainerRequest(BaseModel):
    """Request model for finding a container"""
    container_id_or_name: str = Field(
        ..., 
        description="The ID or name of the container to find"
    )
    container_type: ContainerType = Field(
        default=ContainerType.CATALOG,
        description="The type of the container - 'project', 'catalog', or 'space'. Defaults to 'catalog'"
    )


class FindContainerResponse(BaseModel):
    """Response model for finding a container"""
    container: Container = Field(..., description="The found container")
