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
import traceback

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
            config_file = plugin_path / "plugin.json"
            if not config_file.exists():
                logger.debug("[plugins] %s: missing plugin.json, checking config.json", plugin_path.name)
                config_file = plugin_path / "config.json"
                if not config_file.exists():
                    logger.debug("[plugins] %s: no config file present, skipping", plugin_path.name)
                    continue
            try:
                logger.debug("[plugins] Loading config for %s", plugin_path)
                plugin = await self._load_plugin_config(config_file, plugin_path)
                if not plugin:
                    logger.debug("[plugins] %s: config load returned None", plugin_path.name)
                    continue
                logger.debug("[plugins] %s: config loaded (id=%s) – loading instance", plugin_path.name, plugin.id)
                await self._load_plugin_instance(plugin, app)
                discovered_plugins.append(plugin)
                self.plugins[plugin.id] = plugin
                logger.info("Discovered plugin: %s at %s (healthy=%s)", plugin.id, plugin.plugin_path, plugin.healthy)
            except Exception as e:  # noqa: BLE001
                logger.error("Error loading plugin from %s: %s", plugin_path, e)
                if logger.isEnabledFor(10):
                    logger.debug("Traceback loading %s:\n%s", plugin_path, traceback.format_exc(limit=10))
        
        logger.info(f"Plugin discovery complete. Found {len(discovered_plugins)} plugins")
        return discovered_plugins
    
    async def _load_plugin_config(self, config_file: Path, plugin_path: Path) -> Optional[ChannelPlugin]:
        """Load plugin configuration from plugin.json or config.json"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            if config_file.name == "plugin.json":
                required = ['id', 'name', 'description']
                missing = [k for k in required if k not in config]
                if missing:
                    logger.warning("Plugin %s missing required fields: %s", plugin_path.name, missing)
                    return None
                return ChannelPlugin(
                    id=config['id'],
                    name=config['name'],
                    description=config['description'],
                    icon=config.get('icon'),
                    config_path=config_file,
                    plugin_path=plugin_path
                )
            # legacy config.json path
            required = ['name', 'description']
            missing = [k for k in required if k not in config]
            if missing:
                logger.warning("Legacy plugin %s missing required fields: %s", plugin_path.name, missing)
                return None
            plugin_id = config.get('id', plugin_path.name)
            return ChannelPlugin(
                id=plugin_id,
                name=config['name'],
                description=config['description'],
                icon=config.get('icon'),
                config_path=config_file,
                plugin_path=plugin_path
            )
        except json.JSONDecodeError as e:
            logger.error("Error parsing %s for %s: %s", config_file.name, plugin_path.name, e)
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
            logger.debug(f"[plugins] ({plugin.id}) Checking for channel.py at {channel_file}")
            
            # Import the channel module
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin.id.replace('.', '_')}", 
                channel_file
            )
            if spec is None or spec.loader is None:
                logger.error(f"Failed to create module spec for {plugin.id}")
                plugin.healthy = False
                return
            
            spec_name = f"plugin_{plugin.id.replace('.', '_')}"
            logger.debug(f"[plugins] ({plugin.id}) Creating module spec name={spec_name}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec_name] = module
            logger.debug(f"[plugins] ({plugin.id}) Executing module spec")
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            logger.debug(f"[plugins] ({plugin.id}) Module loaded; searching for channel class")
            
            # Find and instantiate the channel class
            channel_class = self._find_channel_class(module, plugin.id)
            if not channel_class:
                logger.error(f"No suitable channel class found for {plugin.id}")
                plugin.healthy = False
                return
            
            logger.info(f"Found channel class for {plugin.id}: {channel_class.__name__} from {channel_class.__module__}")
            
            # Instantiate the channel
            try:
                logger.debug(f"[plugins] ({plugin.id}) Instantiating channel class {channel_class.__name__}")
                plugin.instance = channel_class(str(plugin.plugin_path))
            except Exception as inst_exc:
                plugin.healthy = False
                logger.error(f"Failed instantiating channel {plugin.id}: {inst_exc}")
                if logger.isEnabledFor(10):
                    logger.debug("Traceback: %s", traceback.format_exc(limit=12))
                return
            
            # Mount plugin router if available
            if hasattr(plugin.instance, 'get_router'):
                try:
                    router = plugin.instance.get_router()
                except Exception as r_exc:
                    logger.error(f"Router construction failed for {plugin.id}: {r_exc}")
                    if logger.isEnabledFor(10):
                        logger.debug("Traceback: %s", traceback.format_exc(limit=12))
                    plugin.healthy = False
                    return
                if router:
                    mount_path = f"/api/channels/{plugin.id}"
                    app.include_router(router, prefix=mount_path, tags=[f"plugin-{plugin.id}"])
                    logger.info(f"Mounted plugin router: {mount_path}")
                else:
                    logger.warning(f"get_router returned None for {plugin.id}")
            
            # Mount static assets
            self._mount_static_assets(app, plugin)
            
            plugin.healthy = True
            logger.info(f"Successfully loaded plugin instance for {plugin.id}")

            # Register push listener if plugin advertises push capability
            try:
                inst = plugin.instance
                if getattr(inst, "supports_push", False) and hasattr(inst, "register_listener"):
                    # Define listener callback bridging to central dispatcher
                    # Capture the main event loop to allow cross-thread scheduling from PushManager thread
                    try:
                        main_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        # Fallback for environments where get_running_loop isn't available here; best-effort
                        main_loop = None  # type: ignore[assignment]

                    def _on_channel_event(raw_evt: dict):  # raw dict from plugin (thread context allowed)
                        # Build event and publish it into the API's dispatcher from any thread.
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
                        # Schedule coroutine safely using the captured loop (thread-safe)
                        try:
                            if main_loop and main_loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    channel_event_dispatcher.publish(evt), main_loop
                                )
                            else:
                                # As a last resort, try current thread's loop if present
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    loop.create_task(channel_event_dispatcher.publish(evt))
                        except Exception:
                            # Avoid crashing plugin thread on scheduling errors
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
