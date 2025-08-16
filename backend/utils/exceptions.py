"""
Custom exception classes for the application.
Provides structured error handling with proper categorization.
"""

from typing import Optional, Dict, Any, List
from enum import Enum


class ErrorCategory(Enum):
    """Categories of errors for proper handling and logging."""
    USER_ERROR = "user_error"           # Client-side errors (400s)
    VALIDATION_ERROR = "validation_error"  # Input validation failures
    AUTHENTICATION_ERROR = "auth_error"    # Authentication/authorization failures
    RESOURCE_ERROR = "resource_error"      # Resource not found, conflicts (404s, 409s)
    EXTERNAL_SERVICE_ERROR = "external_error"  # Third-party service failures
    DATABASE_ERROR = "database_error"     # Database operation failures
    PROCESSING_ERROR = "processing_error"  # Business logic processing failures
    SYSTEM_ERROR = "system_error"         # Internal system errors (500s)
    RATE_LIMIT_ERROR = "rate_limit_error"  # Rate limiting violations
    TIMEOUT_ERROR = "timeout_error"       # Operation timeouts


class BaseApplicationError(Exception):
    """Base class for all application-specific exceptions."""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
        user_facing: bool = True,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.error_code = error_code
        self.details = details or {}
        self.retryable = retryable
        self.user_facing = user_facing
        self.context = context or {}
        self.timestamp = None  # Will be set by error handler

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "retryable": self.retryable,
            "user_facing": self.user_facing,
            "details": self.details,
            "context": self.context
        }

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message} (category: {self.category.value})"


# User-facing errors (400s)
class UserError(BaseApplicationError):
    """Errors caused by invalid user input or requests."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.USER_ERROR,
            error_code=error_code,
            details=details,
            retryable=False,
            user_facing=True
        )


class ValidationError(BaseApplicationError):
    """Input validation failures."""
    
    def __init__(self, message: str, field_errors: Optional[Dict[str, List[str]]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION_ERROR,
            error_code="VALIDATION_FAILED",
            details={"field_errors": field_errors} if field_errors else None,
            retryable=False,
            user_facing=True
        )


class AuthenticationError(BaseApplicationError):
    """Authentication or authorization failures."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION_ERROR,
            error_code="AUTH_REQUIRED",
            retryable=False,
            user_facing=True
        )


# Resource errors (404s, 409s)
class ResourceNotFoundError(BaseApplicationError):
    """Resource not found errors."""
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            category=ErrorCategory.RESOURCE_ERROR,
            error_code="RESOURCE_NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id},
            retryable=False,
            user_facing=True
        )


class ResourceConflictError(BaseApplicationError):
    """Resource conflict errors (e.g., duplicate resources)."""
    
    def __init__(self, message: str, resource_type: str, resource_id: str):
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE_ERROR,
            error_code="RESOURCE_CONFLICT",
            details={"resource_type": resource_type, "resource_id": resource_id},
            retryable=False,
            user_facing=True
        )


# External service errors
class ExternalServiceError(BaseApplicationError):
    """Errors from external services (OpenAI, AWS, etc.)."""
    
    def __init__(
        self,
        service_name: str,
        operation: str,
        original_error: Optional[Exception] = None,
        retryable: bool = True
    ):
        message = f"External service '{service_name}' failed during '{operation}'"
        if original_error:
            message += f": {str(original_error)}"
        
        super().__init__(
            message=message,
            category=ErrorCategory.EXTERNAL_SERVICE_ERROR,
            error_code="EXTERNAL_SERVICE_FAILED",
            details={
                "service_name": service_name,
                "operation": operation,
                "original_error": str(original_error) if original_error else None
            },
            retryable=retryable,
            user_facing=False  # Don't expose internal service details to users
        )


class RateLimitError(BaseApplicationError):
    """Rate limiting violations."""
    
    def __init__(self, service_name: str, retry_after: Optional[int] = None):
        super().__init__(
            message=f"Rate limit exceeded for {service_name}",
            category=ErrorCategory.RATE_LIMIT_ERROR,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"service_name": service_name, "retry_after": retry_after},
            retryable=True,
            user_facing=True
        )


class TimeoutError(BaseApplicationError):
    """Operation timeout errors."""
    
    def __init__(self, operation: str, timeout_seconds: float):
        super().__init__(
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            category=ErrorCategory.TIMEOUT_ERROR,
            error_code="OPERATION_TIMEOUT",
            details={"operation": operation, "timeout_seconds": timeout_seconds},
            retryable=True,
            user_facing=False
        )


# Database errors
class DatabaseError(BaseApplicationError):
    """Database operation failures."""
    
    def __init__(
        self,
        operation: str,
        table: Optional[str] = None,
        original_error: Optional[Exception] = None,
        retryable: bool = True
    ):
        message = f"Database operation '{operation}' failed"
        if table:
            message += f" on table '{table}'"
        if original_error:
            message += f": {str(original_error)}"
        
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE_ERROR,
            error_code="DATABASE_ERROR",
            details={
                "operation": operation,
                "table": table,
                "original_error": str(original_error) if original_error else None
            },
            retryable=retryable,
            user_facing=False
        )


class ConnectionError(BaseApplicationError):
    """Database connection failures."""
    
    def __init__(self, service_name: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to connect to {service_name}",
            category=ErrorCategory.DATABASE_ERROR,
            error_code="CONNECTION_FAILED",
            details={
                "service_name": service_name,
                "original_error": str(original_error) if original_error else None
            },
            retryable=True,
            user_facing=False
        )


# Processing errors
class ProcessingError(BaseApplicationError):
    """Business logic processing failures."""
    
    def __init__(
        self,
        operation: str,
        stage: str,
        message: str,
        retryable: bool = False,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Processing failed during {operation} at {stage}: {message}",
            category=ErrorCategory.PROCESSING_ERROR,
            error_code="PROCESSING_FAILED",
            details={"operation": operation, "stage": stage},
            retryable=retryable,
            user_facing=False,
            context=context
        )


class DocumentProcessingError(ProcessingError):
    """Document processing specific errors."""
    
    def __init__(self, stage: str, filename: str, message: str):
        super().__init__(
            operation="document_processing",
            stage=stage,
            message=message,
            retryable=False,
            context={"filename": filename}
        )


class EmbeddingError(ProcessingError):
    """Embedding generation errors."""
    
    def __init__(self, stage: str, message: str, retryable: bool = True):
        super().__init__(
            operation="embedding_generation",
            stage=stage,
            message=message,
            retryable=retryable
        )


# System errors (500s)
class SystemError(BaseApplicationError):
    """Internal system errors."""
    
    def __init__(self, component: str, operation: str, message: str):
        super().__init__(
            message=f"System error in {component} during {operation}: {message}",
            category=ErrorCategory.SYSTEM_ERROR,
            error_code="SYSTEM_ERROR",
            details={"component": component, "operation": operation},
            retryable=True,
            user_facing=False
        )


class ConfigurationError(SystemError):
    """Configuration-related errors."""
    
    def __init__(self, config_key: str, message: str):
        super().__init__(
            component="configuration",
            operation="initialization",
            message=f"Configuration error for '{config_key}': {message}"
        )


# Convenience functions for common error patterns
def create_external_service_error(service_name: str, operation: str, original_error: Exception) -> ExternalServiceError:
    """Create an external service error with proper categorization."""
    # Determine if error is retryable based on error type
    retryable = isinstance(original_error, (TimeoutError, ConnectionError))
    return ExternalServiceError(service_name, operation, original_error, retryable)


def create_database_error(operation: str, table: str, original_error: Exception) -> DatabaseError:
    """Create a database error with proper categorization."""
    # Determine if error is retryable based on error type
    retryable = isinstance(original_error, (TimeoutError, ConnectionError))
    return DatabaseError(operation, table, original_error, retryable)
