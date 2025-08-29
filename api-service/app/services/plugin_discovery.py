"""
Plugin Discovery Service for New Channel Architecture
Handles discovery and management of independent channel services
"""
import json
import asyncio
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChannelPlugin:
    """Represents a discovered channel plugin"""
    id: str
    name: str
    description: str
    icon: Optional[str]
    service_url: str
    config_path: Path
    last_health_check: Optional[float] = None
    healthy: bool = False


class PluginDiscoveryService:
    """Service for discovering and managing channel plugins"""
    
    def __init__(self, channels_dir: Optional[str] = None):
        self.channels_dir = Path(channels_dir or settings.channels_directory)
        self.plugins: Dict[str, ChannelPlugin] = {}
        self.http_timeout = 30  # seconds
        
    async def discover_plugins(self) -> List[ChannelPlugin]:
        """Discover channel plugins by scanning filesystem"""
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
                logger.debug(f"No plugin.json found in {plugin_path.name}, skipping")
                continue
            
            try:
                plugin = await self._load_plugin_config(config_file, plugin_path)
                if plugin:
                    discovered_plugins.append(plugin)
                    self.plugins[plugin.id] = plugin
                    logger.info(f"Discovered plugin: {plugin.id} at {plugin.service_url}")
                    
            except Exception as e:
                logger.error(f"Error loading plugin from {plugin_path}: {e}")
        
        logger.info(f"Plugin discovery complete. Found {len(discovered_plugins)} plugins")
        return discovered_plugins
    
    async def _load_plugin_config(self, config_file: Path, plugin_path: Path) -> Optional[ChannelPlugin]:
        """Load plugin configuration from plugin.json"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate required fields
            required_fields = ['id', 'name', 'description', 'service_url']
            missing_fields = [field for field in required_fields if field not in config]
            
            if missing_fields:
                logger.warning(f"Plugin {plugin_path.name} missing required fields: {missing_fields}")
                return None
            
            plugin = ChannelPlugin(
                id=config['id'],
                name=config['name'],
                description=config['description'],
                icon=config.get('icon'),
                service_url=config['service_url'],
                config_path=config_file
            )
            
            return plugin
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing plugin.json for {plugin_path.name}: {e}")
            return None
    
    async def check_plugin_health(self, plugin: ChannelPlugin) -> bool:
        """Check if a plugin service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                health_url = f"{plugin.service_url.rstrip('/')}/health"
                response = await client.get(health_url)
                plugin.last_health_check = time.time()
                plugin.healthy = response.status_code == 200
                return plugin.healthy
                    
        except Exception as e:
            logger.debug(f"Health check failed for {plugin.id}: {e}")
            plugin.last_health_check = time.time()
            plugin.healthy = False
            return False
    
    async def get_plugin_manifest(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get manifest from plugin service"""
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                manifest_url = f"{plugin.service_url.rstrip('/')}/manifest"
                response = await client.get(manifest_url)
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get manifest for {plugin_id}: {response.status_code}")
                    return None
                        
        except Exception as e:
            logger.error(f"Error getting manifest for {plugin_id}: {e}")
            return None
    
    async def request_plugin_image(self, plugin_id: str, request_data: Dict[str, Any]) -> Optional[bytes]:
        """Request image generation from plugin service"""
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                request_url = f"{plugin.service_url.rstrip('/')}/request_image"
                response = await client.post(request_url, json=request_data)
                if response.status_code == 200:
                    return response.content
                else:
                    logger.error(f"Failed to request image from {plugin_id}: {response.status_code}")
                    return None
                        
        except Exception as e:
            logger.error(f"Error requesting image from {plugin_id}: {e}")
            return None
    
    async def proxy_request(self, plugin_id: str, path: str, method: str = "GET", 
                          json_data: Optional[Dict[str, Any]] = None,
                          query_params: Optional[Dict[str, str]] = None) -> Optional[httpx.Response]:
        """Generic proxy request to plugin service"""
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                url = f"{plugin.service_url.rstrip('/')}/{path.lstrip('/')}"
                
                kwargs = {}
                if json_data:
                    kwargs['json'] = json_data
                if query_params:
                    kwargs['params'] = query_params
                
                response = await client.request(method, url, **kwargs)
                return response
                    
        except Exception as e:
            logger.error(f"Error proxying request to {plugin_id}: {e}")
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
