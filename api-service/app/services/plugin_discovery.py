"""
Plugin Discovery Service for Embedded Channel Architecture
Handles discovery and loading of channel plugins into the main API process
"""
import json
import sys
import importlib.util
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.logging import get_logger
from app.services.channel_events import channel_event_dispatcher, ChannelUpdateEvent
from app.services.channel_event_consumer import channel_event_consumer

logger = get_logger(__name__)

logger = get_logger(__name__)


@dataclass
class ChannelPlugin:
    """Represents a discovered channel plugin"""
    id: str
    name: str
    description: str
    icon: Optional[str]
    config_path: Path
    plugin_path: Path
    instance: Optional[Any] = None
    last_health_check: Optional[float] = None
    healthy: bool = True  # Embedded plugins are healthy if loaded


class PluginDiscoveryService:
    """Service for discovering and managing embedded channel plugins"""
    
    def __init__(self, channels_dir: Optional[str] = None):
        self.channels_dir = Path(channels_dir or settings.channels_directory)
        self.plugins: Dict[str, ChannelPlugin] = {}
        
    async def discover_plugins(self, app: FastAPI) -> List[ChannelPlugin]:
        """Discover and load channel plugins into the main API"""
        if not self.channels_dir.exists():
            self.channels_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created channels directory: {self.channels_dir}")
            return []
        
        discovered_plugins = []
        logger.info(f"Scanning for channel plugins in: {self.channels_dir}")
        
        for plugin_path in self.channels_dir.iterdir():
            if not plugin_path.is_dir():
                continue
                
            # Skip hidden directories and common non-plugin directories
            if (plugin_path.name.startswith('.') or 
                plugin_path.name.lower() in {'assets', 'data', 'static', 'uploads', 'cache', 'temp', 'logs'}):
                continue
            
            # Look for plugin.json configuration file
            config_file = plugin_path / "plugin.json"
            if not config_file.exists():
                logger.debug(f"No plugin.json found in {plugin_path.name}, trying config.json for backward compatibility")
                # Fallback to config.json for backward compatibility
                config_file = plugin_path / "config.json"
                if not config_file.exists():
                    logger.debug(f"No plugin.json or config.json found in {plugin_path.name}, skipping")
                    continue
            
            try:
                plugin = await self._load_plugin_config(config_file, plugin_path)
                if plugin:
                    # Load the plugin instance
                    await self._load_plugin_instance(plugin, app)
                    
                    discovered_plugins.append(plugin)
                    self.plugins[plugin.id] = plugin
                    logger.info(f"Discovered plugin: {plugin.id} at {plugin.plugin_path}")
                    
            except Exception as e:
                logger.error(f"Error loading plugin from {plugin_path}: {e}")
        
        logger.info(f"Plugin discovery complete. Found {len(discovered_plugins)} plugins")
        return discovered_plugins
    
    async def _load_plugin_config(self, config_file: Path, plugin_path: Path) -> Optional[ChannelPlugin]:
        """Load plugin configuration from plugin.json or config.json"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Handle both plugin.json and config.json formats
            if config_file.name == "plugin.json":
                # New plugin.json format
                required_fields = ['id', 'name', 'description']
                missing_fields = [field for field in required_fields if field not in config]
                
                if missing_fields:
                    logger.warning(f"Plugin {plugin_path.name} missing required fields: {missing_fields}")
                    return None
                
                plugin = ChannelPlugin(
                    id=config['id'],
                    name=config['name'],
                    description=config['description'],
                    icon=config.get('icon'),
                    config_path=config_file,
                    plugin_path=plugin_path
                )
            else:
                # Legacy config.json format
                required_fields = ['name', 'description']
                missing_fields = [field for field in required_fields if field not in config]
                
                if missing_fields:
                    logger.warning(f"Plugin {plugin_path.name} missing required fields: {missing_fields}")
                    return None
                
                # Use directory name or config id
                plugin_id = config.get('id', plugin_path.name)
                
                plugin = ChannelPlugin(
                    id=plugin_id,
                    name=config['name'],
                    description=config['description'],
                    icon=config.get('icon'),
                    config_path=config_file,
                    plugin_path=plugin_path
                )
            
            return plugin
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing {config_file.name} for {plugin_path.name}: {e}")
            return None
    
    async def _load_plugin_instance(self, plugin: ChannelPlugin, app: FastAPI):
        """Load and initialize plugin instance"""
        try:
            # Look for channel.py file
            channel_file = plugin.plugin_path / "channel.py"
            if not channel_file.exists():
                logger.warning(f"No channel.py found for plugin {plugin.id}")
                plugin.healthy = False
                return
            
            # Import the channel module
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin.id.replace('.', '_')}", 
                channel_file
            )
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create module spec for {plugin.id}")
                plugin.healthy = False
                return
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{plugin.id.replace('.', '_')}"] = module
            spec.loader.exec_module(module)
            
            # Find and instantiate the channel class
            channel_class = self._find_channel_class(module, plugin.id)
            if not channel_class:
                logger.error(f"No suitable channel class found for {plugin.id}")
                plugin.healthy = False
                return
            
            logger.info(f"Found channel class for {plugin.id}: {channel_class.__name__} from {channel_class.__module__}")
            
            # Instantiate the channel
            plugin.instance = channel_class(str(plugin.plugin_path))
            
            # Mount plugin router if available
            if hasattr(plugin.instance, 'get_router'):
                router = plugin.instance.get_router()
                if router:
                    mount_path = f"/api/channels/{plugin.id}"
                    app.include_router(router, prefix=mount_path, tags=[f"plugin-{plugin.id}"])
                    logger.info(f"Mounted plugin router: {mount_path}")
            
            # Mount static assets
            self._mount_static_assets(app, plugin)
            
            plugin.healthy = True
            logger.info(f"Successfully loaded plugin instance for {plugin.id}")

            # Register push listener if plugin advertises push capability
            try:
                inst = plugin.instance
                if getattr(inst, "supports_push", False) and hasattr(inst, "register_listener"):
                    # Define listener callback bridging to central dispatcher
                    def _on_channel_event(raw_evt: dict):  # raw dict from plugin (thread context allowed)
                        # We hop into asyncio loop for dispatcher publish.
                        try:
                            evt = ChannelUpdateEvent(
                                channel_id=raw_evt.get("channel_id", plugin.id),
                                event_type=raw_evt.get("event_type", "update"),
                                payload=raw_evt.get("payload", {}),
                                ts=raw_evt.get("ts") or time.time(),
                                version=raw_evt.get("version", 1),
                                hash=raw_evt.get("hash")
                            )
                        except Exception as build_exc:  # noqa: BLE001
                            logger.warning(f"Failed constructing ChannelUpdateEvent for {plugin.id}: {build_exc}")
                            return
                        # Schedule coroutine safely
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                loop.create_task(channel_event_dispatcher.publish(evt))
                        except RuntimeError:
                            # No running loop (during startup) - ignore
                            pass
                    inst.register_listener(_on_channel_event)
                    logger.info(f"Registered push listener for plugin {plugin.id}")
                    # Ensure global consumer service is started (subscription & stale loop)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(channel_event_consumer.ensure_subscription())
                    except RuntimeError:
                        pass
                    # Register consumer subscription (async) after loop available
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(channel_event_consumer.register_channel(plugin.id))
                    except RuntimeError:
                        pass
            except Exception as push_err:  # noqa: BLE001
                logger.warning(f"Failed to register push listener for {plugin.id}: {push_err}")
            
        except Exception as e:
            logger.error(f"Error loading plugin instance for {plugin.id}: {e}")
            plugin.healthy = False
    
    def _find_channel_class(self, module: Any, plugin_id: str) -> Optional[type]:
        """Find the appropriate channel class in the module"""
        # 1. Look for ChannelClass export (preferred)
        if hasattr(module, 'ChannelClass'):
            return getattr(module, 'ChannelClass')
            
        # 2. Look for class with "Channel" in the name
        class_name = f'{plugin_id.split(".")[-1].title()}Channel'
        if hasattr(module, class_name):
            return getattr(module, class_name)
            
        # 3. Look for any class ending with "Channel"
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                attr_name.endswith('Channel') and 
                attr.__module__ == module.__name__):
                return attr
                
        return None
    
    def _mount_static_assets(self, app: FastAPI, plugin: ChannelPlugin):
        """Mount static assets for the plugin"""
        try:
            # Mount UI directory if it exists
            ui_path = plugin.plugin_path / "ui"
            if ui_path.exists() and ui_path.is_dir():
                mount_path = f"/api/channels/{plugin.id}/ui"
                app.mount(mount_path, StaticFiles(directory=str(ui_path)), name=f"{plugin.id}-ui")
                logger.info(f"Mounted UI assets: {mount_path} -> {ui_path}")

            # Mount assets directory if it exists
            assets_path = plugin.plugin_path / "assets"
            if assets_path.exists() and assets_path.is_dir():
                mount_path = f"/api/channels/{plugin.id}/assets"
                app.mount(mount_path, StaticFiles(directory=str(assets_path)), name=f"{plugin.id}-assets")
                logger.info(f"Mounted assets: {mount_path} -> {assets_path}")

        except Exception as e:
            logger.error(f"Error mounting static assets for {plugin.id}: {e}")
    
    async def check_plugin_health(self, plugin: ChannelPlugin) -> bool:
        """Check if a plugin is healthy"""
        plugin.last_health_check = time.time()
        # For embedded plugins, health is determined by successful loading
        return plugin.healthy
    
    async def get_plugin_manifest(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get manifest from plugin instance"""
        plugin = self.plugins.get(plugin_id)
        if not plugin or not plugin.instance:
            return None
        
        try:
            # Try to get manifest from plugin instance
            if hasattr(plugin.instance, 'get_manifest'):
                return plugin.instance.get_manifest()
            
            # Fallback to basic manifest generation
            return {
                "id": plugin.id,
                "name": plugin.name,
                "description": plugin.description,
                "icon": plugin.icon,
                "imageEndpoints": [],  # Plugin should override this
                "uiComponent": f"/api/channels/{plugin.id}/ui/manage.esm.js",
                "staticAssets": f"/api/channels/{plugin.id}/assets"
            }
                        
        except Exception as e:
            logger.error(f"Error getting manifest for {plugin_id}: {e}")
            return None
    
    async def request_plugin_image(self, plugin_id: str, request_data: Dict[str, Any]) -> Optional[bytes]:
        """Request image generation from plugin instance"""
        plugin = self.plugins.get(plugin_id)
        if not plugin or not plugin.instance:
            return None
        
        try:
            # Try to call image request method on plugin instance
            if hasattr(plugin.instance, 'request_image'):
                return plugin.instance.request_image(request_data)
            
            logger.error(f"Plugin {plugin_id} does not support image requests")
            return None
                        
        except Exception as e:
            logger.error(f"Error requesting image from {plugin_id}: {e}")
            return None
    
    def get_plugin(self, plugin_id: str) -> Optional[ChannelPlugin]:
        """Get plugin by ID"""
        return self.plugins.get(plugin_id)
    
    def get_all_plugins(self) -> List[ChannelPlugin]:
        """Get all discovered plugins"""
        return list(self.plugins.values())
    
    def get_healthy_plugins(self) -> List[ChannelPlugin]:
        """Get only healthy plugins"""
        return [plugin for plugin in self.plugins.values() if plugin.healthy]


# Global service instance
plugin_discovery_service = PluginDiscoveryService()
