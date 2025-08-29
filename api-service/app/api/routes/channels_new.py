"""
Channel Plugin API Routes
FastAPI router for the new plugin-based channel architecture

This file implements the 4-endpoint plugin architecture:
1. GET /api/channels/ - List available channel plugins
2. GET /api/channels/{channel_id}/manifest - Get channel capabilities 
3. GET /api/channels/{channel_id}/health - Check channel health
4. POST /api/channels/{channel_id}/request_image - Request image generation

All other channel operations are proxied directly to the channel services.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from typing import Dict, Any, List
import httpx

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
    
    # Perform health check
    healthy = await plugin_discovery.check_plugin_health(plugin)
    
    return {
        "channelId": channel_id,
        "name": plugin.name,
        "healthy": healthy,
        "lastCheck": plugin.last_health_check,
        "serviceUrl": plugin.service_url
    }


@router.post("/{channel_id}/request_image")
async def request_channel_image(
    channel_id: str,
    request_data: Dict[str, Any],
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Request image generation from channel"""
    image_data = await plugin_discovery.request_plugin_image(channel_id, request_data)
    if not image_data:
        raise HTTPException(status_code=404, detail="Channel not found or failed to generate image")
    
    # Return image as response
    return Response(content=image_data, media_type="image/jpeg")


@router.api_route("/{channel_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_channel(
    channel_id: str,
    path: str,
    request: Request,
    plugin_discovery: PluginDiscoveryService = Depends(get_plugin_discovery_service)
):
    """Proxy all other requests to the channel service"""
    plugin = plugin_discovery.get_plugin(channel_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Extract request data
    method = request.method
    query_params = dict(request.query_params) if request.query_params else None
    
    # Handle request body for POST/PUT/PATCH requests
    json_data = None
    if method in ["POST", "PUT", "PATCH"]:
        try:
            json_data = await request.json()
        except:
            # If not JSON, we'll pass through without body for now
            pass
    
    # Proxy the request
    response = await plugin_discovery.proxy_request(
        channel_id, 
        path, 
        method=method,
        json_data=json_data,
        query_params=query_params
    )
    
    if not response:
        raise HTTPException(status_code=503, detail="Channel service unavailable")
    
    # Return the proxied response
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.headers.get("content-type", "application/json")
    )
