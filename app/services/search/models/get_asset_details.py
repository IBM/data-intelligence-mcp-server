from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class GetAssetDetailsRequest(BaseModel):
    asset: str = Field(..., description="UUID or name of the asset to retrieve the metadata for")
    catalog: Optional[str] = Field(None, description="Catalog identifier (UUID or name) in which the asset resides")
    project: Optional[str] = Field(None, description="Project identifier (UUID or name) in which the asset resides")

class AssetUsage(BaseModel):
    last_updated_at: str = Field(..., description="Timestamp asset was last updated at")
    last_updater_id: str = Field(..., description="ID of the user who last updated the asset")
    last_updater_name: str = Field(..., description="Name of the user who last updated the asset")
    last_updater_email: str = Field(..., description="Email of the user who last updated the asset")
    last_update_time: int = Field(..., description="Unix time asset was last updated at")
    last_accessed_at: str = Field(..., description="Timestamp asset was last accessed at")
    last_access_time: int = Field(..., description="Unix time asset was last accessed at")
    last_accessor_id: str = Field(..., description="ID of the user who last accessed the asset")
    last_accessor_name: str = Field(..., description="Name of the user who last accessed the asset")
    last_accessor_email: str = Field(..., description="Email of the user who last accessed the asset")
    access_count: int = Field(..., description="Number of times asset has been accessed")

class MemberRoles(BaseModel):
    user_iam_id: str = Field(..., description="IAM ID of a member of the asset")
    roles: Optional[List[str]] = Field(None, description="Roles attached to the corresponding member of the asset")

class Rov(BaseModel):
    mode: int = Field(..., description="ROV mode")
    collaborator_ids: Optional[List[str]] = Field(None, description="List of user IAM IDs of collaborators of the asset")
    member_roles: Optional[List[MemberRoles]] = Field(None, description="List of members and their roles of the asset")

class SourceAsset(BaseModel):
    action: Optional[str] = Field(None, description="Action of the source asset")
    catalog_id: Optional[str] = Field(None, description="Catalog identifier in which the source asset resides")
    project_id: Optional[str] = Field(None, description="Project identifier in which the source asset resides")
    space_id: Optional[str] = Field(None, description="Space identifier in which the source asset resides")
    asset_id: Optional[str] = Field(None, description="Unique id of the source asset")
    revision_id: Optional[int] = Field(None, description="Revision ID of the source asset")
    bss_account_id: Optional[str] = Field(None, description="BSS account ID of where the source asset resides")
    asset_name: str = Field(..., description="Name of the source asset")
    source_url: Optional[str] = Field(None, description="URL of the source asset")
    resource_key: Optional[str] = Field(None, description="Resource key of the source asset")
    identity_key: Optional[str] = Field(None, description="Identity key of the source asset")

class GetAssetDetailsResponse(BaseModel):
    usage: AssetUsage = Field(..., description="Information about asset usage and access")
    rov: Rov = Field(..., description="ROV information including asset collaborators and members")
    sub_container_id: Optional[str] = Field(None, description="Unique id of the sub container the asset resides in")
    is_linked_with_sub_container: bool = Field(..., description="Whether the asset is linked to a sub container or not")
    name: str = Field(..., description="Name of the asset")
    description: Optional[str] = Field(None, description="Description of the asset")
    tags: Optional[List[str]] = Field(None, description="Tags associated to the asset")
    asset_type: str = Field(..., description="Type of the asset")
    origin_country: Optional[str] = Field(None, description="Origin country of the asset")
    resource_key: str = Field(..., description="Resource key of the asset")
    identity_key: Optional[str] = Field(None, description="Identity key of the asset")
    delete_processing_state: Optional[Literal["pending", "complete", "failed"]] = Field(
        None,
        description="The state of the delete processing of the asset",
        examples=["pending", "complete", "failed"]
    )
    delete_reason: Optional[str] = Field(None, description="The reason for deletion of the asset")
    rating: float = Field(..., description="Rating of the asset")
    total_ratings: int = Field(..., description="Total number of ratings of the asset")
    catalog_id: Optional[str] = Field(None, description="Catalog identifier in which the asset resides")
    project_id: Optional[str] = Field(None, description="Project identifier in which the asset resides")
    space_id: Optional[str] = Field(None, description="Space identifier in which the asset resides")
    created: int = Field(..., description="Unix time asset was created at")
    created_at: str = Field(..., description="Timestamp asset was created at")
    owner_id: Optional[str] = Field(None, description="ID of the owner of the asset")
    owner_name: Optional[str] = Field(None, description="Name of the owner of the asset")
    owner_email: Optional[str] = Field(None, description="Email of the owner of the asset")
    size: int = Field(..., description="Size of the asset")
    version: float = Field(..., description="Version of the asset")
    asset_state: Literal["deleted", "available"] = Field(
        "available",
        description="The current state of the asset",
        examples=["deleted", "available"]
    )
    asset_attributes: Optional[List[str]] = Field(None, description="Attributes associated to the asset")
    asset_id: str = Field(..., description="Unique id of the asset")
    source_asset: Optional[SourceAsset] = Field(None, description="Metadata of the source asset associated to the asset")
    asset_category: Literal["SYSTEM", "USER"] = Field(
        "USER",
        description="The category of the asset",
        examples=["SYSTEM", "USER"]
    )
    revision_id: Optional[int] = Field(None, description="Revision ID of the asset")
    number_of_shards: Optional[int] = Field(None, description="Number of shards of the asset")
    creator_id: str = Field(..., description="ID of the creator of the asset")
    creator_name: str = Field(..., description="Name of the creator of the asset")
    creator_email: str = Field(..., description="Email of the creator of the asset")
    is_branched: Optional[bool] = Field(None, description="Whether the asset is branched or not")
    set_id: Optional[str] = Field(None, description="Set ID of the asset")
    is_managed_asset: bool = Field(..., description="Whether the asset is a managed asset or not")
    entity: Optional[dict] = Field(None, description="Entity information of the asset including asset type, column information etc.")
