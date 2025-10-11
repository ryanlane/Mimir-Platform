"""
Channel Plugin API Routes
FastAPI router for the new embedded plugin architecture

This file implements the core channel listing/metadata endpoints. Channel-owned
image endpoints (like /request-image) are exposed by each plugin's router and
should not be overridden here.

Provided endpoints:
1. GET /api/channels/ - List available channel plugins
2. GET /api/channels/{channel_id}/manifest - Get channel capabilities
3. GET /api/channels/{channel_id}/health - Check channel health

Channel plugins are loaded directly into the main API process and their routes
are mounted at /api/channels/{channel_id}/* by the plugin discovery service.
"""
from fastapi import APIRouter, Depends, HTTPException, Response

from app.services.deps import get_plugin_discovery_service
from app.services.plugin_discovery import PluginDiscoveryService
from app.core.logging import get_logger
from app.services.channel_image_store import channel_image_store

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


## NOTE: The unified request_image endpoint has been removed intentionally to avoid
## shadowing channel-owned endpoints. Call the channel's own `/request-image` route
## (mounted by the plugin) for image generation.


@router.get("/{channel_id}/images/{image_id}")
async def get_channel_image(
    channel_id: str,
    image_id: str,
):
    """Return previously generated channel image by ID.

    Images are ephemeral; a 404 will be returned if expired or missing.
    """
    record = channel_image_store.get(channel_id, image_id)
    if not record:
        raise HTTPException(status_code=404, detail="Image not found or expired")
    return Response(content=record.content, media_type=record.content_type)


# Embedded plugins don't need a general proxy endpoint
# All plugin functionality is exposed through their specific routes
# which are mounted by the plugin discovery service
