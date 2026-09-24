# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from abc import abstractmethod
from typing import Dict, Any, cast, Optional, List
from app.services.internal.glossary_generation.utils.constants import (
    LOCK_FILE,
    PROCESSED_DOCUMENTS_JSON,
    REVIEW_CATEGORIES_CSV,
    REVIEW_TERMS_CSV
    )
from app.shared.storage.file_handler import FileHandler
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.utils.retry_utils import retry_on_failure
import asyncio
import os


class BaseFileHandler(FileHandler):
    """
    Base implementation class providing common functionality for file handlers.
    
    This class implements the CAMS logic that is common across all storage backends, 
    while delegating storage-specific operations to child classes through abstract methods.
    
    Architecture:
    -------------
    FileHandler (ABC) - Public interface
        ↓
    BaseFileHandler - CAMS logic implementation + storage abstractions
        ↓
    COSHandler / AssetFilesHandler - Storage-specific implementations
    
    Separation of Concerns:
    -----------------------
    - BaseFileHandler: Handles CAMS asset lifecycle (create, read, update, delete)
    - Child classes: Handle storage-specific file operations (COS buckets, Asset Files API)
    
    Abstract Methods (must be implemented by child classes):
    --------------------------------------------------------
    - _verify_storage_file_deleted(): Check if file exists in storage
    - _delete_file_from_storage(): Delete file from storage backend
    
    Subclasses must implement both storage-specific abstract methods.
    """

    @abstractmethod
    async def _verify_storage_file_exists(self, object_key: str) -> bool:
        """
        Verify that a file exists in the underlying storage.
        
        This is an internal method used by the deletion workflow to confirm
        that files have been removed from the storage backend. Each storage
        implementation must provide its own verification logic.
        
        Args:
            object_key: The storage path/key of the file to verify
            
        Returns:
            bool: True if file is confirmed deleted, False if still exists
            
        Raises:
            ServiceError: If storage check fails (not including file not found)
        """
        pass

    @abstractmethod
    async def _delete_file_from_storage(self, project_id: str, object_key: str) -> None:
        """
        Delete a file from the underlying storage backend.
        
        This is an internal method called after CAMS asset deletion to remove
        the physical file from storage. Each storage implementation must provide
        its own deletion logic using the appropriate API endpoint.
        
        Storage-Specific Endpoints:
        ---------------------------
        - AssetFilesHandler: DELETE /v2/asset_files/{path}
        - COSHandler: DELETE /{Bucket}/{Key}
        
        Args:
            project_id: Project ID (used by Asset Files, not needed for COS)
            filename: Name of the file to delete (e.g., "lock.txt")
            
        Raises:
            ServiceError: If deletion fails (excluding file not found/already deleted)
        """
        pass

    async def _poll_storage_file_condition(
        self,
        object_key: str,
        expect_exists: bool,
        max_attempts: int = 10,
        initial_delay: float = 1,
        max_delay: float = 30
    ) -> bool:
        """
        Poll storage to verify file existence state from expect_exists value with exponential backoff.
        
        Args:
            object_key: Name/Path of the file to check
            expect_exists: True to wait for file to exist, False to wait for deletion
            max_attempts: Maximum number of polling attempts (default: 10)
            initial_delay: Initial delay between attempts in seconds (default: 1)
            max_delay: Maximum delay between attempts in seconds (default: 30)
            
        Returns:
            True if expected condition is met within max attempts, False otherwise
        """
        delay = initial_delay
        condition_name = "exists" if expect_exists else "deleted"
        LOGGER.info(f"Verifying storage file {condition_name} for {object_key}")
        
        for attempt in range(1, max_attempts + 1):
            try:
                file_exists = await self._verify_storage_file_exists(object_key)
                condition_met = file_exists if expect_exists else not file_exists
                
                if condition_met:
                    LOGGER.info(f"Storage file {object_key} {condition_name} after {attempt} attempt(s)")
                    return True
                
                LOGGER.info(f"Storage file {object_key} not yet {condition_name}, attempt {attempt}/{max_attempts}")
                
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
                
            except Exception as e:
                LOGGER.error(f"Error verifying storage file {object_key} {condition_name}: {e}")
                # Continue retrying on errors
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)
        
        LOGGER.warning(f"Storage file {object_key} not {condition_name} after {max_attempts} attempts")
        return False

    async def _get_cams_asset_id(self, project_id: str, object_key: str) -> Optional[str]:
        """
        Check if a CAMS asset already exists for the given object_key.
        
        Args:
            project_id: Project ID to search in
            object_key: Name/Path of the file/asset to search for
            
        Returns:
            Asset ID if found, None otherwise
        """
        
        filename = os.path.basename(object_key)
        LOGGER.info(f"Searching for CAMS asset with filename: {filename} with object_key: {object_key}")
        
        try:
            search_url = f"{tool_helper_service.base_url}/v2/asset_types/asset/search"

            payload = {
                "query": f"asset.name:{filename}",
                "limit": 10000
                }

            params = {"project_id": project_id}
            search_response = cast(Dict[str, Any], await tool_helper_service.execute_post_request(
                url=search_url,
                json=payload,
                params=params
            ))
            results = search_response.get("results")
            LOGGER.info(f"CAMS search returned {len(results) if results else 0} results")

            if results:
                asset_id = next((result.get("metadata", {}).get("asset_id") for result in results if result.get("metadata", {}).get("name") == filename), None)

                if asset_id:
                    LOGGER.info(f"Found existing CAMS asset for filename {filename}, for object_key {object_key} and asset_id {asset_id}")
                    return asset_id
                else:
                    LOGGER.info(f"No CAMS asset matched filename: {filename} and object_key {object_key}")
                    return None
            else:
                LOGGER.warning(f"No results found for filename {filename} and object_key {object_key}")
            return None
        except Exception as e:
            LOGGER.warning(f"Error checking for existing CAMS asset for {object_key}: {e}")
            raise ServiceError(f"Error finding file {filename}: {e}")

    @retry_on_failure(max_retries=5, backoff_factor=2.0)
    async def _create_cams_asset(self, project_id: str, object_key: str, mime_type: str) -> None:
        """
        Create a new CAMS asset and attach it to the project.
        
        Args:
            project_id: Project ID where the asset should be created
            filename: Name of the file/asset
            object_key: Object key for the attachment
            mime_type: MIME type of the file
        """

        filename = os.path.basename(object_key)
        LOGGER.info(f"Creating CAMS asset with filename: {filename}, object_key: {object_key} and mime_type: {mime_type}")
        
        create_cams_asset_payload = {
            "metadata": {
                "project_id": project_id,
                "name": filename,
                "asset_type": "data_asset",
                "asset_attributes": ["data_asset"],
                "asset_category": "USER"
            },
            "entity": {
                "data_asset": {
                "dataset": False,
                "mime_type": mime_type
                }
            },
            "attachments": [
                {
                    "object_key": object_key,
                    "object_key_is_read_only": False,
                    "mime": mime_type,
                    "asset_type": "data_asset",
                    "name": filename,
                    "description": ""
                }
            ]
        }
        
        await tool_helper_service.execute_post_request(
            url=f"{tool_helper_service.base_url}/v2/assets?project_id={project_id}&duplicate_action=IGNORE",
            json=create_cams_asset_payload
        )

        cams_asset_exists = await self._poll_cams_asset_condition(
            project_id=project_id,
            object_key=object_key,
            expect_exists=True
        )

        if not cams_asset_exists:
            raise ServiceError(f"Unable to create the CAMS asset for object_key {object_key} in storage after 10 attempts")

        LOGGER.info(f"CAMS asset created successfully with object_key: {object_key}, filename: {filename}")

    async def _get_cams_asset(self, project_id: str, asset_id: str) -> Dict[str, Any]:

        cams_url = f"{tool_helper_service.base_url}/v2/assets/{asset_id}"
        params = {"project_id": project_id}

        response = cast(Dict[str, Any], await tool_helper_service.execute_get_request(
            url=cams_url,
            params=params
        ))

        return response
    
    def _extract_attachment_id(self, cams_asset: Dict[str, Any], object_key: str) -> str:
        attachments = cams_asset.get("attachments", [])
        matching_attachment = None
        for attachment in attachments:
            LOGGER.info(f"Found attachment for CAMS asset with object_key {object_key}")
            if attachment.get("object_key", "") == object_key:
                matching_attachment = attachment
                break

        if not matching_attachment:
            LOGGER.error(f"No attachment found for {object_key}")
            raise ServiceError(f"Unable to find the attachment id for the CAMS asset for the file: {object_key}")

        attachment_id = matching_attachment.get("id")
        if not attachment_id:
            LOGGER.error(f"No attachment_id found for {object_key}")
            raise ServiceError(f"Unable to find the attachment id for the CAMS asset for the file: {object_key}")
        
        return attachment_id

    async def _patch_cams_asset_attachment(
        self,
        project_id: str,
        object_key: str,
        new_size: int,
        existing_asset_id: str
    ) -> None:
        """
        Update CAMS asset attachment metadata with new file size.
        
        This method finds the CAMS asset by filename and updates its
        attachment metadata with the new file size after upload.
        
        Args:
            project_id: Project ID where the asset exists
            filename: Name of the file/asset
            new_size: New size of the file in bytes
            
        Raises:
            Exception: If asset or attachment cannot be found or updated
        """
        try:
            LOGGER.info(f"Start patching CAMS asset attachment for: {object_key}")

            cams_asset = await self._get_cams_asset(project_id, existing_asset_id)
            attachment_id = self._extract_attachment_id(cams_asset, object_key)
            # Patch the attachment with new size
            patch_url = f"{tool_helper_service.base_url}/v2/assets/{existing_asset_id}/attachments/{attachment_id}"
            
            LOGGER.info(f"About to patch CAMS asset with asset_id {existing_asset_id} and attachment_id {attachment_id}")
            await tool_helper_service.execute_patch_request(
                url=patch_url,
                params={"project_id": project_id},
                json=[{"op": "replace", "path": "/size", "value": new_size}]
            )
            
            LOGGER.info(f"Successfully patched CAMS asset attachment for {object_key} with size {new_size}")
            
        except Exception as e:
            # Log error but don't fail the entire process
            LOGGER.error(f"Error patching CAMS asset attachment for {object_key}: {e}")
            raise ServiceError(f"Unable to patch CAMS asset for file {object_key}")
    
    async def _poll_cams_asset_condition(
        self,
        project_id: str,
        object_key: str,
        expect_exists: bool = True,
        max_attempts: int = 10,
        initial_delay: float = 0.5,
        max_delay: float = 5.0
    ) -> bool:
        """
        Poll for CAMS asset existence/non-existence with exponential backoff.
        
        This method repeatedly checks whether a CAMS asset exists or doesn't exist,
        using exponential backoff between attempts. It's useful for waiting for
        asynchronous operations to complete (e.g., asset creation or deletion).
        
        Args:
            project_id: Project ID where the asset is located
            filename: Name/Path of the file/asset to check
            expect_exists: If True, wait for asset to exist. If False, wait for asset to not exist.
            max_attempts: Maximum number of polling attempts (default: 10)
            initial_delay: Initial delay between attempts in seconds (default: 0.5)
            max_delay: Maximum delay between attempts in seconds (default: 5.0)
            
        Returns:
            True if the expected condition is met (asset exists/doesn't exist as expected),
            False if the condition is not met after max attempts
            
        Raises:
            ServiceError: If there's an error during polling (other than not found)
        """
        delay = initial_delay
        condition_name = "exists" if expect_exists else "deleted"
        
        LOGGER.info(f"Verifying CAMS asset {condition_name} for {object_key}")
        
        for attempt in range(1, max_attempts + 1):
            # Determine if asset was found
            found = False
            try:
                asset_id = await self._get_cams_asset_id(project_id, object_key)
                found = asset_id is not None
            except ServiceError as e:
                if "not found" in str(e).lower() or "404" in str(e):
                    found = False
                else:
                    # Other error - re-raise
                    raise
            
            # Check if condition is met based on found status and expectation
            condition_met = found if expect_exists else not found
            
            if condition_met:
                LOGGER.info(f"CAMS asset {object_key} {condition_name} after {attempt} attempt(s)")
                return True
            
            # Condition not met, log and wait before next attempt
            LOGGER.info(f"CAMS asset {object_key} not yet {condition_name}, attempt {attempt}/{max_attempts}")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
        
        # Max attempts reached without meeting condition
        LOGGER.warning(f"CAMS asset {object_key} condition not met after {max_attempts} attempts (expected: {condition_name})")
        return False

    async def _delete_cams_asset(self, project_id: str, asset_ids: List[Optional[str]], object_key: str) -> None:
        """
        Delete CAMS assets by their IDs.
        
        Args:
            project_id: Project ID where assets are located
            asset_ids: List of asset IDs to delete (may contain None values which will be filtered)
        """
        # Filter out None values to prevent TypeError in join operation
        valid_asset_ids = [aid for aid in asset_ids if aid is not None]
        
        if not valid_asset_ids:
            LOGGER.info("No valid asset IDs to delete (all were None)")
            return

        delete_cams_url = f"{tool_helper_service.base_url}/v2/assets/bulk"
        
        try:
            await tool_helper_service.execute_delete_request(
                url=delete_cams_url,
                params={"project_id": project_id, "asset_ids": ",".join(valid_asset_ids), "purge_on_delete": True},
            )

            cams_deleted = await self._poll_cams_asset_condition(
                project_id=project_id,
                object_key=object_key,
                expect_exists=False
                )
            
            if not cams_deleted:
                raise ServiceError(f"Unable to delete the {object_key} in CAMS after 10 attempts")

            LOGGER.info("Asset(s) were successfully deleted")
        except ServiceError as e:
            if "404" in str(e):
                LOGGER.warning(f"Asset(s) not found (404) during deletion attempt: {valid_asset_ids}. This may indicate the asset(s) were already deleted.")
            else:
                raise
    
    async def _populate_project(self, project_id: str, object_key: str, filesize: int, mime_type: str = "application/json") -> None:
        """
        Create or update CAMS asset for a file in the project.
        
        If the asset already exists, only patch the attachment with the current file size.
        If it doesn't exist, create a new asset and attachment.
        
        Args:
            project_id: Project ID where the asset should exist
            object_key: Name of the file/asset or path
            filesize: Size of the file in bytes
            mime_type: MIME type of the file
            
        Returns:
            Asset ID of the created or existing asset
        """
        LOGGER.info(f"Populating the projects CAMS assets for project_id: {project_id}, object_key: {object_key}, mime_type: {mime_type}")
        
        # Check if asset already exists
        existing_asset_id = await self._get_cams_asset_id(project_id, object_key)

        if existing_asset_id is not None:
            LOGGER.info(f"CAMS asset already exists for {object_key}, patching attachment only")
            await self._patch_cams_asset_attachment(project_id, object_key, filesize, existing_asset_id)

            # If the patch was applied to glossary-tool-processed-documents.json, then the CSVs should be deleted as they are out of sync
            if PROCESSED_DOCUMENTS_JSON in object_key:
                LOGGER.info(f"{PROCESSED_DOCUMENTS_JSON} exists, deleting existing CSVs")
                category_csv_asset_id = await self._get_cams_asset_id(project_id, REVIEW_CATEGORIES_CSV)
                term_csv_asset_id = await self._get_cams_asset_id(project_id, REVIEW_TERMS_CSV)
                
                # If the CSVs exist, delete them
                if category_csv_asset_id is not None or term_csv_asset_id is not None:
                    await self._delete_cams_asset(project_id, [category_csv_asset_id, term_csv_asset_id], object_key=object_key)
                    await self._delete_file_from_storage(project_id, REVIEW_CATEGORIES_CSV)
                    await self._delete_file_from_storage(project_id, REVIEW_TERMS_CSV)
        
        else:
            LOGGER.info(f"No existing CAMS asset found, will create new asset for object_key: {object_key}")
            await self._create_cams_asset(project_id, object_key, mime_type)
    
    async def _delete_cams_lock_file(self, project_id: str, object_key: str) -> None:
        LOGGER.info(f"Preparing to delete CAMS Asset for {LOCK_FILE} file with object_key: {object_key}")
    
        # Check if CAMS asset exists and delete it
        existing_asset_id = await self._get_cams_asset_id(project_id, object_key)
        
        if existing_asset_id is not None:
            LOGGER.info(f"CAMS asset exists for {object_key}, deleting asset_id: {existing_asset_id}")
            await self._delete_cams_asset(project_id, [existing_asset_id], object_key=object_key)
        else:
            LOGGER.info(f"No CAMS asset found for lock file with object_key: {LOCK_FILE}")
