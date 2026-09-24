# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import List, Dict, Any, Optional, cast
import re
import json
from urllib.parse import quote
import xml.etree.ElementTree as ET
from app.shared.exceptions.base import ServiceError, ExternalAPIError
from app.shared.logging import LOGGER
from app.shared.models.bucket_objects import (
    BucketObjects,
)
from app.shared.storage.base_file_handler import BaseFileHandler
from app.shared.utils.retry_utils import retry_on_failure
from app.services.internal.glossary_generation.utils.constants import (
    LOCK_FILE,
    PROCESSED_DOCUMENTS_JSON,
)
from app.shared.utils.tool_helper_service import tool_helper_service

class COSHandler(BaseFileHandler):
    """
    Handler for Cloud Object Storage (COS) operations.
    
    Provides methods to download and upload documents from/to COS buckets,
    with support for document profiles and merged profiles.
    """

    def __init__(self, storage_details: Dict[str, Any]) -> None:
        self.bucket_name = storage_details.get('properties').get('bucket_name')
        self.bucket_url = f"{storage_details.get('properties').get('endpoint_url')}/{self.bucket_name}"

    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ExternalAPIError,))
    async def get_documents(self) -> Dict[str, Any]:
        """
        Get all documents from the COS bucket.
        
        Args:
            bucket_endpoint_url: Base URL of COS
            bucket_name: Name of the specific COS bucket
        
        Returns:
            Dict mapping document filenames to their content
            
        Raises:
            ValueError: If there are no documents in the project/bucket
            COSError: If COS operations fail
        """

        query_params: Dict[str, int] = {"list-type": 2}
        bucket_url: str = f"{self.bucket_url}"

        LOGGER.info(f"Fetching documents from: {bucket_url}")

        response = await tool_helper_service.execute_get_request(
            url=bucket_url,
            params=query_params
            )

        xml_data: bytes = response.get("content", response) if isinstance(response, dict) else response
        bucket_objects: List[BucketObjects] = self._parse_s3_xml(xml_data)

        if not bucket_objects:
            LOGGER.warning(f"No objects found in bucket: {self.bucket_name}")
            raise ValueError("No documents were found in the project")

        return await self._get_each_document_from_cos(bucket_url, bucket_objects)

    def _parse_s3_content_element(self, content: ET.Element, ns: dict) -> Optional[BucketObjects]:
        """
        Parse a single S3 XML <Contents> element into a BucketObjects instance.

        Args:
            content: A single <Contents> XML element
            ns: XML namespace mapping

        Returns:
            A BucketObjects instance, or None if the element is invalid
        """
        try:
            key_elem = content.find('s3:Key', ns)
            last_modified_elem = content.find('s3:LastModified', ns)
            etag_elem = content.find('s3:ETag', ns)
            size_elem = content.find('s3:Size', ns)
            storage_class_elem = content.find('s3:StorageClass', ns)
            checksum_algorithm_elem = content.find('s3:ChecksumAlgorithm', ns)
            checksum_type_elem = content.find('s3:ChecksumType', ns)

            if key_elem is None or key_elem.text is None:
                LOGGER.warning("Skipping object with missing Key")
                return None

            return BucketObjects(
                key=key_elem.text,
                last_modified=(last_modified_elem.text if last_modified_elem is not None and last_modified_elem.text else ""),
                etag=etag_elem.text.strip('"') if etag_elem is not None and etag_elem.text else "",
                size=int(size_elem.text) if size_elem is not None and size_elem.text else 0,
                storage_class=(storage_class_elem.text if storage_class_elem is not None and storage_class_elem.text else ""),
                checksum_algorithm=(checksum_algorithm_elem.text if checksum_algorithm_elem is not None and checksum_algorithm_elem.text else ""),
                checksum_type=(checksum_type_elem.text if checksum_type_elem is not None and checksum_type_elem.text else "")
            )
        except (ValueError, AttributeError) as e:
            LOGGER.error(f"Error parsing object in S3 XML: {e}")
            return None

    def _parse_s3_xml(self, xml_data: bytes) -> List[Any]:
        """
        Parse S3 XML response to extract bucket objects.
        
        Args:
            xml_data: Raw XML response from S3
            
        Returns:
            List of BucketObjects
            
        Raises:
            ET.ParseError: If XML parsing fails
        """
        try:
            root = ET.fromstring(xml_data)
            m = re.match(r'\{(.*)\}', root.tag)
            namespace = m.group(1) if m else ''
            ns = {'s3': namespace}

            objects = []
            for content in root.findall('s3:Contents', ns):
                obj = self._parse_s3_content_element(content, ns)
                if obj is not None:
                    objects.append(obj)

            return objects
        except ET.ParseError as e:
            LOGGER.error(f"XML parsing error: {e}")
            raise ServiceError("There was an error finding the documents in the project")

    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def _get_each_document_from_cos(
        self,
        bucket_url: str,
        bucket_objects: List[BucketObjects]
    ) -> Dict[str, Any]:
        """
        Download each document from COS bucket.
        
        Args:
            bucket_url: URL of the COS bucket
            bucket_objects: List of objects to download from COS
            
        Returns:
            Dict mapping document filenames to their content
            
        """
        bucket_responses: Dict[str, Any] = {}

        for bucket_object in bucket_objects:
            filename = bucket_object.key
            
            encoded_filename = quote(filename, safe='')
            bucket_object_url: str = f"{bucket_url}/{encoded_filename}"

            LOGGER.info(f"Downloading document: {filename} from {bucket_object_url}")

            bucket_response = await tool_helper_service.execute_get_request(
                url=bucket_object_url,
                tool_name="create_glossary_from_files"
            )
            
            content = bucket_response.get("content", bucket_response) if isinstance(bucket_response, dict) else bucket_response
            bucket_responses[filename] = content
            LOGGER.info(f"Successfully downloaded: {filename}")

        return bucket_responses

    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ExternalAPIError,))
    async def get_merged_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get merged profile JSON from COS bucket.
        
        Uses a lightweight existence check before attempting to fetch the file to avoid
        404 errors that can cause issues in MCP server environments.
        
        Args:
            bucket_endpoint_url: Base URL of COS
            bucket_name: Name of the COS bucket
            
        Returns:
            Dictionary containing the merged profile data, or None if file doesn't exist
        """
        bucket_url: str = f"{self.bucket_url}"
        bucket_object_url: str = f"{bucket_url}/{PROCESSED_DOCUMENTS_JSON}"
        
        # LAYER 1: Check if file exists using lightweight list operation
        # This prevents 404 errors from occurring in the first place
        LOGGER.info(f"Checking if {PROCESSED_DOCUMENTS_JSON} exists in COS bucket")
        file_exists = await self._check_file_exists_in_bucket(PROCESSED_DOCUMENTS_JSON)
        
        if not file_exists:
            LOGGER.info(f"{PROCESSED_DOCUMENTS_JSON} not found in COS - will perform full processing")
            return None
        
        # LAYER 2: File exists, fetch it with exception handling as backup
        try:
            LOGGER.info(f"Fetching merged profile from: {bucket_object_url}")
            result = cast(Dict[str, Any], await tool_helper_service.execute_get_request(
                url=bucket_object_url,
                tool_name="create_glossary_from_files"
            ))
            LOGGER.info(f"Successfully retrieved {PROCESSED_DOCUMENTS_JSON} from COS")
            content = result.get("content", result) if isinstance(result, dict) else result
            if isinstance(content, bytes):
                return json.loads(content.decode('utf-8'))
            return content

        except Exception as e:
            # Backup: Handle 404 if it somehow occurs despite existence check (race condition)
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str or "nosuchkey" in error_str:
                LOGGER.warning(
                    f"{PROCESSED_DOCUMENTS_JSON} disappeared between existence check and fetch - "
                    f"will perform full processing"
                )
                return None
            # For other errors, raise
            error_msg = f"Error downloading merged profile from project: {e}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
    
    async def _check_file_exists_in_bucket(self, filename: str) -> bool:
        """
        Check if a file exists in the COS bucket by leveraging existing get_documents method.
        
        This reuses the already-tested bucket listing logic that properly handles
        XML parsing across different S3 implementations and environments.
        
        Args:
            filename: Name of the file to check (e.g., "glossary-tool-processed-documents.json")
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            # Leverage the existing get_documents() method which already handles
            # XML parsing correctly for all S3 implementations
            LOGGER.debug(f"Checking if {filename} exists using bucket listing")
            
            # Get all documents in the bucket
            documents = await self.get_documents()
            
            # Check if our filename is in the list of documents
            if filename in documents:
                LOGGER.debug(f"File {filename} found in bucket")
                return True
            
            LOGGER.debug(f"File {filename} not found in bucket")
            return False
            
        except ValueError as e:
            # get_documents() raises ValueError when bucket is empty
            # This is expected for new projects
            error_str = str(e).lower()
            if "no documents" in error_str or "empty" in error_str:
                LOGGER.debug(f"Bucket is empty - file {filename} doesn't exist")
                return False
            # Re-raise unexpected ValueErrors
            raise
            
        except Exception as e:
            # If we can't list the bucket, log warning and assume file doesn't exist
            # This is safer than raising an error
            error_str = str(e).lower()
            if "404" in error_str or "not found" in error_str:
                LOGGER.debug(f"Bucket listing returned 404 - file {filename} doesn't exist")
                return False
            
            LOGGER.warning(
                f"Could not check if {filename} exists in bucket (error: {e}). "
                f"Assuming file doesn't exist to be safe."
            )
            return False

    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def upload_merged_profile(
        self,
        merged_profiles: Dict[str, Any],
        project_id: str
    ) -> None:
        """
        Upload merged profiles document to COS bucket.
        
        Also updates the CAMS asset attachment with the new file size.
        
        Args:
            bucket_endpoint_url: Base URL of COS
            bucket_name: Name of the bucket to upload to
            merged_profiles: Dictionary containing merged profile data
            project_id: Project ID for CAMS asset update
        
        Returns:
            Asset ID of the created or existing CAMS asset
        
        Raises:
            ServiceError: If bucket parameters are invalid or merged_profiles is empty
        """
        
        if not merged_profiles:
            raise ServiceError("The intermediate file glossary-tool-processed-documents is empty")
        
        filename = PROCESSED_DOCUMENTS_JSON
        
        content = json.dumps(merged_profiles, indent=2, ensure_ascii=False).encode('utf-8')

        # Upload to COS
        bucket_url: str = f"{self.bucket_url}/{filename}"
        
        LOGGER.info(f"Uploading {PROCESSED_DOCUMENTS_JSON} to bucket storage")
        await tool_helper_service.execute_put_request(
            url=bucket_url,
            content=content,
        )

        file_exists = await self._poll_storage_file_condition(
            object_key=filename,
            expect_exists=True
        )

        if not file_exists:
            raise ServiceError(f"Unable to create the {PROCESSED_DOCUMENTS_JSON} in storage after 10 attempts")
        
        LOGGER.info(f"Successfully uploaded {PROCESSED_DOCUMENTS_JSON} to bucket storage")

        # Create or update CAMS asset (will patch if exists, create if not)
        await self._populate_project(project_id, object_key=filename, filesize=len(content))

    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def upload_csv_file(
        self,
        content: bytes,
        filename: str,
        project_id: str
    ) -> None:
        """
        Upload CSV file to COS bucket.
        
        Args:
            bucket_endpoint_url: Base URL of COS
            bucket_name: Name of the bucket to upload to
            file_data: CSV file content as bytes
            filename: Name of the file to upload
            project_id: Project ID for CAMS asset creation
        
        Returns:
            Asset ID of the created or existing CAMS asset
        
        Raises:
            ValueError: If bucket parameters are invalid or file_data is empty
            COSError: If upload operations fail
        """

        LOGGER.info(f"Preparing to upload CSV file to project: {filename}")

        # Upload to COS with proper Content-Type
        encoded_filename = quote(filename, safe='')
        bucket_url: str = f"{self.bucket_url}/{encoded_filename}"
        
        headers = {"Content-Type": "text/csv"}
        LOGGER.info(f"Uploading CSV file: {filename} to {bucket_url}")
        
        await tool_helper_service.execute_put_request(
            url=bucket_url,
            content=content,
            headers=headers
        )

        file_exists = await self._poll_storage_file_condition(
            object_key=filename,
            expect_exists=True
        )

        if not file_exists:
            LOGGER.error(f"[LOCK_LOG] File could not be created after polling, error in creating: {filename}")
            raise ServiceError(f"Unable to create the {filename} in storage after 10 attempts")
        
        LOGGER.info(f"Successfully uploaded CSV file: {filename} to bucket storage")
        
        await self._populate_project(project_id, object_key=filename, filesize=len(content), mime_type="text/csv")
    
    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def upload_lock_file(
        self,
        project_id: str
    ) -> None:
        """
        Atomically create lock file using S3 conditional PUT.
        
        Uses the If-None-Match: * header for S3 storage to ensure the lock file is only created
        if it doesn't already exist to prevent race conditions
        
        Args:
            project_id: Project ID for CAMS asset creation
            
        Raises:
            ServiceError: If lock file already exists (412 Precondition Failed)
        """
        encoded_filename = quote(LOCK_FILE, safe='')
        bucket_url: str = f"{self.bucket_url}/{encoded_filename}"
        content = b"LOCK"
        
        # Use If-None-Match header for atomic create-if-not-exists
        headers = {
            "If-None-Match": "*"
        }
        
        try:
            LOGGER.info(f"Attempting to create {LOCK_FILE} in bucket storage")
            await tool_helper_service.execute_put_request(
                url=bucket_url,
                content=content,
                headers=headers
            )
            
            file_exists = await self._poll_storage_file_condition(
                object_key=LOCK_FILE,
                expect_exists=True
            )

            if not file_exists:
                raise ServiceError(f"Unable to create the {LOCK_FILE} in storage after 10 attempts")

            LOGGER.info(f"Successfully created {LOCK_FILE} in bucket storage")

            await self._populate_project(project_id, object_key=LOCK_FILE, filesize=len(content))
            
        except Exception as e:
            # 412 Precondition Failed means lock already exists
            error_str = str(e).lower()
            if "412" in error_str or "precondition" in error_str:
                raise ValueError(
                    "There is currently a lock.txt file in the project to prevent the project being used simultaneously. "
                "Please ensure no other user is currently running the tool or delete the lock.txt file from the project"
                )
    
    async def _verify_storage_file_exists(self, object_key: str) -> bool:
        """
        Verify file existence in COS bucket by listing bucket contents.
        This avoids 404 errors that occur when using GET requests.
        
        When purge_on_delete=True, storage deletion is asynchronous and may lag
        behind CAMS asset deletion.
        
        Args:
            object_key: Object key like ".lock"
            
        Returns:
            True if file exists, False if not found
        """
        try:
            LOGGER.debug(f"Checking if {object_key} exists using bucket listing")
            
            # List bucket contents to check if file exists
            query_params: Dict[str, int] = {"list-type": 2}
            response = await tool_helper_service.execute_get_request(
                url=self.bucket_url,
                params=query_params
            )
            
            xml_data: bytes = response.get("content", response) if isinstance(response, dict) else response
            bucket_objects: List[BucketObjects] = self._parse_s3_xml(xml_data)
            
            # Check if object_key is in the list of bucket objects
            file_exists = any(obj.key == object_key for obj in bucket_objects)
            
            if file_exists:
                LOGGER.debug(f"Storage file {object_key} exists in COS bucket")
            else:
                LOGGER.info(f"Confirmed storage deletion of {object_key} from COS")
            
            return file_exists
            
        except Exception as e:
            LOGGER.warning(f"Error checking storage file {object_key} via bucket listing: {e}")
            # On error, assume file exists to be safe
            return True

    @retry_on_failure(max_retries=1, backoff_factor=2.0)
    async def _delete_file_from_storage(self, project_id: str, object_key: str) -> None:
        """
        Delete a file from COS bucket storage using the DELETE endpoint.
        
        This method deletes the physical file from COS storage after the CAMS asset
        has been deleted. It uses the /{Bucket}/{Key} DELETE endpoint.
        
        Args:
            project_id: Project ID (not used for COS but kept for interface consistency)
            filename: Name of the file to delete (e.g., ".lock")
        """
        encoded_filename = quote(object_key, safe='')
        object_url = f"{self.bucket_url}/{encoded_filename}"
        
        LOGGER.info(f"Deleting file from COS bucket storage: {object_key}")
        
        await tool_helper_service.execute_delete_request(
            url=object_url,
            tool_name="create_glossary_from_files"
        )

        deletion_verified = await self._poll_storage_file_condition(
                object_key=object_key,
                expect_exists=False
            )

        if not deletion_verified:
            LOGGER.error(f"[LOCK_LOG] File stills exist in storage after polling, error in deleting: {LOCK_FILE}")
            raise ServiceError(f"Unable to delete the {LOCK_FILE} in storage after 10 attempts, please remove manually through the UI")

        LOGGER.info(f"Successfully deleted file from COS storage: {object_key}")

    async def delete_lock_file(self, project_id: str) -> None:
    
        object_key = LOCK_FILE
        # Check if file exists in storage and delete it
        LOGGER.info(f"Preparing to delete {LOCK_FILE} file with object_key: {object_key}")
        file_exists = await self._verify_storage_file_exists(object_key)
        
        if file_exists:
            LOGGER.info(f"Storage file exists, deleting from storage with object_key: {LOCK_FILE}")
            await self._delete_file_from_storage(project_id, object_key)
        else:
            LOGGER.info(f"No storage file found for lock file with object_key: {LOCK_FILE}")
        
        await self._delete_cams_lock_file(project_id, object_key)
