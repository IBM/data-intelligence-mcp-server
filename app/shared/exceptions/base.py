# Copyright [2025] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Base exception classes for MCP services."""


class MCPServiceError(Exception):
    """
    Base exception for MCP service errors.

    Attributes:
        message: The error message
        service: The service name where the error occurred (optional)
        tool: The tool name where the error occurred (optional)
    """

    def __init__(self, message: str, service: str = "", tool: str = "") -> None:
        """Initialize MCPServiceError with message and optional context."""
        super().__init__(message)
        self.message = message
        self.service = service
        self.tool = tool


class ServiceError(MCPServiceError):
    """General service error for business logic failures."""


class ConfigurationError(MCPServiceError):
    """Configuration-related errors like missing settings or invalid config."""


class ValidationError(MCPServiceError):
    """Input validation errors for malformed or invalid data."""


class ExternalAPIError(MCPServiceError):
    """External API communication errors like timeouts or HTTP failures."""
