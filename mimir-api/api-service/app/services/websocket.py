"""Backward compatibility shim for legacy imports.

The original `WebSocketService` has been superseded by the unified
`WebSocketManager` (see `websocket_manager.py`). This module re-exports
the new singleton so existing imports keep working while code migrates.

Deprecation: Remove this shim after downstream code switches to
`from app.services.websocket_manager import websocket_manager`.
"""
from __future__ import annotations

from app.services.websocket_manager import (
    WebSocketManager as WebSocketService,  # type: ignore
    websocket_manager as websocket_service,
)

__all__ = ["WebSocketService", "websocket_service"]
