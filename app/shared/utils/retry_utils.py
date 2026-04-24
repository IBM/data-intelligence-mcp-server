# Copyright [2026] [IBM]
# Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0)
# See the LICENSE file in the project root for license information.

import asyncio
from functools import wraps
from typing import Optional, Tuple, Type

from app.shared.logging import LOGGER


def retry_on_failure(
    max_retries: int,
    backoff_factor: float,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    context_label: Optional[str] = None,
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
                    last_exception = e
                    if attempt < total_attempts - 1:
                        delay = backoff_factor ** attempt
                        LOGGER.warning(
                            f"[{label}] Attempt {attempt + 1}/{total_attempts} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        LOGGER.error(
                            f"[{label}] All {total_attempts} attempts failed: {e}"
                        )
            if last_exception is not None:
                raise last_exception
            raise RuntimeError(f"[{label}] retry_on_failure called with max_retries=0")
        return wrapper
    return decorator

