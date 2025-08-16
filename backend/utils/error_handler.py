"""
Error handling middleware and utilities for FastAPI.
Provides centralized error handling with proper categorization and logging.
"""

import time
import traceback
from typing import Dict, Any, Optional, Union
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.exceptions import (
    BaseApplicationError, ErrorCategory, UserError, ValidationError,
    AuthenticationError, ResourceNotFoundError, ResourceConflictError,
    ExternalServiceError, DatabaseError, ProcessingError, SystemError,
    create_external_service_error, create_database_error
)
from utils.logging_config import get_logger, log_error_with_context

logger = get_logger(__name__)


class ErrorHandler:
    """Centralized error handler for the application."""
    
    def __init__(self):
        self.request_id_counter = 0
    
    def get_request_id(self) -> str:
        """Generate a unique request ID."""
        self.request_id_counter += 1
        return f"req_{int(time.time())}_{self.request_id_counter}"
    
    def handle_exception(
        self,
        request: Request,
        exc: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Handle an exception and return appropriate HTTP response.
        
        Args:
            request: FastAPI request object
            exc: The exception that occurred
            context: Additional context for logging
            
        Returns:
            JSONResponse with appropriate status code and error details
        """
        request_id = self.get_request_id()
        start_time = getattr(request.state, 'start_time', time.time())
        duration = time.time() - start_time
        
        # Log the error with context
        log_error_with_context(
            logger.bind(request_id=request_id),
            exc,
            context={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "duration": duration,
                **(context or {})
            }
        )
        
        # Convert exception to appropriate HTTP response
        if isinstance(exc, BaseApplicationError):
            return self._handle_application_error(exc, request_id)
        elif isinstance(exc, RequestValidationError):
            return self._handle_validation_error(exc, request_id)
        elif isinstance(exc, HTTPException):
            return self._handle_http_exception(exc, request_id)
        elif isinstance(exc, StarletteHTTPException):
            return self._handle_http_exception(exc, request_id)
        else:
            return self._handle_unexpected_error(exc, request_id)
    
    def _handle_application_error(self, exc: BaseApplicationError, request_id: str) -> JSONResponse:
        """Handle application-specific errors."""
        status_code = self._get_status_code_for_category(exc.category)
        
        response_data = {
            "error": {
                "code": exc.error_code or "APPLICATION_ERROR",
                "message": exc.message if exc.user_facing else "An internal error occurred",
                "request_id": request_id,
                "category": exc.category.value
            }
        }
        
        # Include details for user-facing errors
        if exc.user_facing and exc.details:
            response_data["error"]["details"] = exc.details
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )
    
    def _handle_validation_error(self, exc: RequestValidationError, request_id: str) -> JSONResponse:
        """Handle request validation errors."""
        field_errors = {}
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            field_errors[field] = error["msg"]
        
        response_data = {
            "error": {
                "code": "VALIDATION_FAILED",
                "message": "Request validation failed",
                "request_id": request_id,
                "category": ErrorCategory.VALIDATION_ERROR.value,
                "details": {
                    "field_errors": field_errors
                }
            }
        }
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response_data
        )
    
    def _handle_http_exception(self, exc: Union[HTTPException, StarletteHTTPException], request_id: str) -> JSONResponse:
        """Handle HTTP exceptions."""
        response_data = {
            "error": {
                "code": "HTTP_ERROR",
                "message": exc.detail,
                "request_id": request_id,
                "category": self._get_category_for_status_code(exc.status_code).value
            }
        }
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response_data
        )
    
    def _handle_unexpected_error(self, exc: Exception, request_id: str) -> JSONResponse:
        """Handle unexpected errors (system errors)."""
        logger.exception(f"Unexpected error occurred: {type(exc).__name__}: {str(exc)}")
        
        response_data = {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
                "category": ErrorCategory.SYSTEM_ERROR.value
            }
        }
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_data
        )
    
    def _get_status_code_for_category(self, category: ErrorCategory) -> int:
        """Get appropriate HTTP status code for error category."""
        status_map = {
            ErrorCategory.USER_ERROR: status.HTTP_400_BAD_REQUEST,
            ErrorCategory.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorCategory.AUTHENTICATION_ERROR: status.HTTP_401_UNAUTHORIZED,
            ErrorCategory.RESOURCE_ERROR: status.HTTP_404_NOT_FOUND,
            ErrorCategory.EXTERNAL_SERVICE_ERROR: status.HTTP_502_BAD_GATEWAY,
            ErrorCategory.DATABASE_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorCategory.PROCESSING_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorCategory.SYSTEM_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
            ErrorCategory.RATE_LIMIT_ERROR: status.HTTP_429_TOO_MANY_REQUESTS,
            ErrorCategory.TIMEOUT_ERROR: status.HTTP_504_GATEWAY_TIMEOUT,
        }
        return status_map.get(category, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_category_for_status_code(self, status_code: int) -> ErrorCategory:
        """Get error category for HTTP status code."""
        if status_code == 400:
            return ErrorCategory.USER_ERROR
        elif status_code == 401:
            return ErrorCategory.AUTHENTICATION_ERROR
        elif status_code == 404:
            return ErrorCategory.RESOURCE_ERROR
        elif status_code == 422:
            return ErrorCategory.VALIDATION_ERROR
        elif status_code == 429:
            return ErrorCategory.RATE_LIMIT_ERROR
        elif status_code == 500:
            return ErrorCategory.SYSTEM_ERROR
        elif status_code == 502:
            return ErrorCategory.EXTERNAL_SERVICE_ERROR
        elif status_code == 503:
            return ErrorCategory.DATABASE_ERROR
        elif status_code == 504:
            return ErrorCategory.TIMEOUT_ERROR
        else:
            return ErrorCategory.SYSTEM_ERROR


# Global error handler instance
error_handler = ErrorHandler()


async def error_handler_middleware(request: Request, call_next):
    """
    FastAPI middleware for centralized error handling.
    
    This middleware:
    1. Records request start time
    2. Handles exceptions and converts them to appropriate HTTP responses
    3. Logs request completion with timing
    """
    # Record start time
    request.state.start_time = time.time()
    
    try:
        # Process the request
        response = await call_next(request)
        
        # Log successful request
        duration = time.time() - request.state.start_time
        logger.info(
            f"Request completed: {request.method} {request.url.path}",
            extra_fields={
                "event_type": "request_completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2)
            }
        )
        
        return response
        
    except Exception as exc:
        # Handle the exception
        return error_handler.handle_exception(request, exc)


def setup_error_handlers(app):
    """
    Setup error handlers for FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    # Add middleware for request timing and error handling
    app.middleware("http")(error_handler_middleware)
    
    # Register exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return error_handler.handle_exception(request, exc)
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return error_handler.handle_exception(request, exc)
    
    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        return error_handler.handle_exception(request, exc)
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return error_handler.handle_exception(request, exc)


# Utility functions for common error scenarios
def raise_user_error(message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
    """Raise a user error with proper categorization."""
    raise UserError(message, error_code, details)


def raise_validation_error(message: str, field_errors: Optional[Dict[str, str]] = None):
    """Raise a validation error with field-specific errors."""
    raise ValidationError(message, field_errors)


def raise_resource_not_found(resource_type: str, resource_id: str):
    """Raise a resource not found error."""
    raise ResourceNotFoundError(resource_type, resource_id)


def raise_external_service_error(service_name: str, operation: str, original_error: Exception):
    """Raise an external service error."""
    raise create_external_service_error(service_name, operation, original_error)


def raise_database_error(operation: str, table: str, original_error: Exception):
    """Raise a database error."""
    raise create_database_error(operation, table, original_error)


def raise_processing_error(operation: str, stage: str, message: str, context: Optional[Dict[str, Any]] = None):
    """Raise a processing error."""
    raise ProcessingError(operation, stage, message, context=context)


def raise_system_error(component: str, operation: str, message: str):
    """Raise a system error."""
    raise SystemError(component, operation, message)
