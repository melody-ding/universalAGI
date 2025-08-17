"""
Retry mechanism utilities for handling transient failures.
Provides configurable retry logic with exponential backoff and circuit breaker patterns.
"""

import asyncio
import time
import random
from typing import Callable, Any, Optional, Type, Union, List
from functools import wraps
from utils.exceptions import BaseApplicationError, ErrorCategory
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[Type[Exception]]] = None,
        retryable_error_categories: Optional[List[ErrorCategory]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [
            TimeoutError,
            ConnectionError,
            OSError,
        ]
        self.retryable_error_categories = retryable_error_categories or [
            ErrorCategory.EXTERNAL_SERVICE_ERROR,
            ErrorCategory.DATABASE_ERROR,
            ErrorCategory.TIMEOUT_ERROR,
            ErrorCategory.RATE_LIMIT_ERROR,
        ]


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful execution."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for the given attempt using exponential backoff."""
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        # Add jitter to prevent thundering herd
        delay = delay * (0.5 + random.random() * 0.5)
    
    return delay


def is_retryable_error(error: Exception, config: RetryConfig) -> bool:
    """Determine if an error is retryable based on configuration."""
    # Check if it's a custom application error
    if isinstance(error, BaseApplicationError):
        return error.retryable and error.category in config.retryable_error_categories
    
    # Check if it's a retryable exception type
    return any(isinstance(error, exc_type) for exc_type in config.retryable_exceptions)


def retry(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None
):
    """
    Decorator for adding retry logic to functions.
    
    Args:
        config: Retry configuration
        operation_name: Name of the operation for logging
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            operation = operation_name or func.__name__
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if not is_retryable_error(e, config):
                        logger.warning(f"Non-retryable error in {operation}: {e}")
                        raise
                    
                    if attempt == config.max_attempts:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {operation}",
                            extra_fields={
                                "operation": operation,
                                "attempts": config.max_attempts,
                                "final_error": str(e)
                            }
                        )
                        raise
                    
                    delay = calculate_delay(attempt, config)
                    logger.warning(
                        f"Attempt {attempt} failed for {operation}, retrying in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            operation = operation_name or func.__name__
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if not is_retryable_error(e, config):
                        logger.warning(f"Non-retryable error in {operation}: {e}")
                        raise
                    
                    if attempt == config.max_attempts:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for {operation}",
                            extra_fields={
                                "operation": operation,
                                "attempts": config.max_attempts,
                                "final_error": str(e)
                            }
                        )
                        raise
                    
                    delay = calculate_delay(attempt, config)
                    logger.warning(
                        f"Attempt {attempt} failed for {operation}, retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RetryableOperation:
    """Context manager for retryable operations."""
    
    def __init__(self, config: Optional[RetryConfig] = None, operation_name: Optional[str] = None):
        self.config = config or RetryConfig()
        self.operation_name = operation_name or "operation"
        self.attempt = 0
        self.last_exception = None
    
    def __enter__(self):
        self.attempt += 1
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is None:
            # Success
            return False
        
        if not is_retryable_error(exc_val, self.config):
            # Non-retryable error
            return False
        
        if self.attempt >= self.config.max_attempts:
            # Max attempts reached
            logger.error(
                f"All {self.config.max_attempts} attempts failed for {self.operation_name}",
                extra_fields={
                    "operation": self.operation_name,
                    "attempts": self.config.max_attempts,
                    "final_error": str(exc_val)
                }
            )
            return False
        
        # Retry
        delay = calculate_delay(self.attempt, self.config)
        logger.warning(
            f"Attempt {self.attempt} failed for {self.operation_name}, retrying in {delay:.2f}s: {exc_val}"
        )
        time.sleep(delay)
        return True  # Suppress the exception for retry
    
    async def __aenter__(self):
        self.attempt += 1
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val is None:
            # Success
            return False
        
        if not is_retryable_error(exc_val, self.config):
            # Non-retryable error
            return False
        
        if self.attempt >= self.config.max_attempts:
            # Max attempts reached
            logger.error(
                f"All {self.config.max_attempts} attempts failed for {self.operation_name}",
                extra_fields={
                    "operation": self.operation_name,
                    "attempts": self.config.max_attempts,
                    "final_error": str(exc_val)
                }
            )
            return False
        
        # Retry
        delay = calculate_delay(self.attempt, self.config)
        logger.warning(
            f"Attempt {self.attempt} failed for {self.operation_name}, retrying in {delay:.2f}s: {exc_val}"
        )
        await asyncio.sleep(delay)
        return True  # Suppress the exception for retry


# Predefined retry configurations for common scenarios
DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    retryable_error_categories=[ErrorCategory.DATABASE_ERROR]
)

EXTERNAL_SERVICE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    retryable_error_categories=[
        ErrorCategory.EXTERNAL_SERVICE_ERROR,
        ErrorCategory.TIMEOUT_ERROR,
        ErrorCategory.RATE_LIMIT_ERROR
    ]
)

EMBEDDING_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=10.0,
    retryable_error_categories=[ErrorCategory.EXTERNAL_SERVICE_ERROR, ErrorCategory.TIMEOUT_ERROR]
)


# Convenience functions
def retry_database_operation(operation_name: Optional[str] = None):
    """Decorator for database operations with appropriate retry logic."""
    return retry(DATABASE_RETRY_CONFIG, operation_name)


def retry_external_service(operation_name: Optional[str] = None):
    """Decorator for external service calls with appropriate retry logic."""
    return retry(EXTERNAL_SERVICE_RETRY_CONFIG, operation_name)


def retry_embedding_operation(operation_name: Optional[str] = None):
    """Decorator for embedding operations with appropriate retry logic."""
    return retry(EMBEDDING_RETRY_CONFIG, operation_name)
