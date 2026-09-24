# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

from typing import Dict, Any, Optional, Callable, Awaitable
import json
import aioboto3
from botocore.exceptions import ClientError

from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER
from app.shared.storage.base_file_handler import BaseFileHandler
from app.shared.utils.retry_utils import retry_on_failure, retry_on_expired_aws_token
from app.services.internal.glossary_generation.utils.constants import (
    PROCESSED_DOCUMENTS_JSON,
    LOCK_FILE,
    ErrorCode,
    ErrorResponseKey,
    NO_DOCUMENTS_FOUND_IN_PROJECT_MESSAGE
)


class S3Handler(BaseFileHandler):
    """
    Handler for Amazon S3 storage operations using aioboto3.
    
    Provides methods to download and upload documents from/to S3 buckets
    for AWS-based Data Intelligence deployments (e.g., api.dev.aws.data.ibm.com).
    
    Uses aioboto3 for proper AWS Signature Version 4 (SigV4) authentication,
    which is required for AWS S3 API calls.
    """
    def __init__(
        self,
        storage_details: Dict[str, Any],
        project_id: str,
        credential_refresh_callback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None
    ) -> None:
        """
        Initialize S3Handler with storage configuration.
        
        Args:
            storage_details: Dictionary containing S3 storage configuration
            project_id: Project ID for CAMS asset operations
            credential_refresh_callback: callback function to get storage details to refresh credentials

            storage_details required:
                - properties.bucket_name: Name of the S3 bucket
                - properties.bucket_region: AWS region (e.g., 'us-east-1')
                - properties.credentials.access_key_id: AWS access key
                - properties.credentials.secret_access_key: AWS secret key
                - properties.credentials.session_token: AWS session token (optional)
        """
        self.project_id = project_id
        self.bucket_name = storage_details.get('properties', {}).get('bucket_name')
        self.bucket_region = storage_details.get('properties', {}).get('bucket_region', 'us-east-1')

        self.credential_refresh_callback = credential_refresh_callback

        self._update_credentials_from_storage_details(storage_details)

        if not self.bucket_name:
            raise ValueError("S3 bucket_name is required")
        if not self.access_key_id or not self.secret_access_key:
            raise ValueError("S3 credentials are required")

        # Lazy initialization - client created on first use
        self._session: Optional[aioboto3.Session] = None
        self._client_context = None
        self._client = None
        self._closed = False

        LOGGER.info(f"Initialized S3Handler for bucket: {self.bucket_name}, and S3 bucket region: {self.bucket_region}")

    async def __aenter__(self) -> "S3Handler":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Async context manager exit - ensures proper cleanup."""
        await self.close()
        return False

    def _update_credentials_from_storage_details(self, storage_details: Dict[str, Any]) -> None:
        credentials = storage_details.get('properties', {}).get('credentials', {})
        self.access_key_id = credentials.get('access_key_id')
        self.secret_access_key = credentials.get('secret_access_key')
        self.session_token = credentials.get('session_token')

    async def refresh_credentials(self) -> bool:
        if not self.credential_refresh_callback:
            LOGGER.warning("No credential refresh callback available")
            return False

        try:
            LOGGER.info("Refreshing S3 credentials via callback...")

            new_storage_details = await self.credential_refresh_callback()

            self._update_credentials_from_storage_details(new_storage_details)

            # client must be recreated to use new credentials
            await self._recreate_client()

            LOGGER.info("AWS credentials refreshed successfully")
            return True

        except Exception as e:
            LOGGER.error(f"AWS credential refresh failed: {e}")
            raise ServiceError("Failed to refresh AWS credentials") from e

    async def _recreate_client(self) -> None:
        await self._close_client()

    async def _close_client(self) -> None:
        if self._client_context:
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.warning(f"Error closing client in S3 Handler: {e}")

        self._session = None
        self._client_context = None
        self._client = None

    async def _get_client(self):
        """
        Get or create S3 client with connection pooling.
        
        Uses lazy initialization to create the client only once and reuse it
        across all operations. This provides connection pooling and better performance.
        
        Returns:
            S3 client instance
        """
        if self._client is None:
            LOGGER.debug("Creating new S3 client with connection pooling")
            self._session = aioboto3.Session(
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                aws_session_token=self.session_token,
                region_name=self.bucket_region
            )
            self._client_context = self._session.client('s3')
            self._client = await self._client_context.__aenter__()
            LOGGER.debug("S3 client created and ready for reuse")
        return self._client

    async def close(self) -> None:
        """
        Close the S3 client and cleanup resources.
        
        Should be called when the handler is no longer needed to properly
        close connections and release resources. This method is idempotent
        and safe to call multiple times.
        """
        if self._closed:
            return
            
        if self._client_context is not None:
            LOGGER.debug("Closing S3 client and releasing connections")
            try:
                await self._client_context.__aexit__(None, None, None)
            except Exception as e:
                LOGGER.warning(f"Error during S3 client cleanup: {e}")
            finally:
                self._client = None
                self._client_context = None
                self._session = None
                self._closed = True
                LOGGER.debug("S3 client closed successfully")
        else:
            self._closed = True

    async def _check_bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists.
        
        Returns:
            True if bucket exists, False otherwise
        """
        try:
            s3_client = await self._get_client()
            await s3_client.head_bucket(Bucket=self.bucket_name)
            LOGGER.debug(f"S3 bucket exists: {self.bucket_name}")
            return True
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            if error_code in ('NoSuchBucket', ErrorCode.NOT_FOUND_404, ErrorCode.NOT_FOUND):
                LOGGER.debug(f"S3 bucket does not exist: {self.bucket_name}")
                return False
            # For other errors, log warning and assume bucket exists to be safe
            LOGGER.warning(f"Error checking bucket existence: {e}")
            return True
        except Exception as e:
            LOGGER.warning(f"Unexpected error checking bucket existence: {e}")
            return True

    async def _check_file_exists_in_bucket(self, filename: str) -> bool:
        """
        Check if a file exists in the S3 bucket.
        
        Uses head_object API which is more efficient than listing all objects.
        
        Args:
            filename: Name of the file to check (e.g., "glossary-tool-processed-documents.json")
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            # First check if bucket exists
            bucket_exists = await self._check_bucket_exists()
            if not bucket_exists:
                LOGGER.debug(f"Bucket doesn't exist - file {filename} doesn't exist")
                return False
            
            s3_client = await self._get_client()
            await s3_client.head_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            LOGGER.debug(f"File {filename} found in S3 bucket")
            return True
            
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            if error_code in (ErrorCode.NO_SUCH_KEY, ErrorCode.NOT_FOUND_404, ErrorCode.NOT_FOUND):
                LOGGER.debug(f"File {filename} not found in S3 bucket")
                return False
            # For other errors, log warning and assume file doesn't exist to be safe
            LOGGER.warning(
                f"Could not check if {filename} exists in bucket (error: {e}). "
                f"Assuming file doesn't exist to be safe."
            )
            return False
        except Exception as e:
            LOGGER.warning(
                f"Unexpected error checking if {filename} exists (error: {e}). "
                f"Assuming file doesn't exist to be safe."
            )
            return False

    # Decorator order is important - retry_on_expired_token should be innermost
    # to ensure it runs before other retries.
    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ClientError,))
    @retry_on_expired_aws_token
    async def get_documents(self) -> Dict[str, Any]:
        """
        Get all documents from the S3 bucket.
        
        Uses S3 list_objects_v2 API to retrieve bucket contents, then downloads
        each document individually using get_object.
        
        Returns:
            Dict mapping document filenames to their content (bytes)
            
        Raises:
            ValueError: If there are no documents in the bucket
            ServiceError: If S3 operations fail
        """
        LOGGER.info("S3Handler: Starting get_documents")
        
        try:
            # Check if bucket exists first to avoid NoSuchBucket errors
            bucket_exists = await self._check_bucket_exists()
            if not bucket_exists:
                LOGGER.warning(f"S3 bucket does not exist: {self.bucket_name}")
                raise ValueError(NO_DOCUMENTS_FOUND_IN_PROJECT_MESSAGE)
            
            s3_client = await self._get_client()
            
            # List all objects in the bucket
            LOGGER.info(f"Listing objects in S3 bucket: {self.bucket_name}")
            response = await s3_client.list_objects_v2(Bucket=self.bucket_name)
                
            if 'Contents' not in response or not response['Contents']:
                LOGGER.warning(f"No objects found in S3 bucket: {self.bucket_name}")
                # Raise ValueError outside of generic exception handling
                raise ValueError(NO_DOCUMENTS_FOUND_IN_PROJECT_MESSAGE)
            
            objects = response['Contents']
            LOGGER.info(f"Found {len(objects)} objects in S3 bucket")
            
            # Download each document
            bucket_responses: Dict[str, Any] = {}
            
            for obj in objects:
                filename = obj['Key']
                LOGGER.info(f"Downloading document from S3: {filename}")
                
                # Get object content
                obj_response = await s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=filename
                )
                
                # Read the content
                async with obj_response['Body'] as stream:
                    content = await stream.read()
                
                bucket_responses[filename] = content
                LOGGER.info(f"Successfully downloaded from S3: {filename} ({len(content)} bytes)")
            
            LOGGER.info(f"S3Handler: Downloaded {len(bucket_responses)} documents")
            return bucket_responses
                
        except ValueError:
            # Re-raise ValueError without wrapping it in ServiceError
            raise
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            # Let ExpiredToken pass through to retry_on_expired_aws_token decorator
            if error_code == ErrorCode.EXPIRED_TOKEN:
                LOGGER.info("ExpiredToken detected in get_documents, re-raising for decorator handling")
                raise
            # Handle NoSuchBucket specifically with better messaging
            if error_code == 'NoSuchBucket':
                LOGGER.warning(f"S3 bucket does not exist: {self.bucket_name}")
                raise ValueError(NO_DOCUMENTS_FOUND_IN_PROJECT_MESSAGE)
            error_msg = f"S3 ClientError ({error_code}): {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Error getting documents from S3 bucket: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e

    # Decorator order is important - retry_on_expired_token should be innermost
    # to ensure it runs before other retries.
    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ClientError,))
    @retry_on_expired_aws_token
    async def get_merged_profile(self) -> Optional[Dict[str, Any]]:
        """
        Get merged profile JSON from S3 bucket.
        
        Uses a lightweight existence check before attempting to fetch the file to avoid
        NoSuchKey and NoSuchBucket errors that can cause issues in MCP server environments.
        
        Returns:
            Dictionary containing the merged profile data, or None if file doesn't exist
            
        Raises:
            ServiceError: If S3 operations fail (excluding file not found)
        """
        # LAYER 1: Check if file exists using lightweight head_object operation
        # This prevents NoSuchKey/NoSuchBucket errors from occurring in the first place
        LOGGER.info(f"Checking if {PROCESSED_DOCUMENTS_JSON} exists in S3 bucket")
        file_exists = await self._check_file_exists_in_bucket(PROCESSED_DOCUMENTS_JSON)
        
        if not file_exists:
            LOGGER.info(f"{PROCESSED_DOCUMENTS_JSON} not found in S3 - will perform full processing")
            return None
        
        # LAYER 2: File exists, fetch it with exception handling as backup
        try:
            s3_client = await self._get_client()
            
            LOGGER.info(f"Fetching merged profile from S3: {PROCESSED_DOCUMENTS_JSON}")
            
            # Get object content
            response = await s3_client.get_object(
                Bucket=self.bucket_name,
                Key=PROCESSED_DOCUMENTS_JSON
            )
            
            # Read and parse JSON content
            async with response['Body'] as stream:
                content = await stream.read()
            
            result = json.loads(content.decode('utf-8'))
            LOGGER.info(f"Successfully retrieved {PROCESSED_DOCUMENTS_JSON} from S3")
            return result
                
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            
            # Backup: Handle NoSuchKey/NoSuchBucket if it somehow occurs despite existence check (race condition)
            if error_code in (ErrorCode.NO_SUCH_KEY, 'NoSuchBucket'):
                LOGGER.warning(
                    f"{PROCESSED_DOCUMENTS_JSON} disappeared between existence check and fetch - "
                    f"will perform full processing"
                )
                return None
            
            # Let ExpiredToken pass through to retry_on_expired_aws_token decorator
            if error_code == ErrorCode.EXPIRED_TOKEN:
                LOGGER.info("ExpiredToken detected in get_merged_profile, re-raising for decorator handling")
                raise
            
            # For other errors, raise
            error_msg = f"S3 ClientError ({error_code}) downloading merged profile: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"Error parsing merged profile JSON from S3: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Error downloading merged profile from S3 bucket: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e

    # Decorator order is important - retry_on_expired_token should be innermost
    # to ensure it runs before other retries.        
    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ClientError,))
    @retry_on_expired_aws_token
    async def upload_merged_profile(
        self,
        merged_profiles: Dict[str, Any],
        project_id: str
    ) -> None:
        """
        Upload merged profiles document to S3 bucket.
        
        Also updates the CAMS asset attachment with the new file size.
        
        Args:
            merged_profiles: Dictionary containing merged profile data
            project_id: Project ID for CAMS asset update
        
        Raises:
            ServiceError: If merged_profiles is empty or S3 operations fail
        """
        if not merged_profiles:
            raise ServiceError("The intermediate file merged_profiles is empty")
        
        filename = PROCESSED_DOCUMENTS_JSON
        
        # Convert to JSON bytes
        content = json.dumps(merged_profiles, indent=2, ensure_ascii=False).encode('utf-8')
        
        try:
            s3_client = await self._get_client()
            
            # Upload to S3
            LOGGER.info(f"Uploading merged profile to S3: {filename}")
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=content,
                ContentType='application/json'
            )
            LOGGER.info("Successfully uploaded merged profiles to S3 bucket")
            
            # Create or update CAMS asset (will patch if exists, create if not)
            await self._populate_project(project_id, object_key=filename, filesize=len(content))
            
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            # Let ExpiredToken pass through to retry_on_expired_aws_token decorator
            if error_code == ErrorCode.EXPIRED_TOKEN:
                LOGGER.info("ExpiredToken detected in upload_merged_profile, re-raising for decorator handling")
                raise
            error_msg = f"S3 ClientError ({error_code}) uploading merged profile: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Error uploading merged profile to S3: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e

    # Decorator order is important - retry_on_expired_token should be innermost
    # to ensure it runs before other retries.        
    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ClientError,))
    @retry_on_expired_aws_token
    async def upload_csv_file(
        self,
        content: bytes,
        filename: str,
        project_id: str
    ) -> None:
        """
        Upload CSV file to S3 bucket.
        
        Args:
            content: CSV file content as bytes
            filename: Name of the file to upload
            project_id: Project ID for CAMS asset creation
        
        Raises:
            ValueError: If content is empty
            ServiceError: If S3 operations fail
        """
        if not content:
            raise ValueError("CSV content cannot be empty")
        
        LOGGER.info(f"Preparing to upload CSV file to S3: {filename}")
        
        try:
            s3_client = await self._get_client()
            
            # Upload to S3 with proper Content-Type
            LOGGER.info(f"Uploading CSV file to S3: {filename}")
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=content,
                ContentType='text/csv'
            )
            LOGGER.info(f"Successfully uploaded CSV file to S3: {filename}")
            
            # Create or update CAMS asset
            await self._populate_project(project_id, object_key=filename, filesize=len(content), mime_type="text/csv")
            
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            # Let ExpiredToken pass through to retry_on_expired_aws_token decorator
            if error_code == ErrorCode.EXPIRED_TOKEN:
                LOGGER.info("ExpiredToken detected in upload_csv_file, re-raising for decorator handling")
                raise
            error_msg = f"S3 ClientError ({error_code}) uploading CSV file: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Error uploading CSV file to S3: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e

    # Decorator order is important - retry_on_expired_token should be innermost
    # to ensure it runs before other retries.        
    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ClientError,))
    @retry_on_expired_aws_token
    async def upload_lock_file(
        self,
        project_id: str
    ) -> None:
        """
        Atomically create lock file using S3 conditional PUT.
        
        Uses S3's IfNoneMatch parameter to ensure the lock file is only created
        if it doesn't already exist to prevent race conditions
        
        Args:
            project_id: Project ID for CAMS asset creation
            
        Raises:
            ValueError: If lock file already exists (ErrorCode.PRECONDITION_FAILED)
            ServiceError: If lock file creation fails
        """
        content = b"LOCK"
        
        try:
            LOGGER.info(f"Attempting to create {LOCK_FILE} in S3 bucket")
            
            s3_client = await self._get_client()
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=LOCK_FILE,
                Body=content,
                IfNoneMatch='*'  # S3's conditional put parameter
            )
            
            file_exists = await self._poll_storage_file_condition(
                object_key=LOCK_FILE,
                expect_exists=True
            )

            if not file_exists:
                raise ServiceError(f"Unable to create the {LOCK_FILE} in storage after 10 attempts")

            LOGGER.info(f"Successfully created {LOCK_FILE} in S3 bucket")

            await self._populate_project(project_id, object_key=LOCK_FILE, filesize=len(content))
            
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            # PreconditionFailed means lock already exists
            if error_code == ErrorCode.PRECONDITION_FAILED:
                raise ValueError(
                    "There is currently a lock.txt file in the project to prevent the project being used simultaneously. "
                    "Please ensure no other user is currently running the tool or delete the lock.txt file from the project"
                )
            # Let ExpiredToken pass through to retry_on_expired_aws_token decorator
            if error_code == ErrorCode.EXPIRED_TOKEN:
                LOGGER.info("ExpiredToken detected in upload_lock_file, re-raising for decorator handling")
                raise
            error_msg = f"S3 ClientError ({error_code}) creating lock file: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e
        except Exception as e:
            error_msg = f"Error creating lock file in S3: {str(e)}"
            LOGGER.error(error_msg)
            raise ServiceError(error_msg) from e

    async def _verify_storage_file_exists(self, object_key: str) -> bool:
        """
        Verify file existence in S3 bucket by listing bucket contents.
        
        When purge_on_delete=True, storage deletion is asynchronous and may lag
        behind CAMS asset deletion.
        
        Args:
            object_key: Object key like ".lock"
            
        Returns:
            True if file exists, False if not found
        """
        try:
            LOGGER.debug(f"Checking if {object_key} exists in S3 bucket")
            
            s3_client = await self._get_client()
            try:
                await s3_client.head_object(
                    Bucket=self.bucket_name,
                    Key=object_key
                )
                LOGGER.debug(f"Storage file {object_key} exists in S3 bucket")
                return True
            except ClientError as e:
                error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
                if error_code == ErrorCode.NO_SUCH_KEY or error_code == ErrorCode.NOT_FOUND_404:
                    LOGGER.info(f"Confirmed storage deletion of {object_key} from S3")
                    return False
                # For other errors, re-raise
                raise
            
        except Exception as e:
            LOGGER.warning(f"Error checking storage file {object_key} in S3: {e}")
            # On error, assume file exists to be safe
            return True

    # Decorator order is important - retry_on_expired_token should be innermost
    # to ensure it runs before other retries.        
    @retry_on_failure(max_retries=1, backoff_factor=2.0, exceptions=(ClientError,))
    @retry_on_expired_aws_token
    async def _delete_file_from_storage(self, project_id: str, object_key: str) -> None:
        """
        Delete a file from S3 bucket storage using the delete_object API.
        
        This method deletes the physical file from S3 storage after the CAMS asset
        has been deleted.
        
        Args:
            project_id: Project ID (not used for S3 but kept for interface consistency)
            object_key: Name of the file to delete (e.g., ".lock")
        """
        LOGGER.info(f"Deleting file from S3 bucket storage: {object_key}")
        
        try:
            s3_client = await self._get_client()
            await s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
        except ClientError as e:
            error_code = e.response.get(ErrorResponseKey.ERROR, {}).get(ErrorResponseKey.CODE, ErrorCode.UNKNOWN)
            # NoSuchKey means file already deleted - this is fine
            if error_code == ErrorCode.NO_SUCH_KEY or error_code == ErrorCode.NOT_FOUND_404:
                LOGGER.info(f"File {object_key} already deleted from S3 (NoSuchKey)")
                return
            # Let ExpiredToken pass through to retry_on_expired_aws_token decorator
            if error_code == ErrorCode.EXPIRED_TOKEN:
                LOGGER.info("ExpiredToken detected in _delete_file_from_storage, re-raising for decorator handling")
                raise
            # For other errors, re-raise to trigger retry
            raise

        deletion_verified = await self._poll_storage_file_condition(
            object_key=object_key,
            expect_exists=False
        )

        if not deletion_verified:
            LOGGER.error(f"[LOCK_LOG] File still exists in storage after polling, error in deleting: {LOCK_FILE}")
            raise ServiceError(f"Unable to delete the {LOCK_FILE} in storage after 10 attempts, please remove manually through the UI")

        LOGGER.info(f"Successfully deleted file from S3 storage: {object_key}")

    async def delete_lock_file(self, project_id: str) -> None:
        """
        Delete lock file from S3 bucket.
        
        This method follows the same pattern as COSHandler:
        1. Check if file exists in storage
        2. Delete from storage if it exists
        3. Delete CAMS asset
        
        Args:
            project_id: Project ID for CAMS asset deletion
        """
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
