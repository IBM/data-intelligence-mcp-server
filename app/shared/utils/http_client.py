# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Async HTTP client with connection pooling and error handling."""

from typing import Any

import httpx

from app.core.settings import settings
from app.shared.exceptions.base import ExternalAPIError
from app.shared.utils.ssl_utils import get_ssl_verify_setting


class AsyncHttpClient:
    """
    Async HTTP client with connection pooling and automatic retry logic.

    This class provides an async HTTP client with connection pooling,
    SSL verification, and proper error handling for external API calls.
    """

    def __init__(self) -> None:
        """Initialize the HTTP client with lazy loading."""
        self._client: httpx.AsyncClient | None = None

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
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            )
        return self._client

    async def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Make async GET request with error handling.

        Args:
            url: The URL to make the GET request to
            headers: Optional HTTP headers to include

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        try:
            client = await self.client
            response = await client.get(url, params=params, headers=headers or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise ExternalAPIError(f"HTTP request failed: {str(e)}")
        except Exception as e:
            raise ExternalAPIError(f"Request failed: {str(e)}")

    async def post(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        """
        Make async POST request with error handling.

        Args:
            url: The URL to make the POST request to
            data: Optional JSON data to send in the request body
            headers: Optional HTTP headers to include

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        try:
            client = await self.client
            if content_type == "application/x-www-form-urlencoded":
                response = await client.post(
                    url, data=data, params=params, headers=headers or {}
                )
            else:
                response = await client.post(
                    url, json=data, params=params, headers=headers or {}
                )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise ExternalAPIError(f"HTTP request failed: {str(e)}")
        except Exception as e:
            raise ExternalAPIError(f"Request failed: {str(e)}")
        
    async def patch(
        self,
        url: str,
        data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content_type: str = "application/json"
    ) -> dict[str, Any]:
        """
        Make async PATCH request with error handling.

        Args:
            url: The URL to make the PATCH request to
            data: Optional JSON data to send in the request body
            params: Optional query parameters to include in the request
            headers: Optional HTTP headers to include
            content_type: MIME type of the request body (default: application/json)

        Returns:
            Dict[str, Any]: JSON response data

        Raises:
            ExternalAPIError: If the request fails or returns an error status
        """
        try:
            client = await self.client
            if content_type == "application/x-www-form-urlencoded":
                response = await client.patch(url, data=data, params=params, headers=headers or {})
            else:
                response = await client.patch(url, json=data, params=params, headers=headers or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise ExternalAPIError(f"HTTP request failed: {str(e)}")
        except Exception as e:
            raise ExternalAPIError(f"Request failed: {str(e)}")


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
