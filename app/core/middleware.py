# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

# This file has been modified with the assistance of IBM Bob AI tool

#Enhanced validation error handling middleware with meaningful error messages.

import logging
from collections.abc import Callable
from typing import Any, NoReturn

from mcp import McpError
from mcp.types import ErrorData
from mcp.types import INVALID_PARAMS
from pydantic import ValidationError as PydanticValidationError

from fastmcp.exceptions import ValidationError as FastMCPValidationError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext


class ValidationErrorHandlingMiddleware(Middleware):
    """Middleware that provides meaningful error messages for parameter validation errors.

    This middleware catches validation errors and transforms them into user-friendly
    error messages that explain what went wrong and how to fix it. This is
    especially useful when clients send parameters that don't match the expected
    schema (e.g., not wrapped in the correct request structure).

    Example:
        ```python
        from fastmcp import FastMCP
        from fastmcp_validation_error_handler import ValidationErrorHandlingMiddleware

        mcp = FastMCP("MyServer", strict_input_validation=True)
        mcp.add_middleware(ValidationErrorHandlingMiddleware())
        ```

    The middleware enhances errors for:
    - Missing required parameters
    - Wrong parameter types
    - Invalid parameter values
    - Extra parameters not in schema
    - Malformed parameter structures
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ):
        """Initialize validation error handling middleware.

        Args:
            logger: Logger instance for error logging. If None, uses
                'fastmcp.validation_errors'
        """
        self.logger = logger or logging.getLogger("fastmcp.validation_errors")

    async def on_message(
        self, context: MiddlewareContext, call_next: CallNext
    ) -> Any:
        """Handle validation errors for all messages."""
        try:
            return await call_next(context)
        except PydanticValidationError as e:
            # Pydantic validation error from MCP SDK or FastMCP
            return self._handle_pydantic_validation_error(e, context)
        except FastMCPValidationError as e:
            # FastMCP validation error
            return self._handle_pydantic_validation_error(e, context)

    def _handle_pydantic_validation_error(
        self, error: PydanticValidationError, context: MiddlewareContext
    ) -> NoReturn:
        """Handle Pydantic validation errors with meaningful messages."""
        error_details = error.errors()

        # Build error messages with actual validation details
        error_parts = ["Parameter validation failed:"]
        for error_detail in error_details:
            field = " -> ".join(str(loc) for loc in error_detail.get("loc", []))
            msg = error_detail.get("msg", "Unknown error")
            error_parts.append(f"  - {field}: {msg}")

        suggestions = []
        for error_detail in error_details:
            loc = error_detail.get("loc", [])
            error_type = error_detail.get("type", "")
            
            # Handle missing request argument
            if error_type == 'missing_argument' and loc and loc[0] == 'request':
                suggestions.append("Wrap tool call arguments in a request object")
            
            # Handle type errors
            elif error_type in ['int_parsing', 'float_parsing', 'bool_parsing', 
                                'string_too_short', 'string_too_long']:
                suggestions.append(f"Check the type of parameter '{' -> '.join(str(l) for l in loc)}'")
            
            # Handle format errors
            elif error_type in ['email', 'url', 'json']:
                suggestions.append(f"Ensure parameter '{' -> '.join(str(l) for l in loc)}' has correct format")
            
            # Handle value range errors
            elif error_type in ['greater_than', 'less_than', 'multiple_of']:
                suggestions.append(f"Ensure parameter '{' -> '.join(str(l) for l in loc)}' is within valid range")
            
            # Handle enum errors
            elif error_type == 'literal_error':
                suggestions.append(f"Parameter '{' -> '.join(str(l) for l in loc)}' must be one of the allowed values")

        # Add suggestions if available
        if suggestions:
            error_parts.append("\nSuggestions:")
            error_parts.extend(f"  - {s}" for s in suggestions)

        # Log the error
        self.logger.warning(
            f"Parameter validation error in {context.method or 'unknown'}: "
            f"{error_details}"
        )

        # Raise MCP error with code INVALID_PARAMS (Invalid Params)
        message = "\n".join(error_parts)
        raise McpError(ErrorData(code=INVALID_PARAMS, message=message)) from error
