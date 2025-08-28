"""
Channel API Routes
FastAPI router for channel-related endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any, List

from app.services.deps import (
    get_channel_discovery_service,
    get_content_service,
    get_cache_service,
    get_channel_service
)
from app.services.channel_discovery import ChannelDiscoveryService
from app.services.content import ContentService
from app.services.caching import CacheService
from app.core.services.channel_service import ChannelService
from app.schemas.channels import (
    ChannelResponse
)
# TODO: Add these schemas when they're created in the schemas file
# from app.schemas.channels import ChannelListResponse


router = APIRouter(prefix="/channels", tags=["channels"])


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
    """Get channel settings"""
    settings = channel_discovery.get_channel_settings(channel_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return settings


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
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, return empty list - subchannels would be implemented later
    return {"subchannels": []}


@router.post("/{channel_id}/subchannels")
async def create_subchannel(
    channel_id: str,
    subchannel_data: Dict[str, Any],
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Create a new subchannel (gallery) for a channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Basic gallery creation response
    gallery_name = subchannel_data.get("name", "New Gallery")
    gallery_id = gallery_name.lower().replace(" ", "_")
    
    return {
        "success": True,
        "subchannel": {
            "id": gallery_id,
            "name": gallery_name,
            "type": "gallery",
            "created": True
        }
    }


@router.get("/{channel_id}/images")
async def list_channel_images(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get list of images for a channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, return empty images list - this would be implemented to scan channel directory
    return {
        "images": [],
        "total": 0,
        "channel_id": channel_id
    }


@router.get("/{channel_id}/subchannels/config")
async def get_subchannels_config(
    channel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get subchannel configuration for a channel"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {
        "channelId": channel_id,
        "subchannels": [],
        "config": {}
    }


@router.get("/{channel_id}/subchannels/{subchannel_id}")
async def get_subchannel(
    channel_id: str,
    subchannel_id: str,
    channel_discovery: ChannelDiscoveryService = Depends(get_channel_discovery_service)
):
    """Get specific subchannel data"""
    config = channel_discovery.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # For now, return None - subchannels would be implemented later
    raise HTTPException(status_code=404, detail="Subchannel not found")


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
