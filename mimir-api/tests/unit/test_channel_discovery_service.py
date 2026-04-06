"""
Unit Tests for ChannelDiscoveryService
Tests channel discovery, configuration loading, and SRI hash computation
"""
import pytest
import json
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from app.services.channel_discovery import ChannelDiscoveryService
from app.core.config import Settings


@pytest.mark.unit
@pytest.mark.channels
class TestChannelDiscoveryService:
    """Test ChannelDiscoveryService functionality"""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing"""
        settings = Mock(spec=Settings)
        settings.channels_dir = "test_channels"
        settings.debug = True
        return settings
    
    @pytest.fixture
    def channel_service(self, mock_settings):
        """Create ChannelDiscoveryService instance"""
        return ChannelDiscoveryService(settings=mock_settings)
    
    def test_compute_sri_hash(self, channel_service):
        """Test SRI hash computation"""
        content = "test content"
        expected_hash = f"sha384-{hashlib.sha384(content.encode()).digest().hex()}"
        
        result = channel_service.compute_sri_hash(content)
        
        assert result == expected_hash
    
    def test_compute_sri_hash_empty_content(self, channel_service):
        """Test SRI hash computation with empty content"""
        content = ""
        expected_hash = f"sha384-{hashlib.sha384(content.encode()).digest().hex()}"
        
        result = channel_service.compute_sri_hash(content)
        
        assert result == expected_hash
    
    def test_load_channel_config_valid(self, channel_service, mock_channel_directory):
        """Test loading valid channel configuration"""
        config_path = mock_channel_directory / "config.json"
        
        result = channel_service.load_channel_config(config_path)
        
        assert result is not None
        assert result["id"] == "test-channel"
        assert result["name"] == "Test Channel"
        assert "ui" in result
    
    def test_load_channel_config_missing_file(self, channel_service, tmp_path):
        """Test loading non-existent configuration file"""
        config_path = tmp_path / "missing.json"
        
        result = channel_service.load_channel_config(config_path)
        
        assert result is None
    
    def test_load_channel_config_invalid_json(self, channel_service, tmp_path):
        """Test loading invalid JSON configuration"""
        config_path = tmp_path / "invalid.json"
        config_path.write_text("invalid json content")
        
        result = channel_service.load_channel_config(config_path)
        
        assert result is None
    
    def test_validate_channel_config_valid(self, channel_service, sample_channel_data):
        """Test validation of valid channel configuration"""
        result = channel_service.validate_channel_config(sample_channel_data)
        
        assert result is True
    
    def test_validate_channel_config_missing_required_fields(self, channel_service):
        """Test validation with missing required fields"""
        invalid_config = {"name": "Test Channel"}
        
        result = channel_service.validate_channel_config(invalid_config)
        
        assert result is False
    
    def test_validate_channel_config_invalid_schema_version(self, channel_service, sample_channel_data):
        """Test validation with invalid schema version"""
        sample_channel_data["schemaVersion"] = "1.0"  # Unsupported version
        
        result = channel_service.validate_channel_config(sample_channel_data)
        
        assert result is False
    
    def test_validate_channel_config_invalid_ui_structure(self, channel_service, sample_channel_data):
        """Test validation with invalid UI structure"""
        sample_channel_data["ui"] = [{"type": "invalid"}]  # Missing required fields
        
        result = channel_service.validate_channel_config(sample_channel_data)
        
        assert result is False
    
    @patch('pathlib.Path.exists')
    def test_discover_channels_no_directory(self, mock_exists, channel_service):
        """Test channel discovery when channels directory doesn't exist"""
        mock_exists.return_value = False
        
        result = channel_service.discover_channels()
        
        assert result == []
    
    @patch('pathlib.Path.iterdir')
    @patch('pathlib.Path.exists')
    def test_discover_channels_empty_directory(self, mock_exists, mock_iterdir, channel_service):
        """Test channel discovery in empty directory"""
        mock_exists.return_value = True
        mock_iterdir.return_value = []
        
        result = channel_service.discover_channels()
        
        assert result == []
    
    def test_discover_channels_with_valid_channel(self, channel_service, mock_channel_directory, 
                                                 sample_channel_data, monkeypatch):
        """Test discovering channels with valid configuration"""
        # Mock the channels directory path
        channels_path = mock_channel_directory.parent
        monkeypatch.setattr(channel_service.settings, 'channels_dir', str(channels_path))
        
        with patch.object(channel_service, 'load_channel_config') as mock_load:
            mock_load.return_value = sample_channel_data
            with patch.object(channel_service, 'validate_channel_config') as mock_validate:
                mock_validate.return_value = True
                with patch.object(channel_service, 'process_channel_ui') as mock_process:
                    mock_process.return_value = sample_channel_data["ui"]
                    
                    result = channel_service.discover_channels()
                    
                    assert len(result) == 1
                    assert result[0]["id"] == "test-channel"
    
    def test_discover_channels_with_invalid_channel(self, channel_service, mock_channel_directory, 
                                                   sample_channel_data, monkeypatch):
        """Test discovering channels with invalid configuration"""
        # Mock the channels directory path
        channels_path = mock_channel_directory.parent
        monkeypatch.setattr(channel_service.settings, 'channels_dir', str(channels_path))
        
        with patch.object(channel_service, 'load_channel_config') as mock_load:
            mock_load.return_value = sample_channel_data
            with patch.object(channel_service, 'validate_channel_config') as mock_validate:
                mock_validate.return_value = False
                
                result = channel_service.discover_channels()
                
                assert result == []
    
    def test_process_channel_ui_with_files(self, channel_service, mock_channel_directory):
        """Test processing UI configuration with existing files"""
        ui_config = [
            {
                "type": "settings",
                "moduleUrl": "./settings.js",
                "styleUrl": "./settings.css"
            }
        ]
        
        result = channel_service.process_channel_ui(ui_config, mock_channel_directory)
        
        assert len(result) == 1
        assert "integrity" in result[0]
        assert "module" in result[0]["integrity"]
        assert "style" in result[0]["integrity"]
    
    def test_process_channel_ui_missing_files(self, channel_service, tmp_path):
        """Test processing UI configuration with missing files"""
        ui_config = [
            {
                "type": "settings",
                "moduleUrl": "./missing.js",
                "styleUrl": "./missing.css"
            }
        ]
        
        result = channel_service.process_channel_ui(ui_config, tmp_path)
        
        assert len(result) == 1
        assert "integrity" not in result[0] or result[0]["integrity"] == {}
    
    def test_process_channel_ui_no_urls(self, channel_service, tmp_path):
        """Test processing UI configuration without URLs"""
        ui_config = [
            {
                "type": "settings"
            }
        ]
        
        result = channel_service.process_channel_ui(ui_config, tmp_path)
        
        assert len(result) == 1
        assert "integrity" not in result[0] or result[0]["integrity"] == {}
    
    def test_get_channel_by_id_exists(self, channel_service, sample_channel_data):
        """Test getting channel by ID when it exists"""
        with patch.object(channel_service, 'discover_channels') as mock_discover:
            mock_discover.return_value = [sample_channel_data]
            
            result = channel_service.get_channel_by_id("test-channel")
            
            assert result is not None
            assert result["id"] == "test-channel"
    
    def test_get_channel_by_id_not_exists(self, channel_service):
        """Test getting channel by ID when it doesn't exist"""
        with patch.object(channel_service, 'discover_channels') as mock_discover:
            mock_discover.return_value = []
            
            result = channel_service.get_channel_by_id("missing-channel")
            
            assert result is None
    
    def test_get_all_channels(self, channel_service, sample_channel_data):
        """Test getting all channels"""
        with patch.object(channel_service, 'discover_channels') as mock_discover:
            mock_discover.return_value = [sample_channel_data]
            
            result = channel_service.get_all_channels()
            
            assert len(result) == 1
            assert result[0]["id"] == "test-channel"
    
    def test_refresh_channels(self, channel_service):
        """Test refreshing channel cache"""
        with patch.object(channel_service, 'discover_channels') as mock_discover:
            mock_discover.return_value = []
            
            # Should call discover_channels fresh
            result = channel_service.refresh_channels()
            
            mock_discover.assert_called_once()
            assert result == []
    
    def test_mount_channel_static_files(self, channel_service, mock_channel_directory):
        """Test mounting static files for a channel"""
        app_mock = Mock()
        
        channel_service.mount_channel_static_files(app_mock, "test-channel", mock_channel_directory)
        
        # Should mount static files
        app_mock.mount.assert_called()
    
    @pytest.mark.parametrize("file_content,expected_length", [
        ("short content", 59),  # 'sha384-' + 56 hex chars
        ("a" * 1000, 59),       # Long content, same hash length
        ("", 59),               # Empty content
    ])
    def test_sri_hash_format(self, channel_service, file_content, expected_length):
        """Test SRI hash format consistency"""
        result = channel_service.compute_sri_hash(file_content)
        
        assert result.startswith("sha384-")
        assert len(result) == expected_length
        assert all(c in "0123456789abcdef" for c in result[7:])  # Valid hex
    
    def test_channel_config_schema_versions(self, channel_service):
        """Test supported schema versions"""
        supported_versions = ["2.0", "2.1"]
        
        for version in supported_versions:
            config = {
                "id": "test",
                "name": "Test",
                "schemaVersion": version,
                "settingsType": "simple",
                "ui": []
            }
            
            result = channel_service.validate_channel_config(config)
            assert result is True
        
        # Test unsupported version
        config["schemaVersion"] = "1.0"
        result = channel_service.validate_channel_config(config)
        assert result is False
