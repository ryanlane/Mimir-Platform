"""
WebSocket API Routes
FastAPI router for WebSocket connections and real-time communication
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import json
import asyncio
import datetime
from typing import Dict, List

from app.db.base import SessionLocal
from app.services.websocket_manager import ConnectionManager


router = APIRouter(tags=["websockets"])

# Global WebSocket connection manager
manager = ConnectionManager()


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time communication"""
    await manager.connect(websocket)
    
    try:
        # Send full state snapshot on connection
        await manager.send_full_state(websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client with timeout for heartbeat
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                try:
                    message = json.loads(data)
                    await handle_websocket_message(websocket, message)
                        
                except json.JSONDecodeError:
                    # Handle non-JSON messages
                    await manager.send_personal_message(f"Echo: {data}", websocket)
                    
            except asyncio.TimeoutError:
                # Send heartbeat ping if no message received
                await send_heartbeat(websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def handle_websocket_message(websocket: WebSocket, message: dict):
    """Handle incoming WebSocket messages"""
    event = message.get("event")
    
    if event == "ping":
        # Respond to ping with pong
        pong_response = {
            "event": "pong",
            "data": {"timestamp": datetime.datetime.now().isoformat()},
            "timestamp": datetime.datetime.now().isoformat()
        }
        await manager.send_personal_message(json.dumps(pong_response), websocket)
        
    elif event == "state_sync_request":
        # Handle state sync request
        await manager.send_full_state(websocket)
        
    elif event == "subscribe":
        # Handle subscription management
        events = message.get("data", {}).get("events", [])
        await manager.send_personal_message(
            json.dumps({
                "event": "subscription_confirmed",
                "data": {"events": events},
                "timestamp": datetime.datetime.now().isoformat()
            }),
            websocket
        )
        
    elif event == "display_status_update":
        # Handle display status updates
        await handle_display_status_update(websocket, message.get("data", {}))
        
    elif event == "scene_change_request":
        # Handle scene change requests
        await handle_scene_change_request(websocket, message.get("data", {}))
        
    else:
        # Echo back unknown messages for debugging
        await manager.send_personal_message(
            json.dumps({
                "event": "unknown_event",
                "data": message,
                "timestamp": datetime.datetime.now().isoformat()
            }),
            websocket
        )


async def send_heartbeat(websocket: WebSocket):
    """Send heartbeat ping message"""
    ping_message = {
        "event": "ping",
        "data": {"timestamp": datetime.datetime.now().isoformat()},
        "timestamp": datetime.datetime.now().isoformat()
    }
    await manager.send_personal_message(json.dumps(ping_message), websocket)


async def handle_display_status_update(websocket: WebSocket, data: dict):
    """Handle display status update messages"""
    # Broadcast display status updates to all connected clients
    status_message = {
        "event": "display_status_changed",
        "data": data,
        "timestamp": datetime.datetime.now().isoformat()
    }
    await manager.broadcast(json.dumps(status_message))


async def handle_scene_change_request(websocket: WebSocket, data: dict):
    """Handle scene change request messages"""
    # Process scene change and broadcast to relevant displays
    scene_id = data.get("scene_id")
    display_id = data.get("display_id")
    
    change_message = {
        "event": "scene_change_requested",
        "data": {
            "scene_id": scene_id,
            "display_id": display_id,
            "requested_by": "websocket_client"
        },
        "timestamp": datetime.datetime.now().isoformat()
    }
    await manager.broadcast(json.dumps(change_message))


@router.websocket("/ws/display/{display_id}")
async def display_websocket_endpoint(websocket: WebSocket, display_id: str):
    """WebSocket endpoint for specific display clients"""
    await manager.connect_display(websocket, display_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Add display_id to message context
                message["display_id"] = display_id
                
                # Handle display-specific messages
                await handle_display_message(websocket, display_id, message)
                
            except json.JSONDecodeError:
                error_response = {
                    "event": "error",
                    "data": {"message": "Invalid JSON format"},
                    "timestamp": datetime.datetime.now().isoformat()
                }
                await websocket.send_text(json.dumps(error_response))
                
    except WebSocketDisconnect:
        manager.disconnect_display(websocket, display_id)
    except Exception as e:
        print(f"Display WebSocket error for {display_id}: {e}")
        manager.disconnect_display(websocket, display_id)


async def handle_display_message(websocket: WebSocket, display_id: str, message: dict):
    """Handle messages from display clients"""
    event = message.get("event")
    
    if event == "status_update":
        # Update display status in database and broadcast
        await handle_display_status_update(websocket, {
            "display_id": display_id,
            **message.get("data", {})
        })
        
    elif event == "content_rendered":
        # Handle content rendering confirmation
        content_message = {
            "event": "content_rendered",
            "data": {
                "display_id": display_id,
                **message.get("data", {})
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        await manager.broadcast(json.dumps(content_message))
        
    elif event == "error":
        # Handle display errors
        error_message = {
            "event": "display_error",
            "data": {
                "display_id": display_id,
                **message.get("data", {})
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        await manager.broadcast(json.dumps(error_message))
        
    else:
        # Acknowledge unknown events
        ack_response = {
            "event": "message_acknowledged",
            "data": {"original_event": event},
            "timestamp": datetime.datetime.now().isoformat()
        }
        await websocket.send_text(json.dumps(ack_response))
