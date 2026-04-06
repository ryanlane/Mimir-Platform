"""
Channel Manager
Infrastructure component for channel discovery and management
"""
import json
import hashlib
import base64
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.config import settings


class ChannelManager:
    """Manages channel discovery, loading, and lifecycle"""
    
    def __init__(self, channels_dir: str = None):
        self.channels_dir = Path(channels_dir or settings.channels_directory)
        self.loaded_channels = {}
        self.static_mounts = {}
    
    def compute_sri_hash(self, file_path: Path) -> str:
        """Compute SHA-384 hash for Subresource Integrity"""
        if not file_path.exists():
            return ""
        
        hasher = hashlib.sha384()
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
        
        hash_bytes = hasher.digest()
        hash_b64 = base64.b64encode(hash_bytes).decode('ascii')
        return f"sha384-{hash_b64}"
    
    def load_channel_config(self, channel_path: Path) -> Optional[Dict[str, Any]]:
        """Load and validate channel config.json"""
        config_file = channel_path / "config.json"
        if not config_file.exists():
            return None
            
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            # Validate required fields
            required_fields = ['name', 'description', 'version']
            for field in required_fields:
                if field not in config:
                    print(f"Warning: Channel {channel_path.name} missing required field: {field}")
                    return None
                    
            # Set default schema version if not specified
            if 'schemaVersion' not in config:
                config['schemaVersion'] = '2.0'
                
            # Add computed integrity hashes for UI files
            if 'ui' in config:
                for ui_entry in config['ui']:
                    if 'moduleUrl' in ui_entry:
                        # Extract file path from URL
                        module_path = channel_path / "ui" / Path(ui_entry['moduleUrl']).name
                        if module_path.exists():
                            if 'integrity' not in ui_entry:
                                ui_entry['integrity'] = {}
                            ui_entry['integrity']['module'] = self.compute_sri_hash(module_path)
            
            return config
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading channel config for {channel_path.name}: {e}")
            return None
    
    def discover_channels(self) -> List[Dict[str, Any]]:
        """Discover all available channels in the channels directory"""
        discovered_channels = []
        
        if not self.channels_dir.exists():
            print(f"Channels directory {self.channels_dir} does not exist")
            return discovered_channels
        
        for channel_dir in self.channels_dir.iterdir():
            if not channel_dir.is_dir():
                continue
            
            config = self.load_channel_config(channel_dir)
            if config:
                config['id'] = channel_dir.name
                config['channel_dir'] = str(channel_dir)
                discovered_channels.append(config)
        
        return discovered_channels
    
    def get_channel_by_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel configuration by ID"""
        channel_path = self.channels_dir / channel_id
        if not channel_path.exists():
            return None
        
        return self.load_channel_config(channel_path)
    
    def reload_channel(self, channel_id: str) -> bool:
        """Reload a specific channel"""
        if channel_id in self.loaded_channels:
            del self.loaded_channels[channel_id]
        
        channel_path = self.channels_dir / channel_id
        config = self.load_channel_config(channel_path)
        
        if config:
            self.loaded_channels[channel_id] = config
            return True
        
        return False
    
    def reload_all_channels(self) -> int:
        """Reload all channels and return count of successfully loaded channels"""
        self.loaded_channels.clear()
        discovered = self.discover_channels()
        
        for channel in discovered:
            self.loaded_channels[channel['id']] = channel
        
        return len(discovered)
    
    def get_channel_static_path(self, channel_id: str, file_path: str) -> Optional[Path]:
        """Get the full path to a channel's static file"""
        channel_path = self.channels_dir / channel_id
        if not channel_path.exists():
            return None
        
        full_path = channel_path / file_path
        
        # Security check: ensure path is within channel directory
        try:
            full_path.resolve().relative_to(channel_path.resolve())
            return full_path if full_path.exists() else None
        except ValueError:
            # Path is outside channel directory
            return None
    
    def validate_channel_structure(self, channel_id: str) -> Dict[str, Any]:
        """Validate channel directory structure and return validation results"""
        channel_path = self.channels_dir / channel_id
        validation = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "files_found": []
        }
        
        if not channel_path.exists():
            validation["errors"].append("Channel directory does not exist")
            return validation
        
        # Check for required files
        config_file = channel_path / "config.json"
        if not config_file.exists():
            validation["errors"].append("config.json not found")
        else:
            validation["files_found"].append("config.json")
        
        # Check for channel implementation
        channel_py = channel_path / "channel.py"
        if not channel_py.exists():
            validation["warnings"].append("channel.py not found")
        else:
            validation["files_found"].append("channel.py")
        
        # Check for UI directory if configured
        config = self.load_channel_config(channel_path)
        if config and 'ui' in config:
            ui_dir = channel_path / "ui"
            if not ui_dir.exists():
                validation["warnings"].append("UI directory not found despite UI configuration")
            else:
                validation["files_found"].append("ui/")
        
        validation["valid"] = len(validation["errors"]) == 0
        return validation
