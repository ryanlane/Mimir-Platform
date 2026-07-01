# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Logging configuration for Mimir API
Provides structured logging with optional colored output for development.
"""
from __future__ import annotations

import json
import logging
import logging.config
import threading
import time
from collections import deque
from typing import Any

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
        data: dict[str, Any] = {
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


class LogBuffer:
    """Thread-safe in-memory ring buffer of recent log records.

    Lets /api/admin/logs answer "what's actually going on" over HTTP —
    without this, diagnosing a running server means shelling in for
    `docker logs`, which isn't an option for remote/cloud agents or anyone
    without host access.
    """

    def __init__(self, maxlen: int = 5000) -> None:
        self._buf: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self.maxlen = maxlen

    def append(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._buf.append(entry)

    def query(
        self,
        limit: int = 200,
        level: str | None = None,
        logger_contains: str | None = None,
        text_contains: str | None = None,
        since_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        min_level = logging.getLevelName(level.upper()) if level else 0
        logger_contains = logger_contains.lower() if logger_contains else None
        text_contains = text_contains.lower() if text_contains else None

        with self._lock:
            snapshot = list(self._buf)

        results = []
        for entry in snapshot:
            if isinstance(min_level, int) and entry.get("levelno", 0) < min_level:
                continue
            if logger_contains and logger_contains not in entry.get("logger", "").lower():
                continue
            if text_contains and text_contains not in entry.get("msg", "").lower():
                continue
            if since_ts is not None and entry.get("created", 0) < since_ts:
                continue
            results.append(entry)

        if limit:
            results = results[-limit:]
        return results

    def __len__(self) -> int:
        return len(self._buf)


log_buffer = LogBuffer()


_exc_formatter = logging.Formatter()


class LogBufferHandler(logging.Handler):
    """Feeds every emitted log record into the shared in-memory ring buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        entry: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(record.created)),
            "created": record.created,
            "level": record.levelname,
            "levelno": record.levelno,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            entry["request_id"] = record.request_id
        for k, v in record.__dict__.items():
            if k not in _STANDARD_ATTRS and k not in ("message", "asctime"):
                try:
                    json.dumps(v, default=str)
                except (TypeError, ValueError):
                    v = str(v)
                entry[k] = v
        if record.exc_info:
            entry["exc_info"] = _exc_formatter.formatException(record.exc_info)
        log_buffer.append(entry)


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""

    COLORS = {
        "DEBUG": "\033[96m",  # Cyan
        "INFO": "\033[92m",   # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m\033[1m",  # Magenta and Bold
    }

    def format(self, record: logging.LogRecord) -> str:
        # Get the original formatted message
        message = super().format(record)

        # Add color if available and we're in debug mode
        if settings.debug:
            color = self.COLORS.get(record.levelname, "")
            if color:
                # Color the entire message
                message = f"{color}{message}\033[0m"  # Reset color at the end

        return message


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

    config: dict[str, Any] = {
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
            "buffer": {
                "()": "app.core.logging.LogBufferHandler",
                "level": "DEBUG",
                "filters": ["request_id"],
            },
        },
        "root": {
            "level": level,
            "handlers": ["default", "buffer"],
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

    # Named loggers above all set propagate=False, so they never reach root's
    # handlers — attach "buffer" to each directly so the ring buffer sees
    # everything, not just what happens to bubble up to root.
    for logger_cfg in config["loggers"].values():
        if "buffer" not in logger_cfg["handlers"]:
            logger_cfg["handlers"].append("buffer")

    logging.config.dictConfig(config)

    # In debug mode, swap in a colored formatter on the handler dictConfig
    # already created (named "default") instead of adding a second handler,
    # which would double every log line.
    if settings.debug:
        console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        console_formatter = ColoredFormatter(console_format)
        for handler in logging.getLogger().handlers:
            handler.setFormatter(console_formatter)


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


def log_websocket_event(event_type: str, client_id: str, data: dict[str, Any] | None = None) -> None:
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


def log_channel_event(action: str, channel_id: str, details: dict[str, Any] | None = None) -> None:
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
