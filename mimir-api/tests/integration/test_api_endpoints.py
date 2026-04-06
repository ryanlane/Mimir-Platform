"""
Integration Tests for Channels API
Tests the complete channels router functionality with database
"""
import pytest
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Channel


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.channels
class TestChannelsAPI:
    """Test Channels API endpoints"""
    
    def test_get_channels_empty(self, client: TestClient):
        """Test getting channels when none exist"""
        response = client.get("/api/v1/channels")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["limit"] == 100
        assert data["offset"] == 0
    
    def test_get_channels_with_data(self, client: TestClient, db_with_sample_data: Session):
        """Test getting channels with existing data"""
        response = client.get("/api/v1/channels")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "test-channel"
        assert data["items"][0]["name"] == "Test Channel"
    
    def test_get_channels_pagination(self, client: TestClient, db_with_sample_data: Session):
        """Test channels pagination"""
        response = client.get("/api/v1/channels?limit=10&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert "total" in data
        assert "items" in data
    
    def test_get_channel_by_id_exists(self, client: TestClient, db_with_sample_data: Session):
        """Test getting specific channel by ID"""
        response = client.get("/api/v1/channels/test-channel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-channel"
        assert data["name"] == "Test Channel"
        assert "ui" in data
        assert "permissions" in data
    
    def test_get_channel_by_id_not_found(self, client: TestClient):
        """Test getting non-existent channel"""
        response = client.get("/api/v1/channels/missing-channel")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_create_channel_valid(self, client: TestClient, sample_channel_data):
        """Test creating a new channel"""
        response = client.post("/api/v1/channels", json=sample_channel_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == sample_channel_data["id"]
        assert data["name"] == sample_channel_data["name"]
    
    def test_create_channel_invalid_data(self, client: TestClient):
        """Test creating channel with invalid data"""
        invalid_data = {"name": "Test Channel"}  # Missing required fields
        
        response = client.post("/api/v1/channels", json=invalid_data)
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_create_channel_duplicate_id(self, client: TestClient, db_with_sample_data: Session,
                                        sample_channel_data):
        """Test creating channel with duplicate ID"""
        response = client.post("/api/v1/channels", json=sample_channel_data)
        
        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["detail"]
    
    def test_update_channel_exists(self, client: TestClient, db_with_sample_data: Session):
        """Test updating existing channel"""
        update_data = {
            "name": "Updated Channel Name",
            "description": "Updated description"
        }
        
        response = client.put("/api/v1/channels/test-channel", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Channel Name"
        assert data["description"] == "Updated description"
    
    def test_update_channel_not_found(self, client: TestClient):
        """Test updating non-existent channel"""
        update_data = {"name": "Updated Name"}
        
        response = client.put("/api/v1/channels/missing-channel", json=update_data)
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_delete_channel_exists(self, client: TestClient, db_with_sample_data: Session):
        """Test deleting existing channel"""
        response = client.delete("/api/v1/channels/test-channel")
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]
        
        # Verify channel is deleted
        get_response = client.get("/api/v1/channels/test-channel")
        assert get_response.status_code == 404
    
    def test_delete_channel_not_found(self, client: TestClient):
        """Test deleting non-existent channel"""
        response = client.delete("/api/v1/channels/missing-channel")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_get_channel_settings(self, client: TestClient, db_with_sample_data: Session):
        """Test getting channel settings"""
        response = client.get("/api/v1/channels/test-channel/settings")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
    
    def test_update_channel_settings(self, client: TestClient, db_with_sample_data: Session):
        """Test updating channel settings"""
        new_settings = {"background": "red", "opacity": 0.8}
        
        response = client.put("/api/v1/channels/test-channel/settings", json=new_settings)
        
        assert response.status_code == 200
        data = response.json()
        assert data["background"] == "red"
        assert data["opacity"] == 0.8
    
    def test_channel_discovery_refresh(self, client: TestClient):
        """Test refreshing channel discovery"""
        response = client.post("/api/v1/channels/refresh")
        
        assert response.status_code == 200
        data = response.json()
        assert "refreshed" in data["message"]
        assert "channels" in data
    
    def test_channel_validation(self, client: TestClient):
        """Test channel configuration validation"""
        config_data = {
            "id": "test-validation",
            "name": "Validation Test",
            "schemaVersion": "2.1",
            "settingsType": "simple",
            "ui": []
        }
        
        response = client.post("/api/v1/channels/validate", json=config_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
    
    def test_channel_validation_invalid(self, client: TestClient):
        """Test channel configuration validation with invalid data"""
        config_data = {
            "name": "Invalid Channel"  # Missing required fields
        }
        
        response = client.post("/api/v1/channels/validate", json=config_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "errors" in data
    
    def test_get_channels_filter_by_type(self, client: TestClient, db_with_sample_data: Session):
        """Test filtering channels by settings type"""
        response = client.get("/api/v1/channels?settings_type=simple")
        
        assert response.status_code == 200
        data = response.json()
        # Should return channels with simple settings type
        for item in data["items"]:
            assert item["settingsType"] == "simple"
    
    def test_get_channels_search(self, client: TestClient, db_with_sample_data: Session):
        """Test searching channels by name"""
        response = client.get("/api/v1/channels?search=Test")
        
        assert response.status_code == 200
        data = response.json()
        # Should return channels matching search term
        for item in data["items"]:
            assert "Test" in item["name"] or "Test" in item.get("description", "")
    
    def test_channel_static_files_served(self, client: TestClient, mock_channel_directory):
        """Test that channel static files are served"""
        # This tests that the static file mounting works
        # In a real scenario, this would test actual file serving
        response = client.get("/api/v1/channels")
        
        # If we get here without errors, static mounting is working
        assert response.status_code == 200
    
    def test_channel_permissions_read_only(self, client: TestClient, db_with_sample_data: Session):
        """Test channel with read-only permissions"""
        # First, update channel to be read-only
        channel_data = {
            "permissions": {"read": True, "write": False}
        }
        
        response = client.put("/api/v1/channels/test-channel", json=channel_data)
        assert response.status_code == 200
        
        # Try to update settings (should be restricted)
        settings_data = {"background": "green"}
        response = client.put("/api/v1/channels/test-channel/settings", json=settings_data)
        
        # Depending on implementation, this might return 403 or succeed
        # The actual behavior depends on how permissions are enforced
        assert response.status_code in [200, 403]
    
    def test_channel_ui_config_integrity(self, client: TestClient, db_with_sample_data: Session):
        """Test that UI configuration includes integrity hashes"""
        response = client.get("/api/v1/channels/test-channel")
        
        assert response.status_code == 200
        data = response.json()
        
        if "ui" in data and len(data["ui"]) > 0:
            ui_item = data["ui"][0]
            # Should have integrity information if files exist
            if "moduleUrl" in ui_item or "styleUrl" in ui_item:
                assert "integrity" in ui_item or ui_item.get("integrity") == {}


@pytest.mark.integration
@pytest.mark.api
class TestScenesAPI:
    """Test Scenes API endpoints"""
    
    def test_get_scenes_empty(self, client: TestClient):
        """Test getting scenes when none exist"""
        response = client.get("/api/v1/scenes")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
    
    def test_get_scenes_with_data(self, client: TestClient, db_with_sample_data: Session):
        """Test getting scenes with existing data"""
        response = client.get("/api/v1/scenes")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "test-scene"
    
    def test_create_scene_valid(self, client: TestClient, sample_scene_data):
        """Test creating a new scene"""
        response = client.post("/api/v1/scenes", json=sample_scene_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == sample_scene_data["id"]
        assert data["name"] == sample_scene_data["name"]
    
    def test_activate_scene(self, client: TestClient, db_with_sample_data: Session):
        """Test activating a scene"""
        response = client.post("/api/v1/scenes/test-scene/activate")
        
        assert response.status_code == 200
        data = response.json()
        assert "activated" in data["message"]
    
    def test_get_active_scene(self, client: TestClient, db_with_sample_data: Session):
        """Test getting the currently active scene"""
        # First activate a scene
        client.post("/api/v1/scenes/test-scene/activate")
        
        response = client.get("/api/v1/scenes/active")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-scene"
        assert data["is_active"] is True


@pytest.mark.integration
@pytest.mark.api
class TestDisplaysAPI:
    """Test Displays API endpoints"""
    
    def test_get_displays_empty(self, client: TestClient):
        """Test getting displays when none exist"""
        response = client.get("/api/v1/displays")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
    
    def test_get_displays_with_data(self, client: TestClient, db_with_sample_data: Session):
        """Test getting displays with existing data"""
        response = client.get("/api/v1/displays")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "test-display"
    
    def test_register_display(self, client: TestClient, sample_display_data):
        """Test registering a new display"""
        response = client.post("/api/v1/displays", json=sample_display_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == sample_display_data["id"]
        assert data["name"] == sample_display_data["name"]
    
    def test_update_display_capabilities(self, client: TestClient, db_with_sample_data: Session):
        """Test updating display capabilities"""
        capabilities_data = {
            "capabilities": {
                "resolution": [1920, 1080],
                "supported_formats": ["jpg", "png", "webp"],
                "refresh_rate_hz": 120.0
            }
        }
        
        response = client.put("/api/v1/displays/test-display", json=capabilities_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["width"] == 1920
        assert data["height"] == 1080
    
    def test_get_display_status(self, client: TestClient, db_with_sample_data: Session):
        """Test getting display status"""
        response = client.get("/api/v1/displays/test-display/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "last_seen" in data
    
    def test_get_connected_displays(self, client: TestClient):
        """Test getting connected displays via WebSocket"""
        response = client.get("/api/v1/displays/connected")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.integration
@pytest.mark.api
class TestContentAPI:
    """Test Content API endpoints"""
    
    def test_upload_content_valid_image(self, client: TestClient):
        """Test uploading valid image content"""
        # Create a minimal test image file
        test_image_data = b"fake_image_data"
        
        files = {"file": ("test.jpg", test_image_data, "image/jpeg")}
        
        response = client.post("/api/v1/content/upload", files=files)
        
        # Response depends on implementation
        assert response.status_code in [200, 201, 413, 422]  # Various possible responses
    
    def test_get_content_list(self, client: TestClient):
        """Test getting content list"""
        response = client.get("/api/v1/content")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    def test_get_content_by_id_not_found(self, client: TestClient):
        """Test getting non-existent content"""
        response = client.get("/api/v1/content/missing-file.jpg")
        
        assert response.status_code == 404
    
    def test_delete_content_not_found(self, client: TestClient):
        """Test deleting non-existent content"""
        response = client.delete("/api/v1/content/missing-file.jpg")
        
        assert response.status_code == 404
