# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import asyncio
from functools import wraps
from typing import Optional, Tuple, Type, Callable

from app.shared.logging import LOGGER
from botocore.exceptions import ClientError

def _should_retry_exception(
    exception: Exception,
    retry_condition: Optional[Callable[[Exception], bool]]
) -> bool:
    """
    Determine if an exception should trigger a retry.
    
    Args:
        exception: The exception that was raised
        retry_condition: Optional callable to check if retry should occur
        
    Returns:
        True if the exception should be retried, False otherwise
    """
    return retry_condition(exception) if retry_condition else True


async def _handle_retry_attempt(
    label: str,
    attempt: int,
    total_attempts: int,
    exception: Exception,
    backoff_factor: float
) -> None:
    """
    Handle logging and delay for a retry attempt.
    
    Args:
        label: Context label for logging
        attempt: Current attempt number (0-indexed)
        total_attempts: Total number of attempts allowed
        exception: The exception that triggered the retry
        backoff_factor: Base for exponential backoff calculation
    """
    if attempt < total_attempts - 1:
        delay = backoff_factor ** attempt
        LOGGER.warning(
            f"[{label}] Attempt {attempt + 1}/{total_attempts} failed: {exception}. "
            f"Retrying in {delay}s..."
        )
        await asyncio.sleep(delay)
    else:
        LOGGER.error(
            f"[{label}] All {total_attempts} attempts failed: {exception}"
        )


def retry_on_failure(
    max_retries: int,
    backoff_factor: float,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    context_label: Optional[str] = None,
    retry_condition: Optional[Callable[[Exception], bool]] = None,
):
    """
    Async decorator to retry a coroutine on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (total attempts = max_retries + 1)
        backoff_factor: Base for exponential backoff delay (delay = backoff_factor ** attempt).
                        With the default of 2.0: attempt 0 → 1s, attempt 1 → 2s, attempt 2 → 4s, etc.
        exceptions: Tuple of exception types to catch and retry on. Defaults to (Exception,).
        context_label: Optional label included in log messages for context (e.g. a document number).
                       Defaults to the decorated function's __name__.
        retry_condition: Optional callable that takes an exception and returns True if retry should occur.
                        If None, all exceptions in the exceptions tuple will be retried.
                        Example: lambda e: hasattr(e, 'response') and e.response.status_code == 429
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            label = context_label if context_label is not None else func.__name__
            last_exception: Optional[Exception] = None
            total_attempts = max_retries + 1
            
            for attempt in range(total_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if not _should_retry_exception(e, retry_condition):
                        raise
                    
                    last_exception = e
                    await _handle_retry_attempt(label, attempt, total_attempts, e, backoff_factor)
            
            if last_exception is not None:
                raise last_exception
            raise RuntimeError(f"[{label}] retry_on_failure called with max_retries=0")
        return wrapper
    return decorator

def retry_on_expired_aws_token(func):
    """
    Async decorator to retry a coroutine on expiry of AWS Token.

    Decorator expects `self` to implement:
    async def refresh_credentials() -> bool

    Args:
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
                   
        try:
            return await func(self, *args, **kwargs)

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')

            if error_code == 'ExpiredToken':
                LOGGER.warning(f"{func.__name__} failed with ExpiredToken, refreshing token...")

                if await self.refresh_credentials():
                    return await func(self, *args, **kwargs)

            raise

    return wrapper
