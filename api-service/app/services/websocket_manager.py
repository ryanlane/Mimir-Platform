"""
WebSocket Connection Manager
Manages WebSocket connections and real-time communication
"""
from fastapi import WebSocket
from typing import Dict, List, Set
import json
import datetime
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import Channel, Scene, DisplayClient


class ConnectionManager:
    """Manages WebSocket connections and broadcasts"""
    
    def __init__(self):
        # General WebSocket connections
        self.active_connections: List[WebSocket] = []
        
        # Display-specific connections
        self.display_connections: Dict[str, WebSocket] = {}
        
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, dict] = {}
        
        # Sequence ID for message ordering
        self.current_sequence_id: int = 0


    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "connected_at": datetime.datetime.now(),
            "type": "general"
        }
        print(f"🔗 WebSocket connected. Total connections: {len(self.active_connections)}")


    async def connect_display(self, websocket: WebSocket, display_id: str):
        """Accept a display-specific WebSocket connection"""
        await websocket.accept()
        self.display_connections[display_id] = websocket
        self.connection_metadata[websocket] = {
            "connected_at": datetime.datetime.now(),
            "type": "display",
            "display_id": display_id
        }
        print(f"🖥️ Display WebSocket connected: {display_id}")


    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        # Remove from display connections if present
        display_id = None
        for did, ws in self.display_connections.items():
            if ws == websocket:
                display_id = did
                break
        
        if display_id:
            del self.display_connections[display_id]
            print(f"🖥️ Display WebSocket disconnected: {display_id}")
        
        # Clean up metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        print(f"🔗 WebSocket disconnected. Total connections: {len(self.active_connections)}")


    def disconnect_display(self, websocket: WebSocket, display_id: str):
        """Remove a display-specific WebSocket connection"""
        if display_id in self.display_connections:
            del self.display_connections[display_id]
        
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        
        print(f"🖥️ Display WebSocket disconnected: {display_id}")


    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"❌ Failed to send message to WebSocket: {e}")
            # Remove failed connection
            self.disconnect(websocket)


    async def send_to_display(self, message: str, display_id: str):
        """Send message to specific display"""
        if display_id in self.display_connections:
            websocket = self.display_connections[display_id]
            try:
                await websocket.send_text(message)
            except Exception as e:
                print(f"❌ Failed to send message to display {display_id}: {e}")
                self.disconnect_display(websocket, display_id)


    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSockets"""
        disconnected = []
        
        # Send to general connections
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"❌ Failed to broadcast to connection: {e}")
                disconnected.append(connection)
        
        # Send to display connections
        for display_id, connection in self.display_connections.items():
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"❌ Failed to broadcast to display {display_id}: {e}")
                disconnected.append(connection)
        
        # Clean up failed connections
        for connection in disconnected:
            self.disconnect(connection)


    async def broadcast_to_displays(self, message: str, display_ids: List[str] = None):
        """Broadcast message to specific displays or all displays"""
        if display_ids is None:
            display_ids = list(self.display_connections.keys())
        
        for display_id in display_ids:
            await self.send_to_display(message, display_id)


    async def send_full_state(self, websocket: WebSocket):
        """Send complete application state to WebSocket client"""
        try:
            db = SessionLocal()
            
            # Get current state
            channels = db.query(Channel).all()
            scenes = db.query(Scene).all()
            displays = db.query(DisplayClient).all()
            
            state = {
                "event": "full_state",
                "data": {
                    "channels": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "version": c.version,
                            "description": c.description
                        } for c in channels
                    ],
                    "scenes": [
                        {
                            "id": s.id,
                            "name": s.name,
                            "channels": s.channels,
                            "is_active": s.is_active
                        } for s in scenes
                    ],
                    "displays": [
                        {
                            "id": d.id,
                            "name": d.name,
                            "location": d.location,
                            "is_online": d.is_online,
                            "assigned_scene_id": d.assigned_scene_id
                        } for d in displays
                    ],
                    "connection_count": len(self.active_connections) + len(self.display_connections)
                },
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            await self.send_personal_message(json.dumps(state), websocket)
            
        except Exception as e:
            print(f"❌ Failed to send full state: {e}")
        finally:
            db.close()


    def get_connection_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections) + len(self.display_connections),
            "general_connections": len(self.active_connections),
            "display_connections": len(self.display_connections),
            "connected_displays": list(self.display_connections.keys())
        }


    async def notify_scene_change(self, scene_id: str, display_ids: List[str] = None):
        """Notify about scene changes"""
        message = {
            "event": "scene_changed",
            "data": {
                "scene_id": scene_id,
                "display_ids": display_ids
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        if display_ids:
            await self.broadcast_to_displays(json.dumps(message), display_ids)
        else:
            await self.broadcast(json.dumps(message))


    async def notify_display_status_change(self, display_id: str, status: dict):
        """Notify about display status changes"""
        message = {
            "event": "display_status_changed",
            "data": {
                "display_id": display_id,
                "status": status
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        await self.broadcast(json.dumps(message))


    async def notify_channel_update(self, channel_id: str, update_type: str = "updated"):
        """Notify about channel updates"""
        message = {
            "event": "channel_updated",
            "data": {
                "channel_id": channel_id,
                "update_type": update_type
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        await self.broadcast(json.dumps(message))


    def get_connected_clients_count(self) -> int:
        """Get total number of connected clients"""
        return len(self.active_connections) + len(self.display_connections)


    def get_current_sequence_id(self) -> int:
        """Get current sequence ID"""
        return self.current_sequence_id


    def increment_sequence_id(self) -> int:
        """Increment and return the next sequence ID"""
        self.current_sequence_id += 1
        return self.current_sequence_id
