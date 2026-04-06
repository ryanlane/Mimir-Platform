"""
WebSocket Manager
Infrastructure component for WebSocket connection management
"""
import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import WebSocket
from datetime import datetime


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.display_connections: Dict[str, WebSocket] = {}  # display_id -> websocket
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self.sequence_id = 0
    
    async def connect(self, websocket: WebSocket, client_type: str = "dashboard", **metadata):
        """Accept WebSocket connection and store metadata"""
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # Store connection metadata
        self.connection_metadata[websocket] = {
            "type": client_type,
            "connected_at": datetime.utcnow(),
            **metadata
        }
        
        # Handle display client connections
        if client_type == "display" and "display_id" in metadata:
            display_id = metadata["display_id"]
            self.display_connections[display_id] = websocket
            # TODO: Update database status when database dependency is available
    
    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            
        # Handle display client disconnection
        metadata = self.connection_metadata.get(websocket, {})
        if metadata.get("type") == "display":
            display_id = metadata.get("display_id")
            if display_id and display_id in self.display_connections:
                del self.display_connections[display_id]
                # TODO: Update database status when database dependency is available
        
        # Clean up metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
    
    def get_next_sequence_id(self) -> int:
        """Generate next sequence ID for message ordering"""
        self.sequence_id += 1
        return self.sequence_id
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)
    
    async def send_to_display_client(self, display_client_id: str, message: Dict[str, Any]) -> bool:
        """Send message to specific display client"""
        websocket = self.display_connections.get(display_client_id)
        if websocket:
            try:
                await websocket.send_text(json.dumps(message))
                return True
            except:
                self.disconnect(websocket)
                return False
        return False
    
    async def broadcast_to_display_clients(
        self, 
        message: Dict[str, Any], 
        target_display_ids: Optional[List[str]] = None
    ) -> Dict[str, bool]:
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
        
        for display_id, websocket in target_connections.items():
            try:
                await websocket.send_text(message_str)
                results[display_id] = True
            except:
                self.disconnect(websocket)
                results[display_id] = False
                
        return results
    
    async def broadcast_to_dashboard_clients(self, message: Dict[str, Any]):
        """Broadcast to dashboard/admin clients only"""
        message_str = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            metadata = self.connection_metadata.get(connection, {})
            if metadata.get("type") != "display":  # Send to non-display clients
                try:
                    await connection.send_text(message_str)
                except:
                    disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        message_str = json.dumps(message)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except:
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get information about current connections"""
        return {
            "total_connections": len(self.active_connections),
            "display_connections": len(self.display_connections),
            "dashboard_connections": len(self.active_connections) - len(self.display_connections),
            "display_clients": list(self.display_connections.keys())
        }
    
    def get_display_client_status(self, display_id: str) -> Dict[str, Any]:
        """Get status of specific display client"""
        websocket = self.display_connections.get(display_id)
        if not websocket:
            return {"connected": False}
        
        metadata = self.connection_metadata.get(websocket, {})
        return {
            "connected": True,
            "connected_at": metadata.get("connected_at"),
            "metadata": metadata
        }
