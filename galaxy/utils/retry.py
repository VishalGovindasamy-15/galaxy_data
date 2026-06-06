"""Retry logic with exponential backoff."""
import asyncio
import functools
import logging
from typing import Callable, Any

log = logging.getLogger("galaxy.retry")


async def retry_async(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
) -> Any:
    """Execute async function with exponential backoff retry."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except exceptions as e:
            last_error = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                log.warning(f"Attempt {attempt+1}/{max_retries+1} failed: {e}. Retrying in {delay}s")
                await asyncio.sleep(delay)
            else:
                log.error(f"All {max_retries+1} attempts failed: {e}")
    raise last_error


def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for async functions with retry logic."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                base_delay=base_delay,
            )
        return wrapper
    return decorator
