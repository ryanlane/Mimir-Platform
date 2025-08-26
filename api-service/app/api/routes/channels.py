"""
Channel API Routes
FastAPI router for channel-related endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from typing import Dict, Any, List
from app.dependencies import get_channel_service
from app.core.services.channel_service import ChannelService


router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
async def list_channels(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get paginated list of channels"""
    return channel_service.get_channels(limit=limit, offset=offset)


@router.get("/manifest")
async def get_channels_manifest(
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get manifest of all available channels"""
    return channel_service.get_channels_manifest()


@router.get("/{channel_id}/config")
async def get_channel_config(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get channel configuration"""
    config = channel_service.get_channel_config(channel_id)
    if not config:
        raise HTTPException(status_code=404, detail="Channel not found")
    return config


@router.get("/{channel_id}/settings")
async def get_channel_settings(
    channel_id: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get channel settings"""
    settings = channel_service.get_channel_settings(channel_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return settings


@router.post("/{channel_id}/settings")
async def update_channel_settings(
    channel_id: str,
    settings: Dict[str, Any],
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Update channel settings"""
    success = channel_service.update_channel_settings(channel_id, settings)
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
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get current image for channel"""
    image_path = channel_service.get_current_image_path(channel_id)
    if not image_path:
        raise HTTPException(status_code=404, detail="Channel not found or no image available")
    
    return FileResponse(
        image_path,
        media_type="image/jpeg",
        filename=f"{channel_id}_current.jpg"
    )


@router.get("/{channel_id}/current/{resolution}/{filename}")
async def get_channel_content_file(
    channel_id: str,
    resolution: str,
    filename: str,
    channel_service: ChannelService = Depends(get_channel_service)
):
    """Get specific content file for channel"""
    file_path = channel_service.get_content_file_path(channel_id, resolution, filename)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)


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
