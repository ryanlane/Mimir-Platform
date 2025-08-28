"""
Channel Discovery Service
Handles dynamic channel loading, static file mounting, and SRI hash computation
"""
import json
import hashlib
import base64
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

# Subclass to disable caching for JS files
class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.endswith('.js'):
            response.headers['Cache-Control'] = 'no-store'
        return response

from app.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class ChannelDiscoveryService:
    """Service for discovering, loading, and managing channels dynamically"""
    
    def __init__(self, channels_dir: Optional[str] = None):
        self.channels_dir = Path(channels_dir or settings.channels_directory)
        self.loaded_channels: Dict[str, Dict[str, Any]] = {}
        self.static_mounts: Dict[str, str] = {}
        
    def compute_sri_hash(self, file_path: Path) -> str:
        """Compute SHA-384 hash for Subresource Integrity"""
        if not file_path.exists():
            logger.warning(f"File not found for SRI hash: {file_path}")
            return ""
        
        try:
            hasher = hashlib.sha384()
            with open(file_path, 'rb') as f:
                hasher.update(f.read())
            
            hash_bytes = hasher.digest()
            hash_b64 = base64.b64encode(hash_bytes).decode('ascii')
            return f"sha384-{hash_b64}"
        except Exception as e:
            logger.error(f"Error computing SRI hash for {file_path}: {e}")
            return ""
    
    def load_channel_config(self, channel_path: Path) -> Optional[Dict[str, Any]]:
        """Load and validate channel config.json"""
        config_file = channel_path / "config.json"
        if not config_file.exists():
            logger.warning(f"No config.json found for channel: {channel_path.name} (path: {channel_path})")
            return None
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Validate required fields
            required_fields = ['name', 'description', 'version']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                logger.warning(f"Channel {channel_path.name} missing required fields: {missing_fields}")
                return None
                    
            # Set default schema version if not specified
            if 'schemaVersion' not in config:
                config['schemaVersion'] = '2.1'
                
            # Add computed integrity hashes for UI files
            if 'ui' in config:
                self._add_integrity_hashes(config, channel_path)
                            
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config.json for {channel_path.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading channel {channel_path.name}: {e}")
            return None
    
    def _add_integrity_hashes(self, config: Dict[str, Any], channel_path: Path):
        """Add SRI integrity hashes to UI configuration"""
        for ui_entry in config['ui']:
            # Add module integrity hash
            if 'moduleUrl' in ui_entry:
                module_path = channel_path / "ui" / Path(ui_entry['moduleUrl']).name
                if module_path.exists():
                    if 'integrity' not in ui_entry:
                        ui_entry['integrity'] = {}
                    ui_entry['integrity']['module'] = self.compute_sri_hash(module_path)
            
            # Add style integrity hash        
            if 'styleUrl' in ui_entry:
                style_path = channel_path / "ui" / Path(ui_entry['styleUrl']).name  
                if style_path.exists():
                    if 'integrity' not in ui_entry:
                        ui_entry['integrity'] = {}
                    ui_entry['integrity']['style'] = self.compute_sri_hash(style_path)
    
    def load_channel_class(self, channel_path: Path) -> Optional[Any]:
        """Dynamically load channel implementation class"""
        channel_file = channel_path / "channel.py"
        if not channel_file.exists():
            logger.warning(f"No channel.py found for {channel_path.name}")
            return None
            
        try:
            # Create module spec
            spec = importlib.util.spec_from_file_location(
                f"channel_{channel_path.name}", 
                channel_file
            )
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create module spec for {channel_path.name}")
                return None
                
            # Import the module
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"channel_{channel_path.name}"] = module
            spec.loader.exec_module(module)
            
            # Look for channel class in multiple ways
            channel_class = self._find_channel_class(module, channel_path.name)
            
            if channel_class:
                try:
                    instance = channel_class(str(channel_path))
                    logger.info(f"Successfully instantiated channel class for {channel_path.name}")
                    return instance
                except Exception as e:
                    logger.error(f"Failed to instantiate channel class for {channel_path.name}: {e}")
                    return None
            else:
                self._log_available_classes(module, channel_path.name)
                return None
                
        except Exception as e:
            logger.error(f"Error loading channel class for {channel_path.name}: {e}")
            return None
    
    def _find_channel_class(self, module: Any, channel_name: str) -> Optional[type]:
        """Find the appropriate channel class in the module"""
        # 1. Look for ChannelClass export (preferred)
        if hasattr(module, 'ChannelClass'):
            logger.info(f"Found ChannelClass in {channel_name}")
            return getattr(module, 'ChannelClass')
            
        # 2. Look for class with "Channel" in the name
        class_name = f'{channel_name.title().replace("_", "")}Channel'
        if hasattr(module, class_name):
            logger.info(f"Found {class_name} in {channel_name}")
            return getattr(module, class_name)
            
        # 3. Look for any class ending with "Channel"
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                attr_name.endswith('Channel') and 
                attr.__module__ == module.__name__):
                logger.info(f"Found channel class {attr_name} in {channel_name}")
                return attr
                
        return None
    
    def _log_available_classes(self, module: Any, channel_name: str):
        """Log available classes for debugging"""
        classes = [name for name in dir(module) 
                  if isinstance(getattr(module, name), type) 
                  and getattr(module, name).__module__ == module.__name__]
        logger.error(f"No suitable channel class found in {channel_name}. Available classes: {classes}")
    
    def setup_static_mounts(self, app: FastAPI, channel_id: str, channel_path: Path):
        """Setup static file serving for channel UI and assets"""
        try:
            # Mount UI directory if it exists (no-cache for JS)
            ui_path = channel_path / "ui"
            if ui_path.exists() and ui_path.is_dir():
                mount_path = f"/api/channels/{channel_id}/ui"
                app.mount(mount_path, NoCacheStaticFiles(directory=str(ui_path)), name=f"{channel_id}-ui")
                self.static_mounts[f"{channel_id}-ui"] = mount_path
                logger.info(f"Mounted UI static files (no-cache for JS): {mount_path} -> {ui_path}")

            # Mount assets directory if it exists (default caching)
            assets_path = channel_path / "assets"
            if assets_path.exists() and assets_path.is_dir():
                mount_path = f"/api/channels/{channel_id}/assets"
                app.mount(mount_path, StaticFiles(directory=str(assets_path)), name=f"{channel_id}-assets")
                self.static_mounts[f"{channel_id}-assets"] = mount_path
                logger.info(f"Mounted assets static files: {mount_path} -> {assets_path}")

        except Exception as e:
            logger.error(f"Error setting up static mounts for {channel_id}: {e}")
    
    def discover_channels(self, app: FastAPI) -> List[Dict[str, Any]]:
        """Discover and load all channels from filesystem"""
        if not self.channels_dir.exists():
            self.channels_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created channels directory: {self.channels_dir}")
            return []
        
        discovered_channels = []
        
        logger.info(f"Scanning channels directory: {self.channels_dir}")
        
        for channel_path in self.channels_dir.iterdir():
            # Skip non-directories immediately
            if not channel_path.is_dir():
                logger.debug(f"Skipping non-directory: {channel_path.name}")
                continue
            
            # Skip hidden directories (starting with .)
            if channel_path.name.startswith('.'):
                logger.debug(f"Skipping hidden directory: {channel_path.name}")
                continue
            
            # Skip common subdirectories that aren't channels
            skip_dirs = {'assets', 'data', 'static', 'uploads', 'thumbnails', 'cache', 'temp', 'logs'}
            if channel_path.name.lower() in skip_dirs:
                logger.debug(f"Skipping common subdirectory: {channel_path.name}")
                continue
            
            logger.debug(f"Examining potential channel directory: {channel_path.name} (full path: {channel_path})")
                
            # Load config to get the channel ID
            config = self.load_channel_config(channel_path)
            if not config:
                # This will log its own warning, so just continue
                continue
                
            # Use ID from config if present, otherwise fall back to directory name
            channel_id = config.get('id', channel_path.name)
            logger.info(f"Discovering channel: {channel_id} (directory: {channel_path.name})")
            
            # Load channel class
            channel_instance = self.load_channel_class(channel_path)
            
            # Setup static file mounts
            self.setup_static_mounts(app, channel_id, channel_path)
            
            # Store channel data
            channel_data = {
                'id': channel_id,
                'path': channel_path,
                'config': config,
                'instance': channel_instance,
                'directory_name': channel_path.name
            }
            
            self.loaded_channels[channel_id] = channel_data
            discovered_channels.append(channel_data)
            
            logger.info(f"Successfully loaded channel: {channel_id}")
        
        logger.info(f"Channel discovery complete. Loaded {len(discovered_channels)} channels")
        return discovered_channels
    
    def get_channel_instance(self, channel_id: str) -> Optional[Any]:
        """Get channel instance by ID"""
        channel_data = self.loaded_channels.get(channel_id)
        return channel_data['instance'] if channel_data else None
    
    def get_channel_config(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel configuration by ID"""
        channel_data = self.loaded_channels.get(channel_id)
        return channel_data['config'] if channel_data else None
    
    def get_all_channels(self) -> List[Dict[str, Any]]:
        """Get all loaded channels"""
        return list(self.loaded_channels.values())
    
    def get_channel_settings(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel settings configuration and current values"""
        channel_data = self.loaded_channels.get(channel_id)
        if not channel_data:
            return None
            
        config = channel_data['config']
        settings_config = config.get('settings', {})
        
        # If settings has 'schema' and 'defaults' structure (like photo_frame)
        if 'schema' in settings_config and 'defaults' in settings_config:
            # This is an advanced/schema-based settings structure
            return {
                'schema': settings_config['schema'],
                'current': settings_config['defaults'],  # For now, use defaults as current
                'settingsType': config.get('settingsType', config.get('settings_type', 'advanced'))
            }
        
        # If settings are directly defined (like example_channel and weather_channel)
        elif settings_config:
            # Convert settings definition to a proper schema format
            schema_properties = {}
            current_values = {}
            
            for key, setting_def in settings_config.items():
                if isinstance(setting_def, dict):
                    schema_properties[key] = {
                        'type': setting_def.get('type', 'string'),
                        'title': setting_def.get('label', key.replace('_', ' ').title()),
                        'description': setting_def.get('description', ''),
                        'default': setting_def.get('default')
                    }
                    
                    # Add enum options if present
                    if 'enum' in setting_def:
                        schema_properties[key]['enum'] = setting_def['enum']
                    elif 'options' in setting_def:
                        schema_properties[key]['enum'] = setting_def['options']
                    
                    # Add validation constraints
                    if 'minimum' in setting_def:
                        schema_properties[key]['minimum'] = setting_def['minimum']
                    if 'required' in setting_def and setting_def['required']:
                        schema_properties[key]['required'] = True
                    
                    # Set current value to default for now
                    current_values[key] = setting_def.get('default')
            
            return {
                'schema': {
                    'type': 'object',
                    'properties': schema_properties
                },
                'current': current_values,
                'settingsType': config.get('settingsType', config.get('settings_type', 'simple'))
            }
        
        # No settings defined
        return {
            'schema': {'type': 'object', 'properties': {}},
            'current': {},
            'settingsType': config.get('settingsType', config.get('settings_type', 'simple'))
        }
    
    def update_channel_settings(self, channel_id: str, settings: Dict[str, Any]) -> bool:
        """Update channel settings (for now, just validate they exist)"""
        channel_data = self.loaded_channels.get(channel_id)
        if not channel_data:
            return False
        
        # For now, we'll just return True to indicate the channel exists
        # In a full implementation, you might want to:
        # 1. Store settings in a separate file (e.g., channel_settings.json)
        # 2. Pass settings to the channel instance
        # 3. Persist to a lightweight storage mechanism
        
        logger.info(f"Settings update requested for channel {channel_id}: {settings}")
        return True

    def get_channels_manifest(self) -> Dict[str, Any]:
        """Get manifest of all channels for frontend consumption"""
        channels_data = []
        
        for channel_data in self.loaded_channels.values():
            config = channel_data['config']
            
            # Determine settings type based on structure
            settings_config = config.get('settings', {})
            if 'schema' in settings_config and 'defaults' in settings_config:
                # Advanced schema-based settings
                settings_type = config.get('settingsType', config.get('settings_type', 'advanced'))
            else:
                # Simple or no settings
                settings_type = config.get('settingsType', config.get('settings_type', 'simple'))
            
            manifest_entry = {
                'id': channel_data['id'],
                'name': config['name'],
                'description': config['description'],
                'version': config['version'],
                'schemaVersion': config.get('schemaVersion', '2.1'),
                'ui': config.get('ui', []),
                'permissions': config.get('permissions', {}),
                'assets': config.get('assets', {}),
                'settingsType': settings_type
            }
            channels_data.append(manifest_entry)
        
        return {
            'channels': channels_data,
            'totalChannels': len(channels_data),
            'lastUpdated': None  # Could add timestamp if needed
        }


# Global service instance
channel_discovery_service = ChannelDiscoveryService()
