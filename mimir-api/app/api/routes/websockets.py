"""WebSocket API Routes using unified WebSocketManager.

This module exposes two endpoints:
    - /ws : dashboard / generic clients
    - /ws/display/{display_id} : display clients

Responsibilities intentionally minimal — business logic now lives in
`app.services.websocket_manager.WebSocketManager`.
"""
from __future__ import annotations

import asyncio
import datetime
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import websocket_manager as manager

router = APIRouter(tags=["websockets"])  # Reuse global singleton


@router.get("/api/websocket/status")
async def get_websocket_status():
    """Return basic status/feature info about current WebSocket subsystem."""
    # Use available public stats accessor
    stats = manager.get_connection_stats()
    return {
        "connected_clients": stats["total_connections"],
        "websocket_url": "/ws",  # Client can resolve scheme/host
        "current_sequence_id": stats["sequence_id"],
        "features": {
            "full_state_on_connect": True,
            "heartbeat_support": True,
            "generic_event_envelope": True,
            "channel_status_updates": True,
        },
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Dashboard / generic client endpoint.

    Incoming messages currently support a minimal subset (ping/state_sync_request).
    All outbound messages unified under `emit_event` envelope.
    """
    await manager.connect_dashboard(websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Heartbeat ping
                await manager.emit_event("ping", {"timestamp": datetime.datetime.now().isoformat()}, targets=[websocket])
                continue

            # Attempt JSON parse; if fail echo raw text
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await manager.emit_event("echo", {"text": data}, targets=[websocket])
                continue

            event = msg.get("event")
            if event == "ping":
                await manager.emit_event("pong", {"timestamp": datetime.datetime.now().isoformat()}, targets=[websocket])
            elif event == "state_sync_request":
                # Provide snapshot-like minimal info (reuse stats for now)
                await manager.emit_event("state_snapshot", manager.get_connection_stats(), targets=[websocket])
            else:
                await manager.emit_event("unknown_event", {"original": msg}, targets=[websocket])
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:  # pragma: no cover - defensive
        manager.disconnect(websocket)


# Legacy helper handlers removed; logic simplified inline in endpoint.


# Heartbeat now uses manager.emit_event directly inside loop.


async def handle_display_status_update(data: dict):  # compatibility wrapper (may expand later)
    await manager.emit_event("display_status_changed", data)


async def handle_scene_change_request(data: dict):  # compatibility wrapper
    await manager.emit_event("scene_change_requested", {
        "scene_id": data.get("scene_id"),
        "display_id": data.get("display_id"),
        "requested_by": "websocket_client",
    })


@router.websocket("/ws/display/{display_id}")
async def display_websocket_endpoint(websocket: WebSocket, display_id: str):
    """Display client endpoint using unified manager."""
    await manager.connect_display(websocket, display_id)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.emit_event("error", {"message": "Invalid JSON", "raw": raw}, targets=[websocket])
                continue

            event = msg.get("event")
            if event == "status_update":
                payload = {"display_id": display_id, **msg.get("data", {})}
                await handle_display_status_update(payload)
            elif event == "content_rendered":
                await manager.emit_event("content_rendered", {"display_id": display_id, **msg.get("data", {})})
            elif event == "error":
                await manager.emit_event("display_error", {"display_id": display_id, **msg.get("data", {})})
            else:
                await manager.emit_event("message_acknowledged", {"display_id": display_id, "original_event": event}, targets=[websocket])
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:  # pragma: no cover - defensive
        manager.disconnect(websocket)


# Removed legacy per-message handler; logic handled inline for simplicity.
