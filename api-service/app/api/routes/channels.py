"""
Channel API Routes
FastAPI router for channel-related endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any
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
