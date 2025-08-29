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


@router.get("")
async def list_channels(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get paginated list of channels"""
    all_channels = channel_discovery.get_all_channels()
    
    # Simple pagination
    total = len(all_channels)
    start = offset
    end = min(offset + limit, total)
    channels_slice = all_channels[start:end]
    
    channel_responses = []
    for channel_data in channels_slice:
        config = channel_data['config']
        
        # Determine settings type based on structure (same logic as get_channels_manifest)
        settings_config = config.get('settings', {})
        if 'schema' in settings_config and 'defaults' in settings_config:
            # Advanced schema-based settings
            settings_type = config.get('settingsType', config.get('settings_type', 'advanced'))
        else:
            # Simple or no settings
            settings_type = config.get('settingsType', config.get('settings_type', 'simple'))
        
        channel_responses.append(ChannelResponse(
            id=channel_data['id'],
            name=config['name'],
            description=config['description'],
            version=config['version'],
            schemaVersion=config.get('schemaVersion', '2.1'),
            settingsType=settings_type,
            permissions=config.get('permissions', {}),
            uiConfig=config.get('ui', []),
            assetsConfig=config.get('assets', {}),
            currentSettings=config.get('currentSettings', {}),
            status=config.get('status', {}),
            channelDir=str(channel_data['path'])
        ))
    
    return {
        "channels": channel_responses,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/manifest")
async def get_channels_manifest(
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get manifest of all available channels"""
    # Check cache first
    cached_manifest = cache_service.get_cache("channels_manifest")
    if cached_manifest:
        return cached_manifest
    
    # Generate manifest
    manifest = channel_discovery.get_channels_manifest()
    
    # Cache for 5 minutes
    cache_service.set_cache("channels_manifest", manifest, 300)
    
    return manifest


@router.get("/{channel_id}/config")
async def get_channel_config(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel configuration"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    return config


@router.get("/{channel_id}/settings")
async def get_channel_settings(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel settings with schema and current values"""
    # Get channel config for schema and settingsType
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get current settings
    settings = channel_discovery.get_channel_settings(channel_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Extract current values from the {key: {type, value}} format
    current_values = {}
    for key, setting_data in settings.items():
        if isinstance(setting_data, dict) and 'value' in setting_data:
            current_values[key] = setting_data['value']
        else:
            current_values[key] = setting_data
    
    # Get settings configuration from config
    settings_config = config.get('settings', {})
    
    # Determine settings type
    if 'schema' in settings_config and 'defaults' in settings_config:
        settings_type = config.get('settingsType', 'advanced')
    else:
        settings_type = config.get('settingsType', 'simple')
    
    # Return structured response expected by frontend
    return {
        "schema": settings_config.get('schema'),
        "settingsType": settings_type,
        "current": current_values,
        "defaults": settings_config.get('defaults', {})
    }


@router.post("/{channel_id}/settings")
async def update_channel_settings(
    channel_id: str,
    settings: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Update channel settings"""
    success = channel_discovery.update_channel_settings(channel_id, settings)
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {"message": "Settings updated successfully"}


@router.get("/{channel_id}/status")
async def get_channel_status(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel status"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return config.get("status", {})


@router.get("/{channel_id}/health")
async def get_channel_health(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel health status"""
    # Get channel config from discovery service
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Basic health check based on channel status
    status = config.get("status", {})
    healthy = status.get("active", True) and not status.get("lastError")
    
    return {
        "channelId": channel_id,
        "name": config.get("name", channel_id),
        "version": config.get("version", "unknown"),
        "status": status,
        "healthy": healthy,
        "lastCheck": status.get("lastUpdate")
    }


@router.get("/{channel_id}/token")
async def get_channel_token(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get channel authentication token"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, return a simple token based on channel ID
    # In production, this should generate a proper JWT or secure token
    import hashlib
    import time
    
    token_data = f"{channel_id}:{time.time()}"
    token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
    
    return {"token": token}


@router.get("/{channel_id}/current")
async def get_channel_current_content(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get current content for channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Return basic content info
    return {
        "channelId": channel_id,
        "contentType": "image/jpeg",
        "lastUpdate": config.get("status", {}).get("lastUpdate"),
        "available": True
    }


@router.get("/{channel_id}/current.jpg")
async def get_channel_current_image(
    channel_id: str,
    content_service: ContentService = Depends(get_content_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get current image for channel"""
    # Check rate limiting for content requests
    rate_limit = cache_service.check_rate_limit(f"content:{channel_id}", max_requests=30, window_seconds=60)
    if not rate_limit['allowed']:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Get current content
    content_result = content_service.get_current_content(channel_id)
    if not content_result:
        raise HTTPException(status_code=404, detail="Channel not found or no image available")
    
    file_path, file_info = content_result
    
    return FileResponse(
        file_path,
        media_type=file_info.get("mime_type", "image/jpeg"),
        filename=f"{channel_id}_current.jpg"
    )


@router.get("/{channel_id}/current/{resolution}/{filename}")
async def get_channel_content_file(
    channel_id: str,
    resolution: str,
    filename: str,
    content_service: ContentService = Depends(get_content_service),
    cache_service: CacheService = Depends(get_cache_service)
):
    """Get specific content file for channel"""
    # Rate limiting
    rate_limit = cache_service.check_rate_limit(f"content:{channel_id}:{resolution}", max_requests=50, window_seconds=60)
    if not rate_limit['allowed']:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Get content with resolution
    content_result = content_service.get_current_content(channel_id, resolution=resolution)
    if not content_result:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path, file_info = content_result
    
    # Validate file for security
    validation = content_service.validate_content_file(file_path)
    if not validation['valid']:
        raise HTTPException(status_code=400, detail="Invalid file")
    
    return FileResponse(
        file_path,
        media_type=file_info.get("mime_type", "application/octet-stream"),
        filename=filename
    )


@router.post("/{channel_id}/image_request")
async def request_channel_image(
    channel_id: str,
    request_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Request image generation from channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    from datetime import datetime
    
    return {
        "success": True,
        "channelId": channel_id,
        "requestId": f"{channel_id}_{int(datetime.now().timestamp())}",
        "status": "processing",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: str,
    test_data: Dict[str, Any] = None,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Test channel functionality"""
    # Get channel config from discovery service
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    from datetime import datetime
    
    # Basic test - check if channel exists and has valid configuration
    return {
        "success": True,
        "channelId": channel_id,
        "name": config.get("name", channel_id),
        "version": config.get("version", "unknown"),
        "status": config.get("status", {}),
        "test_result": {
            "message": "Channel configuration test passed",
            "basic_test": True,
            "timestamp": datetime.now().isoformat()
        }
    }


@router.get("/{channel_id}/subchannels")
async def list_subchannels(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get list of subchannels for a channel"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'list_subchannels'):
            subchannels = channel_instance.list_subchannels()
            return {"subchannels": subchannels}
        else:
            # Channel doesn't support subchannels
            return {"subchannels": []}
    except Exception as e:
        logger.error(f"Error listing subchannels for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list subchannels")


@router.post("/{channel_id}/subchannels")
async def create_subchannel(
    channel_id: str,
    subchannel_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Create a new subchannel for a channel"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'create_subchannel'):
            result = channel_instance.create_subchannel(subchannel_data)
            return result
        else:
            raise HTTPException(status_code=501, detail="Channel does not support subchannels")
    except Exception as e:
        logger.error(f"Error creating subchannel for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create subchannel")


@router.get("/{channel_id}/subchannels/{subchannel_id}")
async def get_subchannel(
    channel_id: str,
    subchannel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get specific subchannel details"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'get_subchannel'):
            subchannel = channel_instance.get_subchannel(subchannel_id)
            if not subchannel:
                raise HTTPException(status_code=404, detail="Subchannel not found")
            return subchannel
        else:
            raise HTTPException(status_code=501, detail="Channel does not support subchannels")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subchannel {subchannel_id} for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subchannel")


@router.put("/{channel_id}/subchannels/{subchannel_id}")
async def update_subchannel(
    channel_id: str,
    subchannel_id: str,
    update_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Update subchannel metadata"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'update_subchannel'):
            result = channel_instance.update_subchannel(subchannel_id, update_data)
            return result
        else:
            raise HTTPException(status_code=501, detail="Channel does not support subchannels")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subchannel {subchannel_id} for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update subchannel")


@router.delete("/{channel_id}/subchannels/{subchannel_id}")
async def delete_subchannel(
    channel_id: str,
    subchannel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Delete a subchannel from a channel"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'delete_subchannel'):
            result = channel_instance.delete_subchannel(subchannel_id)
            return result
        else:
            raise HTTPException(status_code=501, detail="Channel does not support subchannels")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting subchannel {subchannel_id} for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete subchannel")


@router.post("/{channel_id}/subchannels/{subchannel_id}/content")
async def assign_content_to_subchannel(
    channel_id: str,
    subchannel_id: str,
    content_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Assign content to a subchannel"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'assign_content_to_subchannel'):
            result = channel_instance.assign_content_to_subchannel(subchannel_id, content_data)
            return result
        else:
            raise HTTPException(status_code=501, detail="Channel does not support subchannel content management")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning content to subchannel {subchannel_id} for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign content to subchannel")


@router.get("/{channel_id}/subchannels/{subchannel_id}/settings")
async def get_subchannel_settings(
    channel_id: str,
    subchannel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get subchannel-specific settings"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'get_subchannel_settings'):
            settings = channel_instance.get_subchannel_settings(subchannel_id)
            return settings
        else:
            # Return default empty settings
            return {}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subchannel settings for {subchannel_id} in {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subchannel settings")


@router.put("/{channel_id}/subchannels/{subchannel_id}/settings")
async def update_subchannel_settings(
    channel_id: str,
    subchannel_id: str,
    settings_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Update subchannel-specific settings"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'update_subchannel_settings'):
            result = channel_instance.update_subchannel_settings(subchannel_id, settings_data)
            return result
        else:
            raise HTTPException(status_code=501, detail="Channel does not support subchannel settings")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subchannel settings for {subchannel_id} in {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update subchannel settings")


@router.get("/{channel_id}/subchannels/{subchannel_id}/images")
async def list_subchannel_images(
    channel_id: str,
    subchannel_id: str,
    include_metadata: bool = Query(False, description="Include detailed image metadata"),
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get list of images in a specific subchannel"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'list_subchannel_images'):
            result = channel_instance.list_subchannel_images(subchannel_id, include_metadata=include_metadata)
            return result
        else:
            raise HTTPException(status_code=501, detail="Channel does not support subchannel images")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing subchannel images for {subchannel_id} in {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list subchannel images")


@router.get("/{channel_id}/images")
async def list_images(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get list of images for a channel"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'list_images'):
            images = channel_instance.list_images()
            return images
        else:
            # Channel doesn't support image listing
            return []
    except Exception as e:
        logger.error(f"Error listing images for {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list images")


@router.delete("/{channel_id}/images/{image_id}")
async def delete_image(
    channel_id: str,
    image_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Delete an image from a channel"""
    # Validate channel exists
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get channel instance and delegate
    channel_instance = channel_discovery.get_channel_instance(channel_id)
    if not channel_instance:
        raise HTTPException(status_code=500, detail="Channel instance not available")
    
    try:
        if hasattr(channel_instance, 'delete_image'):
            result = channel_instance.delete_image(image_id)
            return result
        else:
            raise HTTPException(status_code=501, detail="Channel does not support image deletion")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting image {image_id} from {channel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete image")


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Delete channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, deletion is not implemented in discovery service
    raise HTTPException(status_code=501, detail="Channel deletion not implemented")
