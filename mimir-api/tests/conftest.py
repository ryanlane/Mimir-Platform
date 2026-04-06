"""
Test Configuration and Base Fixtures
Provides common test setup, database fixtures, and utilities
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import create_app
from app.db.base import Base
from app.db.models import Channel, Scene, Overlay, DisplayClient, DisplayStatus
from app.core.config import Settings


class TestSettings(Settings):
    """Test-specific settings"""
    database_url: str = "sqlite:///./test.db"
    channels_dir: str = "test_channels"
    debug: bool = True
    redis_enabled: bool = False
    distribution_enabled: bool = False
    
    class Config:
        env_file = None


@pytest.fixture(scope="session")
def test_settings():
    """Test settings fixture"""
    return TestSettings()


@pytest.fixture(scope="session")
def test_db_engine(test_settings):
    """Create test database engine"""
    engine = create_engine(
        test_settings.database_url,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """Create test database session"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = TestingSessionLocal()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def test_channels_dir():
    """Create temporary channels directory"""
    temp_dir = tempfile.mkdtemp(prefix="test_channels_")
    channels_path = Path(temp_dir)
    
    yield channels_path
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def app_with_test_db(test_settings, test_channels_dir, monkeypatch):
    """Create FastAPI app with test database"""
    # Patch settings
    monkeypatch.setattr("app.core.config.settings", test_settings)
    
    # Create app
    app = create_app()
    
    yield app


@pytest.fixture(scope="function")
def client(app_with_test_db):
    """Create test client"""
    with TestClient(app_with_test_db) as client:
        yield client


@pytest.fixture(scope="function")
def sample_channel_data():
    """Sample channel data for testing"""
    return {
        "id": "test-channel",
        "name": "Test Channel",
        "description": "A test channel for unit testing",
        "version": "1.0.0",
        "schemaVersion": "2.1",
        "settingsType": "simple",
        "permissions": {"read": True, "write": True},
        "ui": [
            {
                "type": "settings",
                "moduleUrl": "./settings.js",
                "styleUrl": "./settings.css",
                "integrity": {
                    "module": "sha384-test",
                    "style": "sha384-test"
                }
            }
        ],
        "assets": {},
        "currentSettings": {}
    }


@pytest.fixture(scope="function")
def sample_scene_data():
    """Sample scene data for testing"""
    return {
        "id": "test-scene",
        "name": "Test Scene",
        "channels": [
            {
                "id": "test-channel",
                "settings": {"background": "blue"}
            }
        ],
        "image_fit": "cover",
        "overlay": None,
        "schedule": None,
        "theme": "default",
        "is_active": False,
        "distribution_mode": "MIRROR"
    }


@pytest.fixture(scope="function")
def sample_overlay_data():
    """Sample overlay data for testing"""
    return {
        "id": "test-overlay",
        "name": "Test Overlay",
        "description": "A test overlay",
        "overlay_type": "text",
        "config": {
            "text": "Test Text",
            "position": "top-right",
            "color": "#ffffff"
        }
    }


@pytest.fixture(scope="function")
def sample_display_data():
    """Sample display client data for testing"""
    return {
        "id": "test-display",
        "name": "Test Display",
        "location": "Test Location",
        "description": "A test display client",
        "hostname": "test-host",
        "webhook_port": 8080,
        "client_version": "1.0.0",
        "capabilities": {
            "resolution": [800, 600],
            "supported_formats": ["jpg", "png"],
            "orientation": "landscape",
            "refresh_rate_hz": 60.0,
            "redis_distribution": False,
            "content_claiming": True
        }
    }


@pytest.fixture(scope="function")
def db_with_sample_data(test_db_session, sample_channel_data, sample_scene_data, 
                       sample_overlay_data, sample_display_data):
    """Database session with sample data"""
    # Create channel
    channel = Channel(
        id=sample_channel_data["id"],
        name=sample_channel_data["name"],
        description=sample_channel_data["description"],
        version=sample_channel_data["version"],
        schema_version=sample_channel_data["schemaVersion"],
        settings_type=sample_channel_data["settingsType"],
        permissions=sample_channel_data["permissions"],
        ui_config=sample_channel_data["ui"],
        current_settings=sample_channel_data["currentSettings"]
    )
    test_db_session.add(channel)
    
    # Create scene
    scene = Scene(
        id=sample_scene_data["id"],
        name=sample_scene_data["name"],
        channels=sample_scene_data["channels"],
        image_fit=sample_scene_data["image_fit"],
        is_active=sample_scene_data["is_active"],
        distribution_mode=sample_scene_data["distribution_mode"]
    )
    test_db_session.add(scene)
    
    # Create overlay
    overlay = Overlay(
        id=sample_overlay_data["id"],
        name=sample_overlay_data["name"],
        description=sample_overlay_data["description"],
        overlay_type=sample_overlay_data["overlay_type"],
        config=sample_overlay_data["config"]
    )
    test_db_session.add(overlay)
    
    # Create display client
    display = DisplayClient(
        id=sample_display_data["id"],
        name=sample_display_data["name"],
        location=sample_display_data["location"],
        description=sample_display_data["description"],
        hostname=sample_display_data["hostname"],
        webhook_port=sample_display_data["webhook_port"],
        client_version=sample_display_data["client_version"],
        width=sample_display_data["capabilities"]["resolution"][0],
        height=sample_display_data["capabilities"]["resolution"][1],
        orientation=sample_display_data["capabilities"]["orientation"],
        redis_distribution=sample_display_data["capabilities"]["redis_distribution"],
        content_claiming=sample_display_data["capabilities"]["content_claiming"]
    )
    test_db_session.add(display)
    
    test_db_session.commit()
    
    yield test_db_session


@pytest.fixture(scope="function")
def mock_channel_directory(test_channels_dir, sample_channel_data):
    """Create mock channel directory structure"""
    channel_dir = test_channels_dir / sample_channel_data["id"]
    channel_dir.mkdir()
    
    # Create config.json
    config_file = channel_dir / "config.json"
    import json
    with open(config_file, 'w') as f:
        json.dump(sample_channel_data, f, indent=2)
    
    # Create UI directory with mock files
    ui_dir = channel_dir / "ui"
    ui_dir.mkdir()
    
    settings_js = ui_dir / "settings.js"
    settings_js.write_text("// Mock settings.js")
    
    settings_css = ui_dir / "settings.css"
    settings_css.write_text("/* Mock settings.css */")
    
    # Create assets directory
    assets_dir = channel_dir / "assets"
    assets_dir.mkdir()
    
    # Create mock channel.py
    channel_py = channel_dir / "channel.py"
    channel_py.write_text("""
class TestChannel:
    def __init__(self, channel_path):
        self.channel_path = channel_path
        
    def get_content(self):
        return {"status": "ok"}

ChannelClass = TestChannel
""")
    
    yield channel_dir


@pytest.fixture(scope="function")
def mock_websocket():
    """Mock WebSocket for testing"""
    class MockWebSocket:
        def __init__(self):
            self.messages_sent = []
            self.accepted = False
            self.closed = False
        
        async def accept(self):
            self.accepted = True
        
        async def send_text(self, message: str):
            self.messages_sent.append(message)
        
        async def close(self):
            self.closed = True
    
    return MockWebSocket()


# Test utilities
def assert_valid_response(response, expected_status: int = 200):
    """Assert response is valid with expected status"""
    assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"


def assert_pagination_response(response_data: Dict[str, Any], expected_total: int = None):
    """Assert response has proper pagination structure"""
    assert "total" in response_data
    assert "limit" in response_data
    assert "offset" in response_data
    
    if expected_total is not None:
        assert response_data["total"] == expected_total


def create_test_content_file(content_dir: Path, filename: str, content: str = "test content") -> Path:
    """Create a test content file"""
    content_dir.mkdir(parents=True, exist_ok=True)
    file_path = content_dir / filename
    file_path.write_text(content)
    return file_path
