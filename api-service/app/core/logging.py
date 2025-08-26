"""
Logging configuration for Mimir API
Provides structured logging with JSON output and request tracking
"""
import logging
import logging.config
import sys
from typing import Dict, Any
from app.config import settings


def setup_logging() -> None:
    """Configure application logging based on settings"""
    
    # Define log format based on configuration
    if settings.log_format.lower() == "json":
        formatter_config = {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}',
            "datefmt": "%Y-%m-%dT%H:%M:%S"
        }
    else:
        formatter_config = {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    
    # Logging configuration
    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": formatter_config,
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": settings.log_level.upper(),
            "handlers": ["default"],
        },
        "loggers": {
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["default"],  
                "propagate": False,
            },
            "app": {
                "level": settings.log_level.upper(),
                "handlers": ["default"],
                "propagate": False,
            },
        },
    }
    
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name"""
    return logging.getLogger(name)


# Application logger
logger = get_logger("app")


class RequestIDFilter(logging.Filter):
    """Add request ID to log records for request tracing"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # TODO: Extract request ID from context when available
        record.request_id = getattr(record, 'request_id', 'N/A')
        return True


def log_api_request(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Log API request with structured data"""
    logger.info(
        "API Request",
        extra={
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "event_type": "api_request"
        }
    )


def log_websocket_event(event_type: str, client_id: str, data: Dict[str, Any] = None) -> None:
    """Log WebSocket events with structured data"""
    logger.info(
        f"WebSocket {event_type}",
        extra={
            "client_id": client_id,
            "event_type": "websocket",
            "websocket_event": event_type,
            "data": data or {}
        }
    )


def log_channel_event(action: str, channel_id: str, details: Dict[str, Any] = None) -> None:
    """Log channel-related events"""
    logger.info(
        f"Channel {action}",
        extra={
            "channel_id": channel_id,
            "event_type": "channel",
            "action": action,
            "details": details or {}
        }
    )
