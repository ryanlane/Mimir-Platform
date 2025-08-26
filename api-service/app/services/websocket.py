"""
WebSocket Management Service
Handles WebSocket connections, broadcasting, and display client communication
"""
import json
import datetime
from typing import List, Dict, Optional, Any
from fastapi import WebSocket

from app.db.base import SessionLocal
from app.db.models import DisplayClient
from app.core.logging import get_logger


logger = get_logger(__name__)


class WebSocketService:
    """Service for managing WebSocket connections and real-time communication"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.display_connections: Dict[str, WebSocket] = {}  # display_client_id -> websocket
        self.connection_metadata: Dict[WebSocket, Dict] = {}  # websocket -> metadata
        self.sequence_id = 0

    async def connect(self, websocket: WebSocket, connection_type: str = "dashboard"):
        """Connect a general WebSocket client"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "type": connection_type,
            "connected_at": datetime.datetime.now()
        }
        logger.info(f"WebSocket connected: {connection_type}")

    async def connect_display_client(self, websocket: WebSocket, display_client_id: str):
        """Connect a specific display client"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.display_connections[display_client_id] = websocket
        self.connection_metadata[websocket] = {
            "type": "display", 
            "display_id": display_client_id,
            "connected_at": datetime.datetime.now()
        }
        
        # Update database status
        await self._update_display_status(display_client_id, is_online=True)
        logger.info(f"Display client connected: {display_client_id}")

    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket and clean up resources"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        # Handle display client disconnection
        metadata = self.connection_metadata.get(websocket, {})
        if metadata.get("type") == "display":
            display_id = metadata.get("display_id")
            if display_id and display_id in self.display_connections:
                del self.display_connections[display_id]
                
                # Update database status asynchronously
                import asyncio
                asyncio.create_task(self._update_display_status(display_id, is_online=False))
                logger.info(f"Display client disconnected: {display_id}")
        
        # Clean up metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]

    async def _update_display_status(self, display_id: str, is_online: bool):
        """Update display client status in database"""
        db = SessionLocal()
        try:
            client = db.query(DisplayClient).filter(DisplayClient.id == display_id).first()
            if client:
                client.is_online = is_online
                client.last_seen = datetime.datetime.now()
                if is_online:
                    client.websocket_connection_id = display_id
                else:
                    client.websocket_connection_id = None
                db.commit()
                logger.debug(f"Updated display status: {display_id} -> online={is_online}")
        except Exception as e:
            logger.error(f"Error updating display status for {display_id}: {e}")
        finally:
            db.close()

    def get_next_sequence_id(self) -> int:
        """Get next sequence ID for message ordering"""
        self.sequence_id += 1
        return self.sequence_id

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            self.disconnect(websocket)
            return False

    async def send_to_display_client(self, display_client_id: str, message: dict):
        """Send message to specific display client"""
        websocket = self.display_connections.get(display_client_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps(message))
                logger.debug(f"Message sent to display {display_client_id}: {message.get('type', 'unknown')}")
                return True
            except Exception as e:
                logger.warning(f"Failed to send message to display {display_client_id}: {e}")
                self.disconnect(websocket)
                return False
        else:
            logger.warning(f"Display client not connected: {display_client_id}")
            return False

    async def broadcast_to_display_clients(self, message: dict, target_display_ids: Optional[List[str]] = None):
        """Broadcast to display clients (all or specific ones)"""
        message_str = json.dumps(message)
        results = {}
        
        target_connections = {}
        if target_display_ids:
            # Send to specific display clients
            for display_id in target_display_ids:
                if display_id in self.display_connections:
                    target_connections[display_id] = self.display_connections[display_id]
        else:
            # Send to all display clients
            target_connections = self.display_connections.copy()
        
        # Send to target connections
        for display_id, websocket in target_connections.items():
            try:
                await websocket.send_text(message_str)
                results[display_id] = {"status": "sent", "error": None}
            except Exception as e:
                logger.warning(f"Failed to broadcast to display {display_id}: {e}")
                self.disconnect(websocket)
                results[display_id] = {"status": "failed", "error": str(e)}
        
        logger.info(f"Broadcast complete: {len(results)} targets, message type: {message.get('type', 'unknown')}")
        return results

    async def broadcast_to_dashboards(self, message: dict):
        """Broadcast message to dashboard connections only"""
        message_str = json.dumps(message)
        dashboard_connections = [
            ws for ws in self.active_connections 
            if self.connection_metadata.get(ws, {}).get("type") == "dashboard"
        ]
        
        results = []
        for websocket in dashboard_connections:
            try:
                await websocket.send_text(message_str)
                results.append({"status": "sent", "error": None})
            except Exception as e:
                logger.warning(f"Failed to broadcast to dashboard: {e}")
                self.disconnect(websocket)
                results.append({"status": "failed", "error": str(e)})
        
        logger.debug(f"Dashboard broadcast complete: {len(results)} connections")
        return results

    async def broadcast_all(self, message: dict):
        """Broadcast message to all connected clients"""
        message_str = json.dumps(message)
        results = []
        
        # Create a copy to avoid modification during iteration
        connections = self.active_connections.copy()
        
        for websocket in connections:
            try:
                await websocket.send_text(message_str)
                results.append({"status": "sent", "error": None})
            except Exception as e:
                logger.warning(f"Failed to broadcast to connection: {e}")
                self.disconnect(websocket)
                results.append({"status": "failed", "error": str(e)})
        
        logger.info(f"Global broadcast complete: {len(results)} connections")
        return results

    # Content distribution specific methods
    async def broadcast_scene_activation(self, scene_id: str, scene_data: dict):
        """Broadcast scene activation to display clients"""
        message = {
            "type": "scene_activation",
            "sequence_id": self.get_next_sequence_id(),
            "timestamp": datetime.datetime.now().isoformat(),
            "scene_id": scene_id,
            "scene_data": scene_data
        }
        return await self.broadcast_to_display_clients(message)

    async def broadcast_content_update(self, content_data: dict, target_displays: Optional[List[str]] = None):
        """Broadcast content update to displays"""
        message = {
            "type": "content_update",
            "sequence_id": self.get_next_sequence_id(),
            "timestamp": datetime.datetime.now().isoformat(),
            "content": content_data
        }
        return await self.broadcast_to_display_clients(message, target_displays)

    async def broadcast_epoch_started(self, scene_id: str, epoch_number: int, distribution_stats: dict):
        """Broadcast epoch start notification"""
        message = {
            "type": "epoch_started",
            "sequence_id": self.get_next_sequence_id(),
            "timestamp": datetime.datetime.now().isoformat(),
            "scene_id": scene_id,
            "epoch_number": epoch_number,
            "distribution_stats": distribution_stats
        }
        await self.broadcast_to_dashboards(message)

    async def broadcast_display_assignment(self, display_id: str, assignment_data: dict):
        """Broadcast display assignment to specific display"""
        message = {
            "type": "display_assignment",
            "sequence_id": self.get_next_sequence_id(),
            "timestamp": datetime.datetime.now().isoformat(),
            "assignment": assignment_data
        }
        return await self.send_to_display_client(display_id, message)

    async def broadcast_heartbeat(self):
        """Send heartbeat to all connections"""
        message = {
            "type": "heartbeat",
            "sequence_id": self.get_next_sequence_id(),
            "timestamp": datetime.datetime.now().isoformat(),
            "server_status": "online"
        }
        return await self.broadcast_all(message)

    async def broadcast_distribution_performance(self, scene_id: str, performance_metrics: dict):
        """Broadcast distribution performance metrics"""
        message = {
            "type": "distribution_performance",
            "sequence_id": self.get_next_sequence_id(),
            "timestamp": datetime.datetime.now().isoformat(),
            "scene_id": scene_id,
            "metrics": performance_metrics
        }
        await self.broadcast_to_dashboards(message)

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics"""
        dashboard_count = sum(
            1 for ws in self.active_connections 
            if self.connection_metadata.get(ws, {}).get("type") == "dashboard"
        )
        
        display_count = len(self.display_connections)
        total_count = len(self.active_connections)
        
        return {
            "total_connections": total_count,
            "dashboard_connections": dashboard_count,
            "display_connections": display_count,
            "connected_displays": list(self.display_connections.keys()),
            "sequence_id": self.sequence_id
        }

    def get_display_connection_status(self, display_id: str) -> Dict[str, Any]:
        """Get connection status for specific display"""
        is_connected = display_id in self.display_connections
        websocket = self.display_connections.get(display_id)
        metadata = self.connection_metadata.get(websocket) if websocket else None
        
        return {
            "display_id": display_id,
            "is_connected": is_connected,
            "connected_at": metadata.get("connected_at") if metadata else None,
            "connection_type": metadata.get("type") if metadata else None
        }


# Global service instance
websocket_service = WebSocketService()
