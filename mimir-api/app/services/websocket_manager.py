"""Unified WebSocket Manager.

Combines legacy `ConnectionManager` and the richer `WebSocketService` into a
single implementation that:

* Tracks dashboard (general) and display connections with metadata
* Provides sequence IDs for ordered events
* (Optionally) emits metrics if `app.core.metrics.metrics` is available
* Updates display online/offline status in the database
* Offers targeted broadcast helpers & generic event emission
* Maintains backward compatibility with previous method names

NOTE: This file replaces the older `services/websocket.py` implementation. A
compatibility shim will re-export the global instance so existing imports
continue to function until fully migrated.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Iterable
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger
from app.db.base import SessionLocal
from app.db.models import Channel, Scene, DisplayClient

try:  # optional metrics
    from app.core.metrics import metrics
    METRICS_AVAILABLE = True
except Exception:  # pragma: no cover - metrics optional
    METRICS_AVAILABLE = False

logger = get_logger(__name__)


class WebSocketManager:
    """Unified WebSocket manager for dashboards & display clients."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []               # all websockets (dashboards + displays)
        self.display_connections: dict[str, WebSocket] = {}         # display_id -> websocket
        self.connection_metadata: dict[WebSocket, dict[str, Any]] = {}
        self.sequence_id: int = 0

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------
    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "type": "dashboard",
            "connected_at": datetime.datetime.now(),
        }
        if METRICS_AVAILABLE:
            metrics.websocket_connection_opened(f"dashboard_{id(websocket)}")
        logger.info("WebSocket connected: dashboard (total=%s)", len(self.active_connections))

    # Backwards compatibility alias (legacy code expected `connect` for general clients)
    async def connect(self, websocket: WebSocket):  # noqa: D401 - documented above
        await self.connect_dashboard(websocket)

    async def connect_display(self, websocket: WebSocket, display_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.display_connections[display_id] = websocket
        self.connection_metadata[websocket] = {
            "type": "display",
            "display_id": display_id,
            "connected_at": datetime.datetime.now(),
        }
        if METRICS_AVAILABLE:
            metrics.websocket_connection_opened(display_id)
        await self._update_display_status(display_id, True)
        logger.info("Display client connected: %s (total=%s)", display_id, len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket not in self.active_connections:
            return
        self.active_connections.remove(websocket)
        meta = self.connection_metadata.get(websocket, {})
        disp_id = meta.get("display_id") if meta.get("type") == "display" else None
        if disp_id and self.display_connections.get(disp_id) is websocket:
            self.display_connections.pop(disp_id, None)
            # schedule DB update async
            import asyncio
            asyncio.create_task(self._update_display_status(disp_id, False))
            if METRICS_AVAILABLE:
                metrics.websocket_connection_closed(disp_id)
        else:
            if METRICS_AVAILABLE:
                metrics.websocket_connection_closed(f"dashboard_{id(websocket)}")
        self.connection_metadata.pop(websocket, None)
        logger.info("WebSocket disconnected (total=%s)", len(self.active_connections))

    # ------------------------------------------------------------------
    # DB side-effects
    # ------------------------------------------------------------------
    async def _update_display_status(self, display_id: str, is_online: bool):
        db = SessionLocal()
        try:
            client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
            if client:
                client.is_online = is_online
                client.last_seen = datetime.datetime.now()
                client.websocket_connection_id = display_id if is_online else None
                db.commit()
                logger.debug("Updated display status: %s online=%s", display_id, is_online)
        except Exception as e:  # pragma: no cover - defensive logging
            logger.error("Error updating display status %s: %s", display_id, e)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Sequence IDs
    # ------------------------------------------------------------------
    def next_sequence_id(self) -> int:
        self.sequence_id += 1
        return self.sequence_id

    # Legacy accessors
    def get_current_sequence_id(self) -> int:  # compatibility
        return self.sequence_id
    def increment_sequence_id(self) -> int:  # compatibility
        return self.next_sequence_id()

    # ------------------------------------------------------------------
    # Low-level send helpers
    # ------------------------------------------------------------------
    async def send_personal_message(self, message: str, websocket: WebSocket) -> bool:
        try:
            await websocket.send_text(message)
            return True
        except Exception as e:
            logger.warning("Failed personal send: %s", e)
            self.disconnect(websocket)
            return False

    async def send_to_display(self, message: str, display_id: str) -> bool:
        ws = self.display_connections.get(display_id)
        if not ws:
            logger.debug("Display %s not connected", display_id)
            return False
        return await self.send_personal_message(message, ws)

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------
    async def _broadcast_raw(self, targets: Iterable[WebSocket], message: str):
        to_drop: list[WebSocket] = []
        for ws in list(targets):
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.warning("Broadcast failure: %s", e)
                to_drop.append(ws)
        for ws in to_drop:
            self.disconnect(ws)

    async def broadcast_all(self, payload: dict):
        msg = json.dumps(payload)
        await self._broadcast_raw(self.active_connections, msg)
        if METRICS_AVAILABLE:
            metrics.websocket_message_sent(payload.get("event") or payload.get("type", "unknown"), len(self.active_connections))

    async def broadcast_dashboards(self, payload: dict):
        msg = json.dumps(payload)
        dashboards = [ws for ws, meta in self.connection_metadata.items() if meta.get("type") == "dashboard"]
        await self._broadcast_raw(dashboards, msg)

    async def broadcast_displays(self, payload: dict, display_ids: list[str] | None = None):
        msg = json.dumps(payload)
        if display_ids:
            sockets = [self.display_connections[d] for d in display_ids if d in self.display_connections]
        else:
            sockets = list(self.display_connections.values())
        await self._broadcast_raw(sockets, msg)

    # Backwards compatibility names
    async def broadcast(self, message: str):  # legacy raw string broadcast
        await self._broadcast_raw(self.active_connections, message)

    async def broadcast_to_displays(self, message: str, display_ids: list[str] | None = None):  # legacy signature
        if display_ids is None:
            display_ids = list(self.display_connections.keys())
        for did in display_ids:
            await self.send_to_display(message, did)

    # ------------------------------------------------------------------
    # Generic event emitter
    # ------------------------------------------------------------------
    async def emit_event(
        self,
        event: str,
        data: dict,
        *,
        audience: str = "all",
        display_ids: list[str] | None = None,
        include_sequence: bool = False,
        targets: list[WebSocket] | None = None,
    ):
        payload: dict[str, Any] = {
            "event": event,
            "data": data,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if include_sequence:
            payload["sequence_id"] = self.next_sequence_id()
        # Direct targeted send (explicit list of websockets) takes precedence
        if targets:
            msg = json.dumps(payload)
            await self._broadcast_raw(targets, msg)
            return

        if audience == "dashboards":
            await self.broadcast_dashboards(payload)
        elif audience == "displays":
            await self.broadcast_displays(payload, display_ids)
        else:
            await self.broadcast_all(payload)

    # ------------------------------------------------------------------
    # Domain specific helpers (new unified forms)
    # ------------------------------------------------------------------
    async def send_full_state(self, websocket: WebSocket):  # retains previous shape
        db = SessionLocal()
        try:
            channels = db.query(Channel).all()
            scenes = db.query(Scene).all()
            displays = db.query(DisplayClient).all()
            state = {
                "event": "full_state",
                "data": {
                    "channels": [{"id": c.id, "name": c.name, "version": c.version, "description": c.description} for c in channels],
                    "scenes": [{"id": s.id, "name": s.name, "channels": s.channels, "is_active": s.is_active} for s in scenes],
                    "displays": [{"id": d.id, "name": d.name, "location": d.location, "is_online": d.is_online, "assigned_scene_id": d.assigned_scene_id} for d in displays],
                    "connection_count": len(self.active_connections) + len(self.display_connections),
                },
                "timestamp": datetime.datetime.now().isoformat(),
            }
            await self.send_personal_message(json.dumps(state), websocket)
        except Exception as e:
            logger.error("Failed sending full state: %s", e)
        finally:
            db.close()

    # Compatibility wrappers (legacy notify_* API)
    async def notify_scene_change(self, scene_id: str, display_ids: list[str] | None = None):
        await self.emit_event("scene_changed", {"scene_id": scene_id, "display_ids": display_ids}, audience="all")

    async def notify_display_status_change(self, display_id: str, status: dict):
        await self.emit_event("display_status_changed", {"display_id": display_id, "status": status}, audience="all")

    async def notify_channel_update(self, channel_id: str, update_type: str = "updated"):
        await self.emit_event("channel_updated", {"channel_id": channel_id, "update_type": update_type}, audience="all")

    # Structured content distribution helpers (preserve prior shapes with `type` key)
    async def broadcast_scene_activation(self, scene_id: str, scene_data: dict):
        payload = {"type": "scene_activation", "sequence_id": self.next_sequence_id(), "timestamp": datetime.datetime.now().isoformat(), "scene_id": scene_id, "scene_data": scene_data}
        await self.broadcast_displays(payload)

    async def broadcast_content_update(self, content_data: dict, target_displays: list[str] | None = None):
        payload = {"type": "content_update", "sequence_id": self.next_sequence_id(), "timestamp": datetime.datetime.now().isoformat(), "content": content_data}
        await self.broadcast_displays(payload, target_displays)

    async def broadcast_epoch_started(self, scene_id: str, epoch_number: int, distribution_stats: dict):
        payload = {"type": "epoch_started", "sequence_id": self.next_sequence_id(), "timestamp": datetime.datetime.now().isoformat(), "scene_id": scene_id, "epoch_number": epoch_number, "distribution_stats": distribution_stats}
        await self.broadcast_dashboards(payload)

    async def broadcast_display_assignment(self, display_id: str, assignment_data: dict):
        payload = {"type": "display_assignment", "sequence_id": self.next_sequence_id(), "timestamp": datetime.datetime.now().isoformat(), "assignment": assignment_data}
        await self.send_to_display(json.dumps(payload), display_id)

    async def broadcast_heartbeat(self):
        payload = {"type": "heartbeat", "sequence_id": self.next_sequence_id(), "timestamp": datetime.datetime.now().isoformat(), "server_status": "online"}
        await self.broadcast_all(payload)

    async def broadcast_distribution_performance(self, scene_id: str, performance_metrics: dict):
        payload = {"type": "distribution_performance", "sequence_id": self.next_sequence_id(), "timestamp": datetime.datetime.now().isoformat(), "scene_id": scene_id, "metrics": performance_metrics}
        await self.broadcast_dashboards(payload)

    # Stats APIs
    def get_connection_stats(self) -> dict[str, Any]:
        dashboards = sum(1 for ws, meta in self.connection_metadata.items() if meta.get("type") == "dashboard")
        return {
            "total_connections": len(self.active_connections),
            "dashboard_connections": dashboards,
            "display_connections": len(self.display_connections),
            "connected_displays": list(self.display_connections.keys()),
            "sequence_id": self.sequence_id,
        }

    def get_connected_clients_count(self) -> int:  # legacy
        return len(self.active_connections)


# Backwards compatibility exported name
ConnectionManager = WebSocketManager  # alias

# Export singleton instance (preferred modern name `websocket_manager`)
websocket_manager = WebSocketManager()

