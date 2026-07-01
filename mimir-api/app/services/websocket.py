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

"""Backward compatibility shim for legacy imports.

The original `WebSocketService` has been superseded by the unified
`WebSocketManager` (see `websocket_manager.py`). This module re-exports
the new singleton so existing imports keep working while code migrates.

Deprecation: Remove this shim after downstream code switches to
`from app.services.websocket_manager import websocket_manager`.
"""
from __future__ import annotations

from app.services.websocket_manager import (
    WebSocketManager as WebSocketService,
)
from app.services.websocket_manager import (
    websocket_manager as websocket_service,
)

__all__ = ["WebSocketService", "websocket_service"]
