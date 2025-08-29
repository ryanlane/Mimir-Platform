"""
Channel Plugin API Routes
FastAPI router for the new embedded plugin architecture

This file implements the 4-endpoint plugin architecture:
1. GET /api/channels/ - List available channel plugins
2. GET /api/channels/{channel_id}/manifest - Get channel capabilities 
3. GET /api/channels/{channel_id}/health - Check channel health
4. POST /api/channels/{channel_id}/request_image - Request image generation

Channel plugins are loaded directly into the main API process and their routes
are mounted at /api/channels/{channel_id}/* by the plugin discovery service.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from app.services.deps import get_plugin_discovery_service
from app.services.plugin_discovery import PluginDiscoveryService
from app.core.logging import get_logger

logger = get_logger("app.api.channels")
router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
async def list_channels(
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """List all available channel plugins"""
    plugins = plugin_discovery.get_all_plugins()
    
    channels = []
    for plugin in plugins:
        channels.append({
            "id": plugin.id,
            "name": plugin.name,
            "description": plugin.description,
            "icon": plugin.icon
        })
    
    return {
        "channels": channels,
        "total": len(channels)
    }


@router.get("/{channel_id}/manifest")
async def get_channel_manifest(
    channel_id: str,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Get channel manifest with current capabilities"""
    manifest = await plugin_discovery.get_plugin_manifest(channel_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Channel not found or unavailable")
    
    return manifest


@router.get("/{channel_id}/health")
async def get_channel_health(
    channel_id: str,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Get channel health status"""
    plugin = plugin_discovery.get_plugin(channel_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For embedded plugins, check if instance is available and working
    healthy = plugin.instance is not None
    
    return {
        "channelId": channel_id,
        "name": plugin.name,
        "healthy": healthy,
        "lastCheck": plugin.last_health_check,
        "pluginPath": plugin.plugin_path
    }


@router.post("/{channel_id}/request_image")
async def request_channel_image(
    channel_id: str,
    request_data: Dict[str, Any] = None,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Request image generation from channel"""
    plugin = plugin_discovery.get_plugin(channel_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if not plugin.instance:
        raise HTTPException(status_code=503, detail="Channel plugin not loaded")
    
    try:
        # Call the request_image method on the embedded plugin instance
        image_data = await plugin.instance.request_image(request_data or {})
        
        # Return the image data (assuming it's base64 encoded or binary)
        return {"image": image_data}
    except Exception as e:
        logger.error(f"Error generating image from plugin {channel_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)}")


# Embedded plugins don't need a general proxy endpoint
# All plugin functionality is exposed through their specific routes
# which are mounted by the plugin discovery service
