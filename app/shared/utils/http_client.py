# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI Tool

"""Async HTTP client with connection pooling and error handling."""

from typing import Any, Callable, Awaitable
import logging
from asyncio import Semaphore

import httpx

from app.core.settings import settings
from app.shared.exceptions.base import ExternalAPIError
from app.shared.utils.ssl_utils import get_ssl_verify_setting
from app.shared.utils.http_constants import (
    APPLICATION_FORM_URL_ENCODED,
    HTTP_CLIENT_STATS_LOG_MSG,
)
from app.services.constants import JSON_CONTENT_TYPE

LOGGER = logging.getLogger(__name__)

# Global semaphore for controlling concurrent IBM API calls
# This prevents overwhelming external APIs and connection pool exhaustion
_ibm_api_semaphore: Semaphore | None = None


def get_ibm_api_semaphore() -> Semaphore:
    """
    Get the global IBM API semaphore instance (singleton pattern).
    
    This semaphore controls how many concurrent requests can be made to IBM APIs,
    preventing connection pool exhaustion and protecting downstream services.
    
    Returns:
        Semaphore: The global semaphore instance
    """
    global _ibm_api_semaphore
    if _ibm_api_semaphore is None:
        _ibm_api_semaphore = Semaphore(settings.ibm_api_max_concurrent_calls)
        LOGGER.info(
            "IBM API semaphore initialized with limit: %d concurrent calls",
            settings.ibm_api_max_concurrent_calls
        )
    return _ibm_api_semaphore


class AsyncHttpClient:
    """
    Async HTTP client with connection pooling and automatic retry logic.

    This class provides an async HTTP client with connection pooling,
    SSL verification, and proper error handling for external API calls.
    """

    def __init__(self) -> None:
        """Initialize the HTTP client with lazy loading."""
        self._client: httpx.AsyncClient | None = None
        self._request_count = 0
        self._error_count = 0

    @property
    async def client(self) -> httpx.AsyncClient:
        """
        Get the async HTTP client instance with lazy initialization.

        Returns:
            httpx.AsyncClient: Configured async HTTP client instance
        """
        if self._client is None:
            # Get enhanced SSL configuration
            verify_setting = get_ssl_verify_setting(
                settings.ssl_config, settings.ssl_verify
            )
            # Note: cert_setting is now None as certificates are loaded into SSL context

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.request_timeout_s),
                verify=verify_setting,  # Enhanced SSL verification (bool, str, or SSLContext)
                limits=httpx.Limits(
                    max_connections=settings.http_max_connections,
                    max_keepalive_connections=settings.http_max_keepalive_connections,
                    keepalive_expiry=settings.http_keepalive_expiry,
                ),
            )
            
            # Log connection pool configuration
            LOGGER.info(
                "HTTP client initialized with connection pool: "
                "max_connections=%d, max_keepalive_connections=%d, keepalive_expiry=%.1fs",
                settings.http_max_connections,
                settings.http_max_keepalive_connections,
                settings.http_keepalive_expiry
            )
        return self._client

    def _log_stats_if_needed(self, semaphore: Semaphore) -> None:
        """
        Log HTTP client statistics periodically (every 50 requests).

        Args:
            semaphore: The semaphore instance to check available slots
        """
        if self._request_count % 50 == 0:
            available_slots = semaphore._value
            LOGGER.info(
                HTTP_CLIENT_STATS_LOG_MSG,
                self._request_count, self._error_count,
                available_slots, settings.ibm_api_max_concurrent_calls
            )

    async def _make_request(
        self,
        request_func: Callable[[httpx.AsyncClient], Awaitable[httpx.Response]],
    ) -> dict[str, Any]:
        """
        Common request execution logic with semaphore-based concurrency control and error handling.

        Args:
            request_func: Async callable that makes the HTTP request and returns the response

        Returns:
            Dict[str, Any]: JSON response data or dict with content and content_type for non-JSON responses

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        semaphore = get_ibm_api_semaphore()
        async with semaphore:
            try:
                self._request_count += 1
                self._log_stats_if_needed(semaphore)
                
                client = await self.client
                response = await request_func(client)
                response.raise_for_status()
                
                # Handle different content types
                content_type = response.headers.get("content-type", "").lower()
                if "application/json" in content_type:
                    return response.json()
                else:
                    return {"content": response.content, "content_type": content_type}
            except httpx.HTTPStatusError as e:
                self._error_count += 1
                handle_api_exception(e)
                raise  # This line is never reached but satisfies type checker
            except httpx.RequestError as e:
                self._error_count += 1
                raise ExternalAPIError(f"HTTP request failed: {str(e)}")
            except Exception as e:
                self._error_count += 1
                raise ExternalAPIError(f"Request failed: {str(e)}")

    async def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Make async GET request with error handling and semaphore-based concurrency control.

        Args:
            url: The URL to make the GET request to
            params: Optional query parameters
            headers: Optional HTTP headers to include

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        async def request_func(client: httpx.AsyncClient) -> httpx.Response:
            return await client.get(url, params=params, headers=headers or {})
        
        return await self._make_request(request_func)

    async def _request_with_body(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Internal helper for HTTP methods with request body (POST, PUT, PATCH).
        
        Args:
            method: HTTP method name (POST, PUT, PATCH)
            url: The URL to make the request to
            data: Form data (application/x-www-form-urlencoded)
            json: JSON data (application/json). Can be dict or list for JSON PATCH operations
            params: Optional query parameters
            headers: Optional HTTP headers
            content: Raw bytes for binary uploads
            files: Multipart file uploads
            
        Returns:
            Dict[str, Any]: JSON response data
            
        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        # Validate multiple body parameters
        provided_params = sum([
            data is not None,
            json is not None,
            content is not None,
            files is not None
        ])
        
        if provided_params > 1:
            LOGGER.warning(
                f"Multiple body parameters provided to {method} {url}. "
                f"Using precedence: files > content > json > data. "
                f"Provided: data={data is not None}, json={json is not None}, "
                f"content={content is not None}, files={files is not None}"
            )
        
        async def request_func(client: httpx.AsyncClient) -> httpx.Response:
            method_func = getattr(client, method.lower())
            return await method_func(
                url,
                json=json,
                params=params,
                headers=headers or {},
                data=data,
                content=content,
                files=files,
            )
        
        return await self._make_request(request_func)

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make async POST request with error handling and semaphore-based concurrency control.

        Args:
            url: The URL to make the POST request to
            data: Form data (application/x-www-form-urlencoded).
                  Do not use with json, content, or files.
            json: JSON data (application/json).
                  Do not use with data, content, or files.
            content: Raw bytes for binary uploads (e.g., CSV, Excel files).
                     Do not use with data, json, or files.
            files: Multipart file uploads. Dictionary mapping field names to file-like objects or tuples.
                   Format: {'field_name': file_object} or {'field_name': ('filename', file_object, 'content_type')}
                   Do not use with data, json, or content.
            params: Optional query parameters
            headers: Optional HTTP headers

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        
        Warning:
            Only provide ONE of: data, json, content, or files.
            If multiple are provided, precedence is: files > content > json > data
        """
        return await self._request_with_body(
            "POST", url, data, json, params, headers, content, files
        )

    async def post_multipart(
        self,
        url: str,
        files: dict[str, tuple[str, bytes, str]],
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Make async POST request with multipart/form-data for file uploads.

        Args:
            url: The URL to make the POST request to
            files: Dictionary of files to upload. Format: {field_name: (filename, content, content_type)}
            params: Optional query parameters
            headers: Optional HTTP headers to include (Content-Type will be set automatically)

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        async def request_func(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(
                url, files=files, params=params, headers=headers or {}
            )
        
        return await self._make_request(request_func)

    async def put(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make async PUT request with error handling and semaphore-based concurrency control.

        Args:
            url: The URL to make the PUT request to
            data: Form data (application/x-www-form-urlencoded).
                  Do not use with json, content, or files.
            json: JSON data (application/json).
                  Do not use with data, content, or files.
            content: Raw bytes for binary uploads (e.g., CSV, Excel files).
                     Do not use with data, json, or files.
            files: Multipart file uploads. Dictionary mapping field names to file-like objects or tuples.
                   Format: {'field_name': file_object} or {'field_name': ('filename', file_object, 'content_type')}
                   Do not use with data, json, or content.
            params: Optional query parameters
            headers: Optional HTTP headers

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        
        Warning:
            Only provide ONE of: data, json, content, or files.
            If multiple are provided, precedence is: files > content > json > data
        """
        return await self._request_with_body(
            "PUT", url, data, json, params, headers, content, files
        )

    async def patch(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | list[dict[str, Any]] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Make async PATCH request with error handling and semaphore-based concurrency control.

        Args:
            url: The URL to make the PATCH request to
            data: Form data (application/x-www-form-urlencoded).
                  Do not use with json, content, or files.
            json: JSON data (application/json). Can be dict or list for JSON PATCH operations.
                  Do not use with data, content, or files.
            content: Raw bytes for binary uploads (e.g., CSV, Excel files).
                     Do not use with data, json, or files.
            files: Multipart file uploads. Dictionary mapping field names to file-like objects or tuples.
                   Format: {'field_name': file_object} or {'field_name': ('filename', file_object, 'content_type')}
                   Do not use with data, json, or content.
            params: Optional query parameters
            headers: Optional HTTP headers

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        
        Warning:
            Only provide ONE of: data, json, content, or files.
            If multiple are provided, precedence is: files > content > json > data
        """
        return await self._request_with_body(
            "PATCH", url, data, json, params, headers, content, files
        )

    async def delete(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Make async DELETE request with error handling and semaphore-based concurrency control.

        Args:
            url: The URL to make the DELETE request to
            params: Optional query parameters
            headers: Optional HTTP headers to include

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        async def request_func(client: httpx.AsyncClient) -> httpx.Response:
            return await client.delete(url, params=params, headers=headers or {})
        
        return await self._make_request(request_func)

    async def close(self) -> None:
        """Close the async HTTP client and clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Global shared client instance
_shared_client: AsyncHttpClient | None = None


async def get_async_http_client() -> AsyncHttpClient:
    """
    Get the global shared async HTTP client instance (singleton pattern).

    Returns:
        AsyncHttpClient: The global async HTTP client instance
    """
    global _shared_client
    if _shared_client is None:
        _shared_client = AsyncHttpClient()
    return _shared_client


# Keep backwards compatibility with sync version name
def get_http_client() -> AsyncHttpClient:
    """
    Backwards compatibility function - returns the async client.

    Note: This client must be used with await for all methods.
    """
    global _shared_client
    if _shared_client is None:
        _shared_client = AsyncHttpClient()
    return _shared_client


def handle_api_exception(e: httpx.HTTPStatusError):
    try:
        # Try to get the full JSON response - we'll extract the message in _format_exception
        error_detail = e.response.text
    except Exception:
        error_detail = str(e.response.text) if hasattr(e.response, 'text') else str(e)

    raise ExternalAPIError(
        f"HTTP error {e.response.status_code} for {e.request.url}: {error_detail}"
    )