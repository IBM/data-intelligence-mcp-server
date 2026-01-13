# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI Tool

import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from app.core.auth import get_access_token
from app.core.settings import settings
from app.services.constants import JSON_CONTENT_TYPE, JSON_PATCH_CONTENT_TYPE
from app.shared.exceptions.base import ExternalAPIError, ServiceError
from app.shared.logging.utils import LOGGER
from app.shared.utils.http_client import get_http_client


def create_default_headers(
    content_type: str = JSON_CONTENT_TYPE,
    accept_type: str = JSON_CONTENT_TYPE,
    additional_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Create headers for API requests.

    Args:
        content_type: Content type for the request
        accept_type: Accept type for the request
        include_auth: Whether to include authorization header
        additional_headers: Additional headers to include

    Returns:
        Dict[str, str]: Headers for the request
    """
    headers = {"Content-Type": content_type, "accept": accept_type}

    if additional_headers:
        headers.update(additional_headers)

    return headers


class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    PATCH = "PATCH"
    PUT = "PUT"
    DELETE = "DELETE"


class ToolHelperService:
    """
    Base class for tool service that provides common functionality for making API calls,
    handling errors.
    """

    def __init__(self):
        self.base_url = settings.di_service_url
        self.resource_controller_url = settings.resource_controller_url
        self.user_management_url = settings.user_management_url
        self.ui_base_url = settings.ui_url
        self.http_client = get_http_client()

    async def execute_get_request(
        self,
        url: str,
        headers: Dict[str, str] = create_default_headers(),
        params: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a GET request with authorization header and handle common error patterns.

        Args:
            url: URL for the request
            headers: Headers for the request
            params: Query parameters
            timeout: Request timeout in seconds
            tool_name: Name of the tool making the request (for error messages)

        Returns:
            Dict[str, Any]: JSON response

        Raises:
            ExternalAPIError: If the request fails
            ServiceError: If the response status code is 404
        """
        headers["Authorization"] = await get_access_token()
        try:
            response_json = await self.http_client.get(
                url=url, headers=headers, params=params
            )

            return response_json
        except ExternalAPIError as e:
            LOGGER.error(
                f"{tool_name or 'Request'} to {url} failed with error: {str(e)}"
            )
            raise self._format_exception(e, HTTPMethod.GET, tool_name)

    async def execute_post_request(
        self,
        url: str,
        headers: Dict[str, str] = create_default_headers(),
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a POST request with authorization header and handle common error patterns.

        Args:
            url: URL for the request
            headers: Headers for the request
            payload: JSON data for the request body
            params: Query parameters
            tool_name: Name of the tool making the request (for error messages)

        Returns:
            Dict[str, Any]: JSON response

        Raises:
            ExternalAPIError: If the request fails
        """
        headers["Authorization"] = await get_access_token()
        try:
            response_json = await self.http_client.post(
                url=url, data=json, headers=headers, params=params
            )

            return response_json
        except ExternalAPIError as e:
            LOGGER.error(
                f"{tool_name or 'Request'} to {url} failed with error: {str(e)}"
            )
            raise self._format_exception(e, HTTPMethod.POST, tool_name)

    async def execute_put_request(
        self,
        url: str,
        headers: Dict[str, str] = create_default_headers(),
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a PUT request with authorization header and handle common error patterns.

        Args:
            url: URL for the request
            headers: Headers for the request
            payload: JSON data for the request body
            params: Query parameters
            tool_name: Name of the tool making the request (for error messages)

        Returns:
            Dict[str, Any]: JSON response

        Raises:
            ExternalAPIError: If the request fails
        """
        headers["Authorization"] = await get_access_token()
        try:
            response_json = await self.http_client.put(
                url=url, data=json, headers=headers, params=params
            )

            return response_json
        except ExternalAPIError as e:
            LOGGER.error(
                f"{tool_name or 'Request'} to {url} failed with error: {str(e)}"
            )
            raise self._format_exception(e, HTTPMethod.PUT, tool_name)

    async def execute_patch_request(
        self,
        url: str,
        headers: Dict[str, str] = create_default_headers(content_type=JSON_PATCH_CONTENT_TYPE),
        json: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        params: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a PATCH request with authorization header and handle common error patterns.

        Args:
            url: URL for the request
            headers: Headers for the request
            json: JSON data for the request body (can be dict or list for JSON PATCH operations)
            params: Query parameters
            tool_name: Name of the tool making the request (for error messages)

        Returns:
            Dict[str, Any]: JSON response

        Raises:
            ExternalAPIError: If the request fails
        """
        headers["Authorization"] = await get_access_token()

        try:
            response_json = await self.http_client.patch(
                url=url, data=json, headers=headers, params=params
            )

            return response_json
        except ExternalAPIError as e:
            LOGGER.error(
                f"{tool_name or 'Request'} to {url} failed with error: {str(e)}"
            )
            raise self._format_exception(e, HTTPMethod.PATCH, tool_name)

    def _format_exception(
        self,
        exception: ExternalAPIError,
        method: HTTPMethod,
        tool_name: Optional[str] = None,
    ) -> ExternalAPIError | ServiceError:
        """
        Handle API error with smart formatting and truncation.

        Extracts status code, error type, and sanitizes error messages to provide
        user-friendly error messages while preventing information overload.

        Args:
            exception: ExternalAPIError
            method: HTTPMethod
            tool_name: Name of the tool making the request (for error messages)

        Returns:
            Dict[str, Any]: JSON response if successful

        Raises:
            ServiceError: If the response status code is 404 or 403
            ExternalAPIError: For other error status codes
        """
        status_code = self._parse_status_code(exception.message)
        error_detail = self._extract_error_detail(exception.message)
        error_category = self._get_error_category(status_code)
        sanitized_message = self._get_sanitized_message(status_code, error_detail)
        
        error_message = self._build_error_message(
            tool_name, error_category, status_code, sanitized_message, error_detail
        )
        
        return self._raise_formatted_error(
            status_code, method, error_message, exception.message
        )
    
    def _parse_status_code(self, message: str) -> str | None:
        """Parse status code from exception message."""
        status_code_match = re.search(r"HTTP error (\d+)", message)
        return status_code_match.group(1) if status_code_match else None
    
    def _extract_error_detail(self, message: str) -> str:
        """Extract error detail from exception message."""
        error_detail_match = re.search(r"HTTP error \d+ for .+?: (.+)", message, re.DOTALL)
        if error_detail_match:
            return error_detail_match.group(1).strip()
        
        LOGGER.debug(f"Could not find error_detail pattern in exception.message: {message[:200]}")
        return ""
    
    def _get_error_category(self, status_code: str | None) -> str:
        """Get error category from status code."""
        if status_code and status_code.isdigit():
            return self._categorize_error(int(status_code))
        return "Unknown Error"
    
    def _get_sanitized_message(self, status_code: str | None, error_detail: str) -> str:
        """Get sanitized message from error detail, skipping for 500 errors."""
        if status_code == "500":
            return ""
        
        LOGGER.debug(f"Extracting message from error_detail (first 200 chars): {error_detail[:200]}")
        sanitized = self._extract_error_message(error_detail, max_length=250)
        LOGGER.debug(f"Extracted sanitized_message: {sanitized[:100] if sanitized else 'EMPTY'}")
        return sanitized

    def _get_error_message_code(self, error_detail: str) -> str:
        LOGGER.debug(f"Extracting error message code from error_detail (first 200 chars): {error_detail[:200]}")
        error_message_code = self._extract_error_message_code(error_detail)
        LOGGER.debug(f"Extracted error message code: {error_message_code}")
        return error_message_code
    
    def _build_error_message(
        self, tool_name: Optional[str], error_category: str, 
        status_code: str | None, sanitized_message: str, error_detail: str
    ) -> str:
        """Build formatted error message."""
        tool_display = tool_name or 'request'
        base_message = f"Tool {tool_display} call failed: {error_category}"
        
        if status_code == "500":
            return f"{base_message} (Status: {status_code}). Internal server error."
        
        if status_code == "404":
            error_message_code = self._get_error_message_code(error_detail)
            
            # Handle "not_implemented" error code
            not_implemented_error = self._handle_not_implemented_error(error_message_code, base_message, status_code, sanitized_message)
            if not_implemented_error:
                return not_implemented_error
            
            # Default 404 message
            message = f"{base_message} (Status: {status_code}). Resource was not found."
            return f"{message} {sanitized_message}" if sanitized_message else message
        
        if status_code == "403":
            message = f"{base_message} (Status: {status_code}). Operation is forbidden."
            return f"{message} {sanitized_message}" if sanitized_message else message
        
        if status_code:
            message = f"{base_message} (Status: {status_code})"
            return f"{message}. {sanitized_message}" if sanitized_message else message
        
        # Fallback if we can't parse status code
        return f"{base_message}. {sanitized_message}" if sanitized_message else base_message
    
    def _handle_not_implemented_error(self, error_message_code: str, base_message: str, status_code: str, sanitized_message: str) -> str | None:
        if error_message_code.lower() == "not_implemented" and settings.di_env_mode == "CPD":
            message = f"{base_message} (Status: {status_code}). This capability is not available in this CPD version or the functionality is not enabled. Please refer to https://github.com/IBM/data-intelligence-mcp-server/blob/main/TOOLS_PROMPTS.md (TOOLS_PROMPTS.md) for information about the versions where this is available. Consider upgrading to the right version to access this capability."
            return f"{message} {sanitized_message}" if sanitized_message else message

        if error_message_code.lower() == "not_implemented" and settings.di_env_mode == "SaaS":
            message = f"{base_message} (Status: {status_code}). This capability is not available in this SaaS version or the functionality is not enabled."
            return f"{message} {sanitized_message}" if sanitized_message else message

    def _raise_formatted_error(
        self, status_code: str | None, method: HTTPMethod, 
        error_message: str, original_message: str
    ) -> ExternalAPIError | ServiceError:
        """Raise appropriate error type based on status code."""
        LOGGER.error(f"{error_message}, Full exception: {original_message}")
        
        if status_code == "404" and method == HTTPMethod.GET:
            raise ServiceError(error_message)
        
        if status_code == "403":
            raise ServiceError(error_message)
        
        raise ExternalAPIError(error_message)
    
    def _categorize_error(self, status_code: int) -> str:
        """
        Categorize HTTP error by status code.
        
        Args:
            status_code: HTTP status code
            
        Returns:
            str: Error category name
        """
        if 400 <= status_code < 500:
            if status_code == 400:
                return "Validation Error"
            elif status_code == 401:
                return "Authentication Error"
            elif status_code == 403:
                return "Authorization Error"
            elif status_code == 404:
                return "Not Found Error"
            elif status_code == 422:
                return "Validation Error"
            else:
                return "Client Error"
        elif 500 <= status_code < 600:
            return "Server Error"
        else:
            return "Unknown Error"
    
    def _extract_error_message(self, error_detail: str, max_length: int = 250) -> str:
        """
        Extract error message from error detail.
        If error_detail is JSON, tries to extract message from errors array or message field.
        Otherwise, returns empty string to show only categorized error.
        
        Args:
            error_detail: Original error detail (could be JSON string or plain text)
            max_length: Maximum length for the extracted message
            
        Returns:
            str: Extracted and sanitized error message, or empty string if no message found
        """
        if not error_detail:
            return ""
        
        json_str = self._find_json_string(error_detail)
        if not json_str:
            return ""
        
        error_json = self._parse_json_safely(json_str)
        if error_json is None:
            return ""
        
        # Try to extract message from errors array first
        message = self._extract_message_from_errors_array(error_json, max_length)
        if message:
            return message
        
        # Fallback to top-level message field
        message = self._extract_message_from_top_level(error_json, max_length)
        if message:
            return message
        
        # No message found
        LOGGER.debug(f"Could not extract message from error_json. Keys: {list(error_json.keys()) if isinstance(error_json, dict) else 'not a dict'}")
        return ""

    def _extract_error_message_code(self, error_detail: str) -> str:
        """
        Extract error message code from error detail.
        If error_detail is JSON, tries to extract message code from errors array or message field.
        Otherwise, returns empty string to show only categorized error.
        
        Args:
            error_detail: Original error detail (could be JSON string or plain text)
            
        Returns:
            str: Extracted and sanitized error message code, or empty string if no message found
        """
        if not error_detail:
            return ""
        
        json_str = self._find_json_string(error_detail)
        if not json_str:
            return ""
        
        error_json = self._parse_json_safely(json_str)
        if error_json is None:
            return ""
        
        # Try to extract error message code from errors array first
        message = self._extract_message_code_from_errors_array(error_json)
        if message:
            return message
        
        # No error message code found
        LOGGER.debug(f"Could not extract error message code from error_json. Keys: {list(error_json.keys()) if isinstance(error_json, dict) else 'not a dict'}")
        return ""
    
    def _find_json_string(self, error_detail: str) -> str:
        """Find and extract JSON string from error detail."""
        for i, char in enumerate(error_detail):
            if char in ['{', '[']:
                return error_detail[i:]
        
        LOGGER.debug(f"No JSON found in error_detail: {error_detail[:100]}")
        return ""
    
    def _parse_json_safely(self, json_str: str) -> dict | list | None:
        """Parse JSON string safely, returning None on failure."""
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as e:
            LOGGER.error(f"Failed to parse error_detail as JSON: {e}. JSON string: {json_str[:200]}")
            return None
    
    def _extract_message_from_errors_array(self, error_json: dict | list, max_length: int) -> str:
        """Extract message from errors array if present."""
        if not isinstance(error_json, dict) or "errors" not in error_json:
            return ""
        
        errors = error_json.get("errors", [])
        if not isinstance(errors, list) or len(errors) == 0:
            LOGGER.debug(f"errors is not a list or is empty: {errors}")
            return ""
        
        first_error = errors[0]
        if not isinstance(first_error, dict) or "message" not in first_error:
            LOGGER.debug(f"first_error is not dict or has no message: {first_error}")
            return ""
        
        message = first_error.get("message", "")
        if message:
            LOGGER.debug(f"Extracted message from errors[0]: {message[:100]}")
            return self._sanitize_error_message(message, max_length)
        
        return ""
        
    def _extract_message_code_from_errors_array(self, error_json: dict | list) -> str:
        """Extract message code from errors array if present."""
        if not isinstance(error_json, dict) or "errors" not in error_json:
            return ""
        
        errors = error_json.get("errors", [])
        if not isinstance(errors, list) or len(errors) == 0:
            LOGGER.debug(f"errors is not a list or is empty: {errors}")
            return ""
        
        first_error = errors[0]
        if not isinstance(first_error, dict) or "code" not in first_error:
            LOGGER.debug(f"first_error is not dict or has no error message code: {first_error}")
            return ""
        
        message = first_error.get("code", "")
        return message
    
    def _extract_message_from_top_level(self, error_json: dict | list, max_length: int) -> str:
        """Extract message from top-level message field if present."""
        if not isinstance(error_json, dict) or "message" not in error_json:
            return ""
        
        message = error_json.get("message", "")
        if message:
            LOGGER.debug(f"Extracted message from top-level: {message[:100]}")
            return self._sanitize_error_message(message, max_length)
        
        return ""
    
    def _sanitize_error_message(self, error_message: str, max_length: int = 250) -> str:
        """
        Sanitize and truncate error message to prevent information overload and leak sensitive data.
        
        Args:
            error_message: Original error message
            max_length: Maximum length for the sanitized message
            
        Returns:
            str: Sanitized and truncated error message
        """
        if not error_message:
            return ""
        
        sanitized = error_message
        
        # IMPORTANT: Order matters - sanitize most specific patterns first
        
        # Remove URLs first (but keep domain for context) - do this before token sanitization
        # to avoid partial matches in URLs
        sanitized = re.sub(r'https?://[^\s]+', '[URL]', sanitized)
        
        # Remove database connection strings (contains credentials, do before generic token matching)
        sanitized = re.sub(r'\b(?:postgresql|postgres|mysql|mongodb|redis|mssql|sqlserver|oracle|sqlite)://[^\s]+', 
                          '[DATABASE_URL]', sanitized, flags=re.IGNORECASE)
        
        # Remove potential AWS/Azure/GCP keys or ARNs (specific patterns before generic tokens)
        # Note: Using [a-z0-9] instead of [a-zA-Z0-9] since IGNORECASE flag makes case redundant
        # Note: Escaping - to avoid it being interpreted as a range operator (which would create duplicates with 0-9)
        sanitized = re.sub(r'\b(?:AKIA|ASIA|arn:aws|azure-|gcp-)[a-z0-9/_\-]+', '[CLOUD_CREDENTIAL]', sanitized, flags=re.IGNORECASE)
        
        # Remove Bearer tokens (Bearer followed by alphanumeric string) - specific pattern
        # Note: Using [a-z0-9] instead of [a-zA-Z0-9] since IGNORECASE flag makes case redundant
        # Note: Escaping - to avoid it being interpreted as a range operator
        sanitized = re.sub(r'\bBearer\s+[a-z0-9_\-]{20,}\b', 'Bearer [REDACTED]', sanitized, flags=re.IGNORECASE)
        
        # Handle Stripe-style keys (sk_live_..., pk_test_...) - specific pattern
        # Note: Using [a-z0-9] instead of [A-Za-z0-9] since IGNORECASE flag makes case redundant
        sanitized = re.sub(r'\b(sk|pk|rk)_(live|test|prod)_[a-z0-9]{24,}\b', r'\1_\2_[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        # Remove potential API keys with prefixes (e.g., "apikey:abc123...", "token:...")
        # Note: api[_-]?key already matches "apikey" (when optional [_-]? is empty), so "apikey" is redundant
        sanitized = re.sub(r'\b(api[_-]?key|token|secret|password|pwd|credential|auth[_-]?token)[=:]\s*[^\s]+', 
                          r'\1=[REDACTED]', sanitized, flags=re.IGNORECASE)
        
        # Remove potential API keys, tokens, or secrets (long alphanumeric strings)
        # Catch strings of 32+ characters (common token/secret lengths) - do this after specific patterns
        sanitized = re.sub(r'\b[a-zA-Z0-9]{32,}\b', '[REDACTED]', sanitized)
        
        # Remove potential email addresses (but keep domain context)
        sanitized = re.sub(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', '[EMAIL]', sanitized)
        
        # Remove potential IP addresses (IPv4)
        sanitized = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', '[IP]', sanitized)
        # Remove IPv6 addresses (simplified pattern)
        sanitized = re.sub(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b', '[IP]', sanitized)
        
        # Remove potential file paths with sensitive names (e.g., /home/user/.ssh/id_rsa)
        # Match paths containing sensitive keywords or file extensions
        sanitized = re.sub(r'[/\\][^\s]*(?:passwd|password|secret|key|credential|token|\.env|\.pem|\.key|\.p12|\.pfx|id_rsa|id_dsa|id_ed25519)[^\s]*', 
                          '[FILE_PATH]', sanitized, flags=re.IGNORECASE)
        
        # Remove potential UUIDs (which might be sensitive IDs) - do before generic alphanumeric
        sanitized = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 
                          '[UUID]', sanitized, flags=re.IGNORECASE)
        
        # Remove potential credit card numbers (16 digits, possibly with spaces or dashes)
        sanitized = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[CREDIT_CARD]', sanitized)
        
        # Remove potential SSN (XXX-XX-XXXX)
        sanitized = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', sanitized)
        
        # Remove potential phone numbers (various formats)
        sanitized = re.sub(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE]', sanitized)
        
        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rsplit(' ', 1)[0] + "... (message truncated)"
        
        return sanitized.strip()


tool_helper_service = ToolHelperService()
