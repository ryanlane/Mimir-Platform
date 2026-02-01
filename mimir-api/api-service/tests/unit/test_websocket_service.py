"""
Unit Tests for WebSocketService
Tests WebSocket connection management, heartbeat monitoring, and broadcasting
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.websocket import WebSocketService
from app.db.models import DisplayClient, DisplayStatus


@pytest.mark.unit
@pytest.mark.websocket
class TestWebSocketService:
    """Test WebSocketService functionality"""
    
    @pytest.fixture
    def websocket_service(self):
        """Create WebSocketService instance"""
        return WebSocketService()
    
    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket connection"""
        websocket = Mock()
        websocket.accept = AsyncMock()
        websocket.send_text = AsyncMock()
        websocket.close = AsyncMock()
        return websocket
    
    @pytest.fixture
    def mock_display_client(self):
        """Mock DisplayClient model"""
        display = Mock(spec=DisplayClient)
        display.id = "test-display-1"
        display.name = "Test Display"
        display.hostname = "test-host"
        display.webhook_port = 8080
        return display
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = Mock()
        session.query = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session
    
    def test_init_websocket_service(self, websocket_service):
        """Test WebSocketService initialization"""
        assert websocket_service.connections == {}
        assert websocket_service.heartbeat_task is None
    
    @pytest.mark.asyncio
    async def test_connect_display_client_success(self, websocket_service, mock_websocket, 
                                                 mock_display_client, mock_db_session):
        """Test successful display client connection"""
        display_id = "test-display-1"
        
        with patch.object(websocket_service, '_update_display_status') as mock_update:
            await websocket_service.connect_display_client(
                websocket=mock_websocket,
                display_id=display_id,
                display_client=mock_display_client,
                db=mock_db_session
            )
            
            # Should accept WebSocket connection
            mock_websocket.accept.assert_called_once()
            
            # Should store connection
            assert display_id in websocket_service.connections
            assert websocket_service.connections[display_id]["websocket"] == mock_websocket
            assert websocket_service.connections[display_id]["display_client"] == mock_display_client
            
            # Should update status to connected
            mock_update.assert_called_with(mock_db_session, display_id, "connected")
    
    @pytest.mark.asyncio
    async def test_connect_display_client_already_connected(self, websocket_service, 
                                                           mock_websocket, mock_display_client,
                                                           mock_db_session):
        """Test connecting already connected display client"""
        display_id = "test-display-1"
        
        # Pre-populate connection
        old_websocket = Mock()
        old_websocket.close = AsyncMock()
        websocket_service.connections[display_id] = {
            "websocket": old_websocket,
            "display_client": mock_display_client,
            "last_heartbeat": datetime.now()
        }
        
        await websocket_service.connect_display_client(
            websocket=mock_websocket,
            display_id=display_id,
            display_client=mock_display_client,
            db=mock_db_session
        )
        
        # Should close old connection
        old_websocket.close.assert_called_once()
        
        # Should accept new connection
        mock_websocket.accept.assert_called_once()
        
        # Should update connection
        assert websocket_service.connections[display_id]["websocket"] == mock_websocket
    
    @pytest.mark.asyncio
    async def test_disconnect_display_client(self, websocket_service, mock_websocket,
                                            mock_display_client, mock_db_session):
        """Test disconnecting display client"""
        display_id = "test-display-1"
        
        # Setup connection
        websocket_service.connections[display_id] = {
            "websocket": mock_websocket,
            "display_client": mock_display_client,
            "last_heartbeat": datetime.now()
        }
        
        with patch.object(websocket_service, '_update_display_status') as mock_update:
            await websocket_service.disconnect_display_client(display_id, mock_db_session)
            
            # Should close WebSocket
            mock_websocket.close.assert_called_once()
            
            # Should remove connection
            assert display_id not in websocket_service.connections
            
            # Should update status to disconnected
            mock_update.assert_called_with(mock_db_session, display_id, "disconnected")
    
    @pytest.mark.asyncio
    async def test_disconnect_display_client_not_connected(self, websocket_service, mock_db_session):
        """Test disconnecting non-connected display client"""
        display_id = "non-existent"
        
        # Should not raise exception
        await websocket_service.disconnect_display_client(display_id, mock_db_session)
        
        # Connections should remain empty
        assert websocket_service.connections == {}
    
    @pytest.mark.asyncio
    async def test_send_message_to_display(self, websocket_service, mock_websocket,
                                          mock_display_client):
        """Test sending message to specific display"""
        display_id = "test-display-1"
        message = {"type": "update", "content": "test"}
        
        # Setup connection
        websocket_service.connections[display_id] = {
            "websocket": mock_websocket,
            "display_client": mock_display_client,
            "last_heartbeat": datetime.now()
        }
        
        success = await websocket_service.send_message_to_display(display_id, message)
        
        assert success is True
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    
    @pytest.mark.asyncio
    async def test_send_message_to_display_not_connected(self, websocket_service):
        """Test sending message to non-connected display"""
        display_id = "non-existent"
        message = {"type": "update", "content": "test"}
        
        success = await websocket_service.send_message_to_display(display_id, message)
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_send_message_to_display_websocket_error(self, websocket_service, 
                                                          mock_websocket, mock_display_client):
        """Test sending message when WebSocket raises error"""
        display_id = "test-display-1"
        message = {"type": "update", "content": "test"}
        
        # Setup connection
        websocket_service.connections[display_id] = {
            "websocket": mock_websocket,
            "display_client": mock_display_client,
            "last_heartbeat": datetime.now()
        }
        
        # Mock WebSocket error
        mock_websocket.send_text.side_effect = Exception("Connection error")
        
        success = await websocket_service.send_message_to_display(display_id, message)
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_broadcast_to_all_displays(self, websocket_service):
        """Test broadcasting message to all connected displays"""
        message = {"type": "broadcast", "content": "test"}
        
        # Setup multiple connections
        mock_ws1 = Mock()
        mock_ws1.send_text = AsyncMock()
        mock_ws2 = Mock()
        mock_ws2.send_text = AsyncMock()
        
        websocket_service.connections = {
            "display-1": {
                "websocket": mock_ws1,
                "display_client": Mock(),
                "last_heartbeat": datetime.now()
            },
            "display-2": {
                "websocket": mock_ws2,
                "display_client": Mock(),
                "last_heartbeat": datetime.now()
            }
        }
        
        await websocket_service.broadcast_to_all_displays(message)
        
        # Should send to all displays
        mock_ws1.send_text.assert_called_once_with(json.dumps(message))
        mock_ws2.send_text.assert_called_once_with(json.dumps(message))
    
    @pytest.mark.asyncio
    async def test_broadcast_to_all_displays_empty(self, websocket_service):
        """Test broadcasting when no displays connected"""
        message = {"type": "broadcast", "content": "test"}
        
        # Should not raise exception
        await websocket_service.broadcast_to_all_displays(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_scene_update(self, websocket_service):
        """Test broadcasting scene update"""
        scene_data = {"id": "scene-1", "name": "Test Scene"}
        
        with patch.object(websocket_service, 'broadcast_to_all_displays') as mock_broadcast:
            await websocket_service.broadcast_scene_update(scene_data)
            
            # Should broadcast with correct message format
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args[0][0]
            assert call_args["type"] == "scene_update"
            assert call_args["scene"] == scene_data
    
    @pytest.mark.asyncio
    async def test_broadcast_content_update(self, websocket_service):
        """Test broadcasting content update"""
        content_data = {"path": "/test.jpg", "size": 1024}
        
        with patch.object(websocket_service, 'broadcast_to_all_displays') as mock_broadcast:
            await websocket_service.broadcast_content_update(content_data)
            
            # Should broadcast with correct message format
            mock_broadcast.assert_called_once()
            call_args = mock_broadcast.call_args[0][0]
            assert call_args["type"] == "content_update"
            assert call_args["content"] == content_data
    
    def test_get_connected_displays(self, websocket_service, mock_display_client):
        """Test getting list of connected displays"""
        # Setup connections
        websocket_service.connections = {
            "display-1": {
                "websocket": Mock(),
                "display_client": mock_display_client,
                "last_heartbeat": datetime.now()
            },
            "display-2": {
                "websocket": Mock(),
                "display_client": mock_display_client,
                "last_heartbeat": datetime.now()
            }
        }
        
        connected = websocket_service.get_connected_displays()
        
        assert len(connected) == 2
        assert "display-1" in connected
        assert "display-2" in connected
        assert all("display_client" in info for info in connected.values())
    
    def test_is_display_connected(self, websocket_service, mock_display_client):
        """Test checking if display is connected"""
        display_id = "test-display-1"
        
        # Not connected initially
        assert websocket_service.is_display_connected(display_id) is False
        
        # Connect display
        websocket_service.connections[display_id] = {
            "websocket": Mock(),
            "display_client": mock_display_client,
            "last_heartbeat": datetime.now()
        }
        
        # Should be connected now
        assert websocket_service.is_display_connected(display_id) is True
    
    @pytest.mark.asyncio
    async def test_handle_heartbeat(self, websocket_service, mock_display_client):
        """Test handling heartbeat from display"""
        display_id = "test-display-1"
        
        # Setup connection with old heartbeat
        old_time = datetime.now() - timedelta(minutes=5)
        websocket_service.connections[display_id] = {
            "websocket": Mock(),
            "display_client": mock_display_client,
            "last_heartbeat": old_time
        }
        
        await websocket_service.handle_heartbeat(display_id)
        
        # Should update last_heartbeat
        new_time = websocket_service.connections[display_id]["last_heartbeat"]
        assert new_time > old_time
    
    @pytest.mark.asyncio
    async def test_handle_heartbeat_not_connected(self, websocket_service):
        """Test handling heartbeat from non-connected display"""
        display_id = "non-existent"
        
        # Should not raise exception
        await websocket_service.handle_heartbeat(display_id)
        
        # Connections should remain empty
        assert websocket_service.connections == {}
    
    @pytest.mark.asyncio
    async def test_start_heartbeat_monitor(self, websocket_service):
        """Test starting heartbeat monitor"""
        with patch('asyncio.create_task') as mock_create_task:
            websocket_service.start_heartbeat_monitor()
            
            # Should create heartbeat task
            mock_create_task.assert_called_once()
            assert websocket_service.heartbeat_task is not None
    
    @pytest.mark.asyncio
    async def test_stop_heartbeat_monitor(self, websocket_service):
        """Test stopping heartbeat monitor"""
        # Create mock task
        mock_task = Mock()
        mock_task.cancel = Mock()
        websocket_service.heartbeat_task = mock_task
        
        websocket_service.stop_heartbeat_monitor()
        
        # Should cancel task
        mock_task.cancel.assert_called_once()
        assert websocket_service.heartbeat_task is None
    
    @pytest.mark.asyncio
    async def test_stop_heartbeat_monitor_no_task(self, websocket_service):
        """Test stopping heartbeat monitor when no task exists"""
        # Should not raise exception
        websocket_service.stop_heartbeat_monitor()
        
        assert websocket_service.heartbeat_task is None
    
    @pytest.mark.asyncio
    async def test_heartbeat_monitor_loop(self, websocket_service, mock_db_session):
        """Test heartbeat monitor loop functionality"""
        display_id = "test-display-1"
        
        # Setup connection with stale heartbeat
        stale_time = datetime.now() - timedelta(minutes=10)
        mock_websocket = Mock()
        mock_websocket.close = AsyncMock()
        
        websocket_service.connections[display_id] = {
            "websocket": mock_websocket,
            "display_client": Mock(),
            "last_heartbeat": stale_time
        }
        
        with patch.object(websocket_service, '_update_display_status') as mock_update:
            # Run one iteration of the monitor
            await websocket_service._check_stale_connections(mock_db_session)
            
            # Should close stale connection
            mock_websocket.close.assert_called_once()
            
            # Should remove from connections
            assert display_id not in websocket_service.connections
            
            # Should update status
            mock_update.assert_called_with(mock_db_session, display_id, "disconnected")
    
    def test_update_display_status(self, websocket_service, mock_db_session):
        """Test updating display status in database"""
        display_id = "test-display-1"
        status = "connected"
        
        # Mock query chain
        mock_query = Mock()
        mock_display = Mock(spec=DisplayStatus)
        mock_query.filter.return_value.first.return_value = mock_display
        mock_db_session.query.return_value = mock_query
        
        websocket_service._update_display_status(mock_db_session, display_id, status)
        
        # Should query for display status
        mock_db_session.query.assert_called_with(DisplayStatus)
        
        # Should update status and timestamp
        assert mock_display.status == status
        assert mock_display.last_seen is not None
        
        # Should commit changes
        mock_db_session.commit.assert_called_once()
    
    def test_update_display_status_create_new(self, websocket_service, mock_db_session):
        """Test creating new display status record"""
        display_id = "test-display-1"
        status = "connected"
        
        # Mock query to return None (no existing record)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        websocket_service._update_display_status(mock_db_session, display_id, status)
        
        # Should add new DisplayStatus record
        mock_db_session.add.assert_called_once()
        
        # Should commit changes
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_all_connections(self, websocket_service, mock_db_session):
        """Test cleaning up all connections"""
        # Setup multiple connections
        mock_ws1 = Mock()
        mock_ws1.close = AsyncMock()
        mock_ws2 = Mock()
        mock_ws2.close = AsyncMock()
        
        websocket_service.connections = {
            "display-1": {
                "websocket": mock_ws1,
                "display_client": Mock(),
                "last_heartbeat": datetime.now()
            },
            "display-2": {
                "websocket": mock_ws2,
                "display_client": Mock(),
                "last_heartbeat": datetime.now()
            }
        }
        
        with patch.object(websocket_service, '_update_display_status') as mock_update:
            await websocket_service.cleanup_all_connections(mock_db_session)
            
            # Should close all connections
            mock_ws1.close.assert_called_once()
            mock_ws2.close.assert_called_once()
            
            # Should clear connections
            assert websocket_service.connections == {}
            
            # Should update all statuses
            assert mock_update.call_count == 2
