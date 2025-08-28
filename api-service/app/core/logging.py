"""
Logging configuration for Mimir API
Provides structured logging with JSON output and request tracking
"""
from __future__ import annotations

import json
import logging
import logging.config
import sys
import time
from typing import Any, Dict

from app.config import settings


# --- Helpers ---------------------------------------------------------------

# Build a set of standard LogRecord attributes to detect "extra" fields.
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class RequestIDFilter(logging.Filter):
    """Add request ID to log records for request tracing (if available)."""

    def filter(self, record: logging.LogRecord) -> bool:
        # If some middleware later sets record.request_id, we keep it.
        # Otherwise, provide a consistent placeholder.
        if not hasattr(record, "request_id"):
            record.request_id = "N/A"
        return True


class JSONFormatter(logging.Formatter):
    """Minimal JSON formatter that includes extra fields automatically."""

    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Common extras we care about
        if hasattr(record, "request_id"):
            data["request_id"] = record.request_id

        # Merge any other extras that were added via Logger(..., extra={...})
        for k, v in record.__dict__.items():
            if k not in _STANDARD_ATTRS and k not in ("message", "asctime"):
                data[k] = v

        return json.dumps(data, default=str)


# --- Public API ------------------------------------------------------------

def setup_logging() -> None:
    """Configure application logging based on settings."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    json_mode = settings.log_format.lower() == "json"

    # Route warnings.warn(...) into logging
    logging.captureWarnings(True)

    formatter_name = "json" if json_mode else "plain"
    formatters = {
        "json": {"()": "app.core.logging.JSONFormatter"},
        "plain": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }

    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "filters": {
            "request_id": {
                "()": "app.core.logging.RequestIDFilter",
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": formatter_name,
                "filters": ["request_id"],
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": level,
            "handlers": ["default"],
        },
        "loggers": {
            # Keep uvicorn logs for endpoint access monitoring
            "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": False},
            "uvicorn.access": {"level": "INFO", "handlers": ["default"], "propagate": False},
            # Reduce SQLAlchemy verbosity - only show errors
            "sqlalchemy.engine": {"level": "ERROR", "handlers": ["default"], "propagate": False},
            "sqlalchemy": {"level": "ERROR", "handlers": ["default"], "propagate": False},
            "sqlalchemy.engine.Engine": {"level": "ERROR", "handlers": ["default"], "propagate": False},
            "sqlalchemy.pool": {"level": "ERROR", "handlers": ["default"], "propagate": False},
            "sqlalchemy.dialects": {"level": "ERROR", "handlers": ["default"], "propagate": False},
            # Reduce other noisy loggers
            "alembic": {"level": "WARNING", "handlers": ["default"], "propagate": False},
            "asyncio": {"level": "WARNING", "handlers": ["default"], "propagate": False},
            # App namespace
            "app": {"level": level, "handlers": ["default"], "propagate": False},
        },
    }

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name."""
    return logging.getLogger(name)


# Application logger
logger = get_logger("app")


def log_api_request(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Log API request with structured data."""
    logger.info(
        "API Request",
        extra={
            "event_type": "api_request",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        },
    )


def log_websocket_event(event_type: str, client_id: str, data: Dict[str, Any] | None = None) -> None:
    """Log WebSocket events with structured data."""
    logger.info(
        f"WebSocket {event_type}",
        extra={
            "event_type": "websocket",
            "websocket_event": event_type,
            "client_id": client_id,
            "data": data or {},
        },
    )


def log_channel_event(action: str, channel_id: str, details: Dict[str, Any] | None = None) -> None:
    """Log channel-related events."""
    logger.info(
        f"Channel {action}",
        extra={
            "event_type": "channel",
            "action": action,
            "channel_id": channel_id,
            "details": details or {},
        },
    )
