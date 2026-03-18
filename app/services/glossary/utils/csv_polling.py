# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

"""CSV import polling utilities for glossary import."""

import asyncio
from typing import Dict, Any

from app.core.auth import get_access_token
from app.core.settings import settings
from app.services.glossary.constants import (
    IMPORT_COMPLETION_STATUSES,
    GLOSSARY_IMPORT_STATUS_ENDPOINT,
    DEFAULT_POLL_MAX_WAIT_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
)
from app.shared.exceptions.base import ServiceError
from app.shared.logging import LOGGER


async def poll_import_status(
    process_id: str,
    max_wait_seconds: int = DEFAULT_POLL_MAX_WAIT_SECONDS,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS
) -> Dict[str, Any]:
    """
    Poll the import status endpoint until completion or timeout.
    
    Args:
        process_id: The process ID returned from the import API
        max_wait_seconds: Maximum time to wait in seconds (default: 120)
        poll_interval: Time between polls in seconds (default: 2.0)
        
    Returns:
        Final status response from the API
        
    Raises:
        ServiceError: If polling fails or times out
    """
    from app.shared.utils.http_client import get_async_http_client
    
    http_client = await get_async_http_client()
    
    # Build the status URL
    url = f"{settings.di_service_url}{GLOSSARY_IMPORT_STATUS_ENDPOINT}/{process_id}"
    
    auth_token = await get_access_token()
    if not auth_token:
        raise ServiceError("Failed to obtain authorization token")
    
    headers = {
        'Authorization': auth_token
    }
    
    start_time = asyncio.get_event_loop().time()
    elapsed = 0
    
    LOGGER.info(f"Starting to poll import status for process_id={process_id}")
    
    while elapsed < max_wait_seconds:
        try:
            # Poll the status endpoint
            response = await http_client.get(url=url, headers=headers)
            
            status = response.get('status', 'UNKNOWN')
            LOGGER.info(f"Import status poll: process_id={process_id}, status={status}, elapsed={elapsed:.1f}s")
            
            # Check if import is complete
            if status in IMPORT_COMPLETION_STATUSES:
                LOGGER.info(f"Import process completed with status: {status}")
                return response
            
            await asyncio.sleep(poll_interval)
            elapsed = asyncio.get_event_loop().time() - start_time
            
        except Exception as e:
            LOGGER.error(f"Error polling import status: {str(e)}")
            # Continue polling unless we've exceeded max wait time
            if elapsed >= max_wait_seconds:
                raise ServiceError(f"Import status polling failed: {str(e)}")
            await asyncio.sleep(poll_interval)
            elapsed = asyncio.get_event_loop().time() - start_time
    
    # Timeout reached
    raise ServiceError(f"Import process timed out after {max_wait_seconds} seconds. Process ID: {process_id}")