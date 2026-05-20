# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""Common utility functions for lineage services."""

from typing import Callable, TypeVar, Any
from app.services.lineage.constants import (
    HTTP_STATUS_500_INTERNAL_SERVER_ERROR,
)
from app.shared.exceptions.base import ExternalAPIError

T = TypeVar('T')


def handle_500_error(
    error: ExternalAPIError,
    error_response_factory: Callable[[], T]
) -> T:
    """
    Check if an ExternalAPIError is a 500 error and return appropriate response.
    """
    error_message_lower = str(error.message).lower()
    status_pattern = f"status: {HTTP_STATUS_500_INTERNAL_SERVER_ERROR}".lower()
    
    # Check for both formats: "status: 500" and "(status: 500)"
    if f"({status_pattern})" in error_message_lower or status_pattern in error_message_lower:
        return error_response_factory()
    
    # Not a 500 error, re-raise the original exception
    raise error