"""
Test Scene Model Updates for Sub-Channel Support

Tests the new scene model functionality that supports sub-channel assignments
while maintaining backward compatibility with existing scenes.
"""

import pytest
import json
from fastapi.testclient import TestClient
from main import app, get_db, Base, engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_scenes.db"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test tables
Base.metadata.create_all(bind=test_engine)

client = TestClient(app)

class TestSceneSubChannels:
    """Test scene functionality with sub-channel support"""
    
    def setup_method(self):
        """Set up test environment"""
        # Clear any existing data
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)
    
    def test_create_scene_with_simple_channels(self):
        """Test creating scene with simple channel IDs (backward compatibility)"""
        scene_data = {
            "name": "Test Scene Simple",
            "channels": ["photo_frame", "weather"]
        }
        
        response = client.post("/api/scenes", json=scene_data)
        assert response.status_code == 200
        
        # Verify scene was created
        scene_response = client.get("/api/scenes/test-scene-simple")
        assert scene_response.status_code == 200
        
        scene = scene_response.json()
        assert scene["name"] == "Test Scene Simple"
        assert len(scene["channels"]) == 2
        
        # Check channel assignments format
        assert scene["channels"][0]["channel_id"] == "photo_frame"
        assert scene["channels"][0]["subchannel_id"] is None
        assert scene["channels"][1]["channel_id"] == "weather"
        assert scene["channels"][1]["subchannel_id"] is None
    
    def test_create_scene_with_subchannel_assignments(self):
        """Test creating scene with sub-channel assignments"""
        scene_data = {
            "name": "Test Scene With SubChannels",
            "channels": [
                {"channel_id": "photo_frame", "subchannel_id": "family_photos"},
                {"channel_id": "weather", "subchannel_id": "outdoor_location"}
            ]
        }
        
        response = client.post("/api/scenes", json=scene_data)
        assert response.status_code == 200
        
        # Verify scene was created
        scene_response = client.get("/api/scenes/test-scene-with-subchannels")
        assert scene_response.status_code == 200
        
        scene = scene_response.json()
        assert scene["name"] == "Test Scene With SubChannels"
        assert len(scene["channels"]) == 2
        
        # Check sub-channel assignments
        assert scene["channels"][0]["channel_id"] == "photo_frame"
        assert scene["channels"][0]["subchannel_id"] == "family_photos"
        assert scene["channels"][1]["channel_id"] == "weather"
        assert scene["channels"][1]["subchannel_id"] == "outdoor_location"
    
    def test_create_scene_mixed_format(self):
        """Test creating scene with mixed channel and sub-channel assignments"""
        scene_data = {
            "name": "Test Scene Mixed",
            "channels": [
                {"channel_id": "photo_frame", "subchannel_id": "vacation_photos"},
                {"channel_id": "weather"}  # No sub-channel specified
            ]
        }
        
        response = client.post("/api/scenes", json=scene_data)
        assert response.status_code == 200
        
        scene_response = client.get("/api/scenes/test-scene-mixed")
        assert scene_response.status_code == 200
        
        scene = scene_response.json()
        assert len(scene["channels"]) == 2
        
        # First channel has sub-channel
        assert scene["channels"][0]["channel_id"] == "photo_frame"
        assert scene["channels"][0]["subchannel_id"] == "vacation_photos"
        
        # Second channel has no sub-channel
        assert scene["channels"][1]["channel_id"] == "weather"
        assert scene["channels"][1]["subchannel_id"] is None
    
    def test_update_scene_add_subchannels(self):
        """Test updating existing scene to add sub-channel assignments"""
        # Create scene with simple channels
        scene_data = {
            "name": "Test Scene Update",
            "channels": ["photo_frame"]
        }
        
        response = client.post("/api/scenes", json=scene_data)
        assert response.status_code == 200
        
        # Update scene to add sub-channel
        updated_data = {
            "name": "Test Scene Update",
            "channels": [
                {"channel_id": "photo_frame", "subchannel_id": "family_gallery"}
            ]
        }
        
        update_response = client.put("/api/scenes/test-scene-update", json=updated_data)
        assert update_response.status_code == 200
        
        # Verify update
        scene_response = client.get("/api/scenes/test-scene-update")
        scene = scene_response.json()
        
        assert scene["channels"][0]["channel_id"] == "photo_frame"
        assert scene["channels"][0]["subchannel_id"] == "family_gallery"
    
    def test_list_scenes_backward_compatibility(self):
        """Test listing scenes maintains backward compatibility"""
        # Create scenes with different formats
        scenes_data = [
            {
                "name": "Old Format Scene",
                "channels": ["photo_frame", "weather"]
            },
            {
                "name": "New Format Scene", 
                "channels": [
                    {"channel_id": "photo_frame", "subchannel_id": "gallery1"},
                    {"channel_id": "weather"}
                ]
            }
        ]
        
        # Create scenes
        for scene_data in scenes_data:
            response = client.post("/api/scenes", json=scene_data)
            assert response.status_code == 200
        
        # List all scenes
        response = client.get("/api/scenes")
        assert response.status_code == 200
        
        scenes_list = response.json()
        assert "results" in scenes_list
        assert len(scenes_list["results"]) == 2
        
        # Check each scene has proper channel assignment format
        for scene in scenes_list["results"]:
            assert "channels" in scene
            for channel in scene["channels"]:
                assert "channel_id" in channel
                assert "subchannel_id" in channel  # May be None
    
    def test_scene_validation_errors(self):
        """Test scene validation with invalid data"""
        # Test empty channels
        invalid_data = {
            "name": "Invalid Scene",
            "channels": []
        }
        
        response = client.post("/api/scenes", json=invalid_data)
        # Should still create scene but with empty channels
        assert response.status_code == 200
        
        # Test malformed channel assignment
        invalid_data = {
            "name": "Invalid Scene 2",
            "channels": [
                {"invalid_field": "photo_frame"}  # Missing channel_id
            ]
        }
        
        response = client.post("/api/scenes", json=invalid_data)
        assert response.status_code == 422  # Validation error
    
    def test_scene_activation_with_subchannels(self):
        """Test scene activation with sub-channel assignments"""
        # Create scene with sub-channels
        scene_data = {
            "name": "Activation Test Scene",
            "channels": [
                {"channel_id": "photo_frame", "subchannel_id": "test_gallery"}
            ]
        }
        
        response = client.post("/api/scenes", json=scene_data)
        assert response.status_code == 200
        
        # Activate scene
        activation_response = client.post("/api/scenes/activation-test-scene/activate")
        assert activation_response.status_code == 200
        
        # Verify scene is active
        scene_response = client.get("/api/scenes/activation-test-scene")
        scene = scene_response.json()
        assert scene["isActive"] is True


class TestBackwardCompatibility:
    """Test backward compatibility with existing scene data"""
    
    def setup_method(self):
        """Set up test environment"""
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)
    
    def test_read_legacy_scene_data(self):
        """Test reading existing scenes with old channel format"""
        # This would simulate reading a scene that was created before sub-channel support
        # For now, we'll test the conversion logic by mocking the database data
        pass  # Implementation would require direct database manipulation
    
    def test_migration_from_old_format(self):
        """Test that old format scenes work without modification"""
        # Create scene using old API format
        old_format_data = {
            "name": "Legacy Scene",
            "channels": ["photo_frame", "weather", "news"]
        }
        
        response = client.post("/api/scenes", json=old_format_data)
        assert response.status_code == 200
        
        # Retrieve and verify conversion to new format
        scene_response = client.get("/api/scenes/legacy-scene")
        scene = scene_response.json()
        
        assert len(scene["channels"]) == 3
        for i, expected_channel in enumerate(["photo_frame", "weather", "news"]):
            assert scene["channels"][i]["channel_id"] == expected_channel
            assert scene["channels"][i]["subchannel_id"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
