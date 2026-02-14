"""
Retry logic utilities with exponential backoff and jitter.

Provides robust error handling for external API calls.
"""

import random
import time
from typing import Callable, TypeVar, Any
from functools import wraps
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)
import httpx

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

T = TypeVar("T")


class APIError(Exception):
    """Raised when API call fails with a retriable error."""

    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    pass


def exponential_backoff_with_jitter(attempt_number: int, base: int = 2, max_wait: int = 60) -> float:
    """
    Calculate wait time with exponential backoff and jitter.

    This prevents "thundering herd" problem when multiple requests
    retry simultaneously.

    Formula: wait = min(base^attempt, max_wait) + random(0, 1)

    Args:
        attempt_number: Current retry attempt (0-indexed)
        base: Base for exponential calculation (default 2)
        max_wait: Maximum wait time in seconds

    Returns:
        Wait time in seconds

    Example:
        >>> exponential_backoff_with_jitter(0)  # First retry
        2.0 to 3.0 seconds
        >>> exponential_backoff_with_jitter(3)  # Fourth retry
        8.0 to 9.0 seconds
    """
    base_wait = min(base**attempt_number, max_wait)
    jitter = random.uniform(0, 1)
    wait_time = base_wait + jitter

    logger.debug(f"Retry attempt {attempt_number}: waiting {wait_time:.2f}s")
    return wait_time


def should_retry_http_error(exception: Exception) -> bool:
    """
    Determine if an HTTP error should be retried.

    Retries on:
    - Network errors (connection, timeout)
    - Server errors (5xx)
    - Rate limit errors (429)

    Does NOT retry on:
    - Client errors (4xx except 429)
    - Authentication errors (401, 403)

    Args:
        exception: Exception to check

    Returns:
        True if should retry, False otherwise
    """
    if isinstance(exception, httpx.TimeoutException):
        logger.warning("Request timeout - will retry")
        return True

    if isinstance(exception, httpx.NetworkError):
        logger.warning(f"Network error - will retry: {exception}")
        return True

    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code

        # Rate limiting - always retry
        if status_code == 429:
            logger.warning("Rate limit exceeded - will retry with backoff")
            return True

        # Server errors - retry
        if 500 <= status_code < 600:
            logger.warning(f"Server error {status_code} - will retry")
            return True

        # Client errors - don't retry (except 429 handled above)
        if 400 <= status_code < 500:
            logger.error(f"Client error {status_code} - will NOT retry")
            return False

    # Unknown error type - don't retry by default
    return False


def retry_with_backoff(
    max_attempts: int = 3,
    min_wait: int = 2,
    max_wait: int = 10,
    exceptions: tuple = (httpx.HTTPError, APIError),
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_attempts=3)
        def fetch_data(url):
            response = httpx.get(url)
            response.raise_for_status()
            return response.json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(exceptions),
            reraise=True,
        )
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                # Check if we should retry this specific HTTP error
                if should_retry_http_error(e):
                    raise APIError(f"Retriable API error: {e}") from e
                else:
                    # Don't retry - raise original exception
                    raise

        return wrapper

    return decorator


def call_with_retry(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    **kwargs,
) -> T:
    """
    Call a function with retry logic (functional interface).

    Alternative to decorator when you need one-off retry behavior.

    Args:
        func: Function to call
        *args: Positional arguments to pass to func
        max_attempts: Maximum retry attempts
        **kwargs: Keyword arguments to pass to func

    Returns:
        Function result

    Raises:
        Exception: If all retries exhausted

    Example:
        result = call_with_retry(
            httpx.get,
            "https://api.example.com/data",
            max_attempts=5
        )
    """
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.error(f"All {max_attempts} retry attempts exhausted")
                raise

            if isinstance(e, httpx.HTTPError) and should_retry_http_error(e):
                wait_time = exponential_backoff_with_jitter(attempt)
                logger.info(f"Retry {attempt + 1}/{max_attempts} after {wait_time:.1f}s")
                time.sleep(wait_time)
            else:
                # Non-retriable error - fail fast
                raise

    # Should never reach here
    raise RuntimeError("Unexpected retry loop exit")


# Async version for async functions
async def call_with_retry_async(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    **kwargs,
) -> T:
    """
    Async version of call_with_retry.

    Args:
        func: Async function to call
        *args: Positional arguments
        max_attempts: Maximum retry attempts
        **kwargs: Keyword arguments

    Returns:
        Function result

    Example:
        result = await call_with_retry_async(
            client.get,
            "https://api.example.com/data"
        )
    """
    import asyncio

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.error(f"All {max_attempts} retry attempts exhausted")
                raise

            if isinstance(e, httpx.HTTPError) and should_retry_http_error(e):
                wait_time = exponential_backoff_with_jitter(attempt)
                logger.info(f"Async retry {attempt + 1}/{max_attempts} after {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
            else:
                # Non-retriable error - fail fast
                raise

    # Should never reach here
    raise RuntimeError("Unexpected retry loop exit")
