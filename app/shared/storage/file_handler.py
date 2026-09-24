# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, Awaitable
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER

__all__ = ['FileHandler', 'create_file_handler', 'LOGGER']

class FileHandler(ABC):
    """
    Abstract base class for file storage handlers.
    
    This interface defines the contract for file storage operations used by
    the glossary generation tool. Implementations can provide different storage
    backends (e.g., Cloud Object Storage, local file system, S3, Azure Blob Storage).
    
    The interface enforces four core operations:
    1. Retrieving documents from storage
    2. Retrieving merged profile data
    3. Uploading merged profile data
    4. Uploading CSV files
    """

    @abstractmethod
    async def get_documents(self) -> Dict[str, Any]:
        """
        Get all documents from the storage backend.
        
        This method retrieves all available documents from the configured storage
        location. Documents are returned as a dictionary mapping filenames to content.
        
        Returns:
            Dict[str, Any]: Dictionary mapping document filenames to their content:
                - key (str): Document filename/key
                - value (Any): Document content (typically bytes or dict)
                
        Raises:
            ValueError: If no documents are found in the storage location
            ServiceError: If storage operations fail
        """
        pass

    @abstractmethod
    async def get_merged_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get merged profile JSON from storage.
        
        The merged profile contains consolidated metadata about all processed
        documents. This method retrieves the profile if it exists, or returns
        None if no profile has been created yet.
        
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing the merged profile data,
                or None if the profile file doesn't exist
                
        Raises:
            ServiceError: If storage operations fail (excluding file not found)
        """
        pass

    @abstractmethod
    async def upload_merged_profile(
        self,
        merged_profiles: Dict[str, Any],
        project_id: str
    ) -> None:
        """
        Upload merged profiles document to storage.
        
        This method stores the consolidated profile data for all processed documents.
        The profile is used to track which documents have been analyzed and their
        extracted metadata.
        
        Args:
            merged_profiles: Dictionary containing merged profile data with structure:
                {
                    "profiles": [
                        {
                            "document_name": str,
                            "metadata": dict,
                            ...
                        },
                        ...
                    ]
                }
            project_id: Project ID for asset management and tracking
        
        Raises:
            ServiceError: If merged_profiles is empty or storage operations fail
        """
        pass

    @abstractmethod
    async def upload_csv_file(
        self,
        content: bytes,
        filename: str,
        project_id: str
    ) -> None:
        """
        Upload CSV file to storage.
        
        This method stores CSV files (typically categories and glossary terms)
        generated during the glossary creation process.
        
        Args:
            content: CSV file content as bytes
            filename: Name of the file to upload (e.g., "categories.csv")
            project_id: Project ID for asset management and tracking
        
        Raises:
            ValueError: If content is empty or filename is invalid
            ServiceError: If storage operations fail
        """
        pass

    @abstractmethod
    async def delete_lock_file(
        self, 
        project_id: str
    ) -> None:
        pass

    @abstractmethod
    async def upload_lock_file(
        self,
        project_id: str,
    ) -> None:
        pass

def create_file_handler(
    storage_details: Dict[str, Any], 
    project_id: str,
    credential_refresh_callback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None
) -> "FileHandler":
    """
    Factory function to create the appropriate file handler based on storage type.
    
    Supports multiple storage backends:
    - bmcos_object_storage: IBM Cloud Object Storage (SaaS)
    - amazon_s3: Amazon S3 storage (AWS)
    - assetfiles: Direct asset files storage
        
    Args:
        storage_details: Dictionary containing storage configuration with 'type' field
        project_id: Project ID for asset management
        credential_refresh_callback: Optional async callback to refresh S3 credentials.
                                     Only used by S3Handler, ignored by other handlers.
        
    Returns:
        FileHandler: Instance of the appropriate file handler (COSHandler, S3Handler, or AssetFilesHandler)
        
    Raises:
        ServiceError: If storage type is not supported
    """
    from app.shared.storage.cos_handler import COSHandler
    from app.shared.storage.s3_handler import S3Handler
    from app.shared.storage.asset_files_handler import AssetFilesHandler

    storage_type = storage_details.get("type", "")

    if storage_type == "bmcos_object_storage":
        LOGGER.info("Creating COSHandler for IBM Cloud Object Storage")
        return COSHandler(storage_details)
    elif storage_type == "amazon_s3":
        LOGGER.info("Creating S3Handler for Amazon S3 storage")
        # Only S3Handler receives the credential_refresh_callback
        return S3Handler(storage_details, project_id, credential_refresh_callback)
    elif storage_type == "assetfiles":
        LOGGER.info("Creating AssetFilesHandler for direct asset files")
        return AssetFilesHandler(project_id)
    else:
        raise ServiceError(f"Unsupported storage type: {storage_type}. Supported types: bmcos_object_storage, amazon_s3, assetfiles")
