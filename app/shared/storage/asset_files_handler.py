# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Dict, Any, Optional, cast
import json
from app.services.internal.glossary_generation.utils.constants import LOCK_FILE, PROCESSED_DOCUMENTS_JSON
from app.shared.storage.base_file_handler import BaseFileHandler
from app.shared.logging import LOGGER
from app.shared.utils.tool_helper_service import tool_helper_service
from app.shared.exceptions.base import ServiceError, ExternalAPIError
from urllib.parse import quote
import os
from app.shared.utils.retry_utils import retry_on_failure

NOT_FOUND_ERROR = "not found"

class AssetFilesHandler(BaseFileHandler):
   
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id

    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ExternalAPIError,))
    async def get_documents(self) -> Dict[str, Any]:

        LOGGER.info(f"Fetching asset files list for project_id: {self.project_id}")

        response = await tool_helper_service.execute_get_request(
            url=f"{tool_helper_service.base_url}/v2/asset_files/data_asset",
            params={"project_id": self.project_id},
            tool_name="create_glossary_from_files",
        )

        resources = response.get("resources", []) if isinstance(response, dict) else []

        file_resources = [resource for resource in resources if resource.get("type") == "file"]

        if not file_resources:
            LOGGER.warning(f"No file resources found in asset files for project_id: {self.project_id}")
            return {}

        LOGGER.info(f"Found {len(file_resources)} file resource(s) in asset files")
        return await self._get_each_file_from_asset_files(self.project_id, file_resources)
    
    async def _get_each_file_from_asset_files(
        self,
        project_id: str,
        file_resources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        results: Dict[str, Any] = {}

        for resource in file_resources:
            path = resource.get("path", "")
            encoded_path = quote(path, safe='/')
            file_url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded_path}"
            filename = os.path.basename(path)

            LOGGER.info(f"Downloading asset file: {path}")

            file_response = await tool_helper_service.execute_get_request(
                url=file_url,
                params={"project_id": project_id},
                tool_name="create_glossary_from_files",
            )

            content = (
                file_response.get("content", file_response)
                if isinstance(file_response, dict)
                else file_response
            )
            
            results[filename] = content
            LOGGER.info(f"Successfully downloaded asset file: {path}")

        return results
    
    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ExternalAPIError,))
    async def get_merged_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get merged profile JSON from asset files.
        
        Uses a lightweight existence check before attempting to fetch the file to avoid
        404 errors that can cause issues in MCP server environments.
        
        Returns:
            Dictionary containing the merged profile data, or None if file doesn't exist
        """
        path = f"data_asset/{PROCESSED_DOCUMENTS_JSON}"
        encoded_path = quote(path, safe='/')
        file_url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded_path}"
        
        # LAYER 1: Check if file exists using lightweight verification
        # This prevents 404 errors from occurring in the first place
        LOGGER.info(f"Checking if {PROCESSED_DOCUMENTS_JSON} exists in asset files")
        file_exists = await self._verify_storage_file_exists(path)
        
        if not file_exists:
            LOGGER.info(f"{PROCESSED_DOCUMENTS_JSON} not found in asset files - will perform full processing")
            return None
        
        # LAYER 2: File exists, fetch it with exception handling as backup
        try:
            LOGGER.info(f"Downloading asset file: {PROCESSED_DOCUMENTS_JSON}")

            file_response = cast(Dict[str, Any], await tool_helper_service.execute_get_request(
                url=file_url,
                params={"project_id": self.project_id},
                tool_name="create_glossary_from_files",
            ))

            content = (
                file_response.get("content", file_response)
                if isinstance(file_response, dict)
                else file_response
            )
            
            LOGGER.info(f"Successfully downloaded asset file: {PROCESSED_DOCUMENTS_JSON}")
            return content
        
        except Exception as e:
            # Backup: Handle 404 if it somehow occurs despite existence check (race condition)
            error_str = str(e).lower()
            if "404" in error_str or NOT_FOUND_ERROR in error_str:
                LOGGER.warning(
                    f"{PROCESSED_DOCUMENTS_JSON} disappeared between existence check and fetch - "
                    f"will perform full processing"
                )
                return None
            
            # Handle JSON parsing errors specifically
            json_error_patterns = [
                "expecting", "delimiter", "unterminated", "invalid",
                "jsondecode", "extra data", "control character"
            ]
            is_json_error = any(pattern in error_str for pattern in json_error_patterns)
            
            if is_json_error:
                raise ServiceError(
                    f"The file '{PROCESSED_DOCUMENTS_JSON}' contains invalid JSON and cannot be parsed. "
                    f"Parsing error: {str(e)}. "
                    f"To fix this issue: Delete the corrupted '{PROCESSED_DOCUMENTS_JSON}' file from the project "
                    f"and re-run the tool in 'process' mode to regenerate it."
                ) from e
            
            # For other errors, raise
            error_msg = f"Error downloading merged profile from project: {e}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
    
    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def upload_merged_profile(
        self,
        merged_profiles: Dict[str, Any],
        project_id: str
    ) -> None:

        if not merged_profiles:
            raise ServiceError(f"The intermediate file {PROCESSED_DOCUMENTS_JSON} is empty")
        
        # Upload to asset files
        object_key = f"data_asset/{PROCESSED_DOCUMENTS_JSON}"
        encoded_path = quote(object_key, safe='')
        asset_files_url: str = f"{tool_helper_service.base_url}/v2/asset_files/{encoded_path}"
        params = {
            "project_id": project_id
        }
        content = json.dumps(merged_profiles, indent=2, ensure_ascii=False).encode('utf-8')
        files = {
            'file': (PROCESSED_DOCUMENTS_JSON, content, 'application/json')
            }
        headers = {
            'accept': "*/*"
        }
        LOGGER.info(f"Uploading {PROCESSED_DOCUMENTS_JSON} to CPD storage")
        
        await tool_helper_service.execute_put_request(
            url=asset_files_url,
            files=files,
            params=params,
            headers=headers
        )

        file_exists = await self._poll_storage_file_condition(
            object_key=object_key,
            expect_exists=True
        )

        if not file_exists:
            raise ServiceError(f"Unable to create the {PROCESSED_DOCUMENTS_JSON} in storage after many attempts")
        
        LOGGER.info(f"Successfully uploaded {PROCESSED_DOCUMENTS_JSON} to CPD storage")

        # Create or update CAMS asset (will patch if exists, create if not)
        await self._populate_project(project_id, object_key=object_key, filesize=len(content))
    
    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def upload_csv_file(
        self,
        content: bytes,
        filename: str,
        project_id: str
    ) -> None:
        LOGGER.info(f"Preparing to upload CSV file to project: {filename}")

        # Upload to asset files
        object_key = f"data_asset/{filename}"
        encoded_path = quote(object_key, safe='')
        asset_files_url: str = f"{tool_helper_service.base_url}/v2/asset_files/{encoded_path}"
        params = {
            "project_id": project_id
        }
        
        files = {
            'file': (filename, content, 'text/csv')
            }
        headers = {
            'accept': "*/*"
        }
        LOGGER.info(f"Uploading CSV file: {object_key} to CPD storage")
        
        await tool_helper_service.execute_put_request(
            url=asset_files_url,
            files=files,
            headers=headers,
            params=params
        )

        file_exists = await self._poll_storage_file_condition(
            object_key=object_key,
            expect_exists=True
        )

        if not file_exists:
            raise ServiceError(f"Unable to create the {filename} in storage after 10 attempts")
        
        LOGGER.info(f"Successfully uploaded CSV file: {object_key} to CPD storage")

        await self._populate_project(project_id, object_key=object_key, mime_type="text/csv", filesize=len(content))

    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def upload_lock_file(
        self,
        project_id: str
    ) -> None:
        """
        Atomically create lock file in Asset Files storage using override=false parameter.
        
        Uses the override=false parameter in the PUT request to ensure the lock file is only
        created if it doesn't already exist, preventing race conditions. This eliminates the
        need for polling and reduces lock creation time from 30-60s to <1s.
        
        Args:
            project_id: Project ID for asset creation
            
        Raises:
            ValueError: If lock file already exists (409/412 response from API)
            ServiceError: If upload fails for other reasons
        """
        object_key = f"data_asset/{LOCK_FILE}"
        encoded_path = quote(object_key, safe='')
        asset_files_url: str = f"{tool_helper_service.base_url}/v2/asset_files/{encoded_path}"
        
        # Use override=false for atomic create-if-not-exists behavior
        params = {
            "project_id": project_id,
            "override": "false"
        }

        content = b"LOCK"
        files = {
            'file': (LOCK_FILE, content, 'text/plain')
        }
        headers = {
            'accept': "*/*"
        }
        
        try:
            LOGGER.info(f"Attempting to atomically create {LOCK_FILE} in CPD storage with override=false")
            await tool_helper_service.execute_put_request(
                url=asset_files_url,
                files=files,
                headers=headers,
                params=params
            )
            
            LOGGER.info(f"Successfully created {LOCK_FILE} in CPD storage")
            
            # Create CAMS asset for the lock file
            await self._populate_project(project_id, object_key=object_key, filesize=len(content))
            
        except Exception as e:
            # Check if error indicates lock already exists
            # Expected error codes: 409 Conflict, 412 Precondition Failed
            # Expected error messages: conflict, precondition, already exists
            error_str = str(e).lower()
            lock_error_indicators = ["409", "412", "conflict", "precondition", "already exists"]
            
            if any(indicator in error_str for indicator in lock_error_indicators):
                raise ValueError(
                    "There is currently a lock.txt file in the project to prevent the project being used simultaneously. "
                    "Please ensure no other user is currently running the tool or delete the lock.txt file from the project"
                )
            # For other errors, re-raise
            raise

    async def _verify_storage_file_exists(self, object_key: str) -> bool:
        """
        Verify file existence in Asset Files storage by checking the specific file path.
        
        Uses the /v2/asset_files/{path} endpoint to check if file still exists.
        When purge_on_delete=True, storage deletion is asynchronous and may lag
        behind CAMS asset deletion.
        
        Args:
            object_key: Full storage path like "data_asset/glossary-tool-processed-documents.json"
            
        Returns:
            True if file still exists, False if deleted (404)
        """
        try:
            # object_key already contains the full path including "data_asset/" prefix
            encoded_path = quote(object_key, safe='')
            file_url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded_path}"
            LOGGER.debug(f"Checking asset file URL for existence: {file_url}")

            # Use tool_helper_service which has proper MCP authentication context
            await tool_helper_service.execute_get_request(
                url=file_url,
                params={"project_id": self.project_id},
                tool_name="create_glossary_from_files",
            )
            
            # If we reach here without exception, file exists
            LOGGER.info(f"Storage file {object_key} exists in CPD storage")
            return True
            
        except Exception as e:
            error_str = str(e).lower()
            if "404" in error_str or NOT_FOUND_ERROR in error_str:
                LOGGER.info(f"Storage file {object_key} is not present in CPD storage")
                return False
            # For any other error, assume file exists to be safe (same as original behavior)
            LOGGER.warning(f"Unable to verify storage file state for {object_key}: {e}")
            return True

    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def _delete_file_from_storage(self, project_id: str, object_key: str) -> None:
        """
        Delete a file from Asset Files storage using the DELETE endpoint.
        
        This method deletes the physical file from storage after the CAMS asset
        has been deleted. It uses the /v2/asset_files/{path} DELETE endpoint.
        
        Args:
            project_id: Project ID where the file is stored
            object_key: Name of the file to delete (e.g., "lock.txt")
            
        Raises:
            ServiceError: If deletion fails
        """
        encoded_path = quote(object_key, safe='')
        file_url = f"{tool_helper_service.base_url}/v2/asset_files/{encoded_path}"
        
        LOGGER.info(f"Deleting file from CPD storage: {object_key}")
        
        try:
            await tool_helper_service.execute_delete_request(
                url=file_url,
                params={"project_id": project_id},
                tool_name="create_glossary_from_files"
            )
        except Exception as e:
            error_str = str(e).lower()
            # If file is already gone (404), consider it a success
            if "404" in error_str or "not found" in error_str:
                LOGGER.info(f"Storage file {object_key} is already absent from CPD storage")
                return
            error_msg = f"Error deleting file {object_key} from storage: {e}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e

        deletion_verified = await self._poll_storage_file_condition(
            object_key=object_key,
            expect_exists=False
        )

        if not deletion_verified:
            LOGGER.error(f"Storage file still exists after polling during delete operation: {object_key}")
            raise ServiceError(f"Unable to delete {LOCK_FILE} from storage after 10 attempts, please remove it manually through the UI")
        
        LOGGER.info(f"Successfully deleted file from storage: {object_key}")
    
    async def delete_lock_file(self, project_id: str) -> None:

        object_key = f"data_asset/{LOCK_FILE}"
        
        # Check if file exists in storage and delete it
        LOGGER.info(f"Preparing to delete {LOCK_FILE} file with object_key: {object_key}")
        file_exists = await self._verify_storage_file_exists(object_key)
        
        if file_exists:
            LOGGER.info(f"Storage file exists, deleting from storage with object_key: {LOCK_FILE}")
            await self._delete_file_from_storage(project_id, object_key)
        else:
            LOGGER.info(f"No storage file found for lock file with object_key: {LOCK_FILE}")
        
        await self._delete_cams_lock_file(project_id, object_key)
