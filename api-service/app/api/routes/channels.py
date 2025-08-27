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
        channel_responses.append(ChannelResponse(
            id=channel_data['id'],
            name=config['name'],
            description=config['description'],
            version=config['version'],
            schemaVersion=config.get('schemaVersion', '2.1'),
            settingsType=config.get('settingsType', 'simple'),
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
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get channel status"""
    channel = channel_service.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return channel.status or {}


@router.get("/{channel_id}/health")
async def get_channel_health(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get channel health status"""
    health = channel_service.get_channel_health(channel_id)
    if health is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return health


@router.get("/{channel_id}/token")
async def get_channel_token(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get channel authentication token"""
    token = channel_service.get_channel_token(channel_id)
    if not token:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"token": token}


@router.get("/{channel_id}/current")
async def get_channel_current_content(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get current content for channel"""
    content = channel_service.get_current_content(channel_id)
    if not content:
        raise HTTPException(status_code=404, detail="Channel not found or no content available")
    return content


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
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Request image generation from channel"""
    result = channel_service.request_image(channel_id, request_data)
    if not result:
        raise HTTPException(status_code=404, detail="Channel not found")
    return result


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: str,
    test_data: Dict[str, Any] = None,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Test channel functionality"""
    result = channel_service.test_channel(channel_id, test_data or {})
    if not result:
        raise HTTPException(status_code=404, detail="Channel not found")
    return result


@router.get("/{channel_id}/subchannels")
async def list_subchannels(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get list of subchannels for a channel"""
    subchannels = channel_service.get_subchannels(channel_id)
    if subchannels is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"subchannels": subchannels}


@router.get("/{channel_id}/subchannels/config")
async def get_subchannels_config(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get subchannel configuration for a channel"""
    config = channel_service.get_subchannels_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    return config


@router.get("/{channel_id}/subchannels/{subchannel_id}")
async def get_subchannel(
    channel_id: str,
    subchannel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get specific subchannel data"""
    subchannel = channel_service.get_subchannel(channel_id, subchannel_id)
    if not subchannel:
        raise HTTPException(status_code=404, detail="Channel or subchannel not found")
    return subchannel


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Delete channel"""
    success = channel_service.delete_channel(channel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {"message": "Channel deleted successfully"}
