"""
Structured logging configuration for the application.
Provides consistent logging across all components with proper formatting and levels.
"""

import logging
import logging.config
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Extract structured data from record
        structured_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            structured_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            structured_data.update(record.extra_fields)
        
        # Add context if present
        if hasattr(record, 'context'):
            structured_data["context"] = record.context
        
        # Add error details if present
        if hasattr(record, 'error_details'):
            structured_data["error_details"] = record.error_details
        
        return json.dumps(structured_data, default=str)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development and debugging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human reading."""
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname.ljust(8)
        logger_name = record.name.ljust(20)
        message = record.getMessage()
        
        formatted = f"{timestamp} | {level} | {logger_name} | {message}"
        
        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            formatted += f"\nExtra: {record.extra_fields}"
        
        return formatted


class ContextLogger:
    """Logger wrapper that supports structured context and error details."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.context: Dict[str, Any] = {}
    
    def bind(self, **kwargs) -> 'ContextLogger':
        """Bind context data to this logger instance."""
        new_logger = ContextLogger(self.logger)
        new_logger.context = {**self.context, **kwargs}
        return new_logger
    
    def _log_with_context(self, level: int, message: str, extra_fields: Optional[Dict[str, Any]] = None, **kwargs):
        """Log with context and extra fields."""
        record = self.logger.makeRecord(
            self.logger.name, level, "", 0, message, (), None
        )
        
        if self.context:
            record.context = self.context
        
        if extra_fields:
            record.extra_fields = extra_fields
        
        # Add any additional kwargs as extra fields
        if kwargs:
            if not hasattr(record, 'extra_fields'):
                record.extra_fields = {}
            record.extra_fields.update(kwargs)
        
        self.logger.handle(record)
    
    def debug(self, message: str, extra_fields: Optional[Dict[str, Any]] = None, **kwargs):
        self._log_with_context(logging.DEBUG, message, extra_fields, **kwargs)
    
    def info(self, message: str, extra_fields: Optional[Dict[str, Any]] = None, **kwargs):
        self._log_with_context(logging.INFO, message, extra_fields, **kwargs)
    
    def warning(self, message: str, extra_fields: Optional[Dict[str, Any]] = None, **kwargs):
        self._log_with_context(logging.WARNING, message, extra_fields, **kwargs)
    
    def error(self, message: str, extra_fields: Optional[Dict[str, Any]] = None, **kwargs):
        self._log_with_context(logging.ERROR, message, extra_fields, **kwargs)
    
    def critical(self, message: str, extra_fields: Optional[Dict[str, Any]] = None, **kwargs):
        self._log_with_context(logging.CRITICAL, message, extra_fields, **kwargs)
    
    def exception(self, message: str, extra_fields: Optional[Dict[str, Any]] = None, **kwargs):
        """Log exception with traceback."""
        record = self.logger.makeRecord(
            self.logger.name, logging.ERROR, "", 0, message, (), sys.exc_info()
        )
        
        if self.context:
            record.context = self.context
        
        if extra_fields:
            record.extra_fields = extra_fields
        
        if kwargs:
            if not hasattr(record, 'extra_fields'):
                record.extra_fields = {}
            record.extra_fields.update(kwargs)
        
        self.logger.handle(record)


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",  # "json" or "human"
    log_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """
    Setup application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format ("json" for structured, "human" for readable)
        log_file: Optional file path for logging
        enable_console: Whether to enable console logging
    """
    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Choose formatter based on format preference
    if log_format == "json":
        formatter = StructuredFormatter()
    else:
        formatter = HumanReadableFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    loggers_config = {
        # External libraries - reduce noise
        "urllib3": {"level": "WARNING"},
        "boto3": {"level": "WARNING"},
        "botocore": {"level": "WARNING"},
        "openai": {"level": "INFO"},
        "langchain": {"level": "INFO"},
        
        # Application loggers
        "backend": {"level": log_level.upper()},
        "backend.agent": {"level": log_level.upper()},
        "backend.services": {"level": log_level.upper()},
        "backend.database": {"level": log_level.upper()},
        "backend.search": {"level": log_level.upper()},
    }
    
    for logger_name, config in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, config["level"]))
        logger.propagate = True  # Propagate to root logger


def get_logger(name: str) -> ContextLogger:
    """
    Get a context-aware logger for the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        ContextLogger instance
    """
    return ContextLogger(logging.getLogger(name))


# Convenience functions for common logging patterns
def log_request(logger: ContextLogger, method: str, path: str, status_code: int, duration: float, **kwargs):
    """Log HTTP request details."""
    logger.info(
        f"HTTP {method} {path} - {status_code}",
        extra_fields={
            "event_type": "http_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration * 1000, 2)
        },
        **kwargs
    )


def log_database_operation(logger: ContextLogger, operation: str, table: str, duration: float, success: bool, **kwargs):
    """Log database operation details."""
    logger.info(
        f"Database {operation} on {table} - {'SUCCESS' if success else 'FAILED'}",
        extra_fields={
            "event_type": "database_operation",
            "operation": operation,
            "table": table,
            "duration_ms": round(duration * 1000, 2),
            "success": success
        },
        **kwargs
    )


def log_external_service_call(logger: ContextLogger, service: str, operation: str, duration: float, success: bool, **kwargs):
    """Log external service call details."""
    logger.info(
        f"External service {service} {operation} - {'SUCCESS' if success else 'FAILED'}",
        extra_fields={
            "event_type": "external_service_call",
            "service": service,
            "operation": operation,
            "duration_ms": round(duration * 1000, 2),
            "success": success
        },
        **kwargs
    )


def log_error_with_context(logger: ContextLogger, error: Exception, context: Dict[str, Any] = None, **kwargs):
    """Log error with structured context."""
    error_details = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "retryable": getattr(error, 'retryable', None),
        "category": getattr(error, 'category', None),
    }
    
    logger.error(
        f"Error occurred: {type(error).__name__}: {str(error)}",
        extra_fields={"event_type": "error"},
        error_details=error_details,
        context=context,
        **kwargs
    )


# Initialize logging on module import
def initialize_logging():
    """Initialize logging with default configuration."""
    try:
        from config import settings
        setup_logging(
            log_level=settings.logging.level.value,
            log_format=settings.logging.format.value,
            log_file=settings.logging.file_path,
            enable_console=settings.logging.enable_console
        )
    except ImportError:
        # Fallback to environment variables if config is not available
        import os
        log_level = os.getenv("LOG_LEVEL", "INFO")
        log_format = os.getenv("LOG_FORMAT", "json")
        log_file = os.getenv("LOG_FILE")
        enable_console = os.getenv("LOG_CONSOLE", "true").lower() == "true"
        
        setup_logging(
            log_level=log_level,
            log_format=log_format,
            log_file=log_file,
            enable_console=enable_console
        )


# Auto-initialize when module is imported
initialize_logging()
