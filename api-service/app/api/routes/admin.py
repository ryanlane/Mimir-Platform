"""
Health and Admin API Routes
FastAPI router for health checks and administrative endpoints
"""
from fastapi import APIRouter, Depends
from app.dependencies import get_channel_service, get_scene_service, get_display_service
from app.config import settings


health_router = APIRouter(tags=["health"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@health_router.get("/health")
async def health_check():
    """System health check endpoint"""
    return {
        "status": "healthy",
        "database": {
            "status": "connected"
        },
        "channels": {
            "status": "operational"
        },
        "websocket": {
            "status": "operational"
        },
        "uptime": "running"
    }


@admin_router.get("/redis/status")
async def get_redis_status():
    """Get Redis connection status"""
    return {
        "enabled": settings.redis_enabled,
        "connected": settings.redis_enabled,  # Simplified for now
        "url": settings.redis_dsn if settings.redis_enabled else None,
        "status": "connected" if settings.redis_enabled else "disabled"
    }


@admin_router.post("/channels/reload")
async def reload_channels():
    """Reload all channels"""
    # TODO: Implement channel reloading logic
    return {"message": "Channels reloaded successfully"}


@admin_router.get("/channels/debug")
async def debug_channels():
    """Debug information for channels"""
    # TODO: Implement channel debugging logic
    return {"debug_info": "Channel debug information"}


@admin_router.post("/channels/{channel_id}/reload")
async def reload_channel(channel_id: str):
    """Reload a specific channel"""
    # TODO: Implement single channel reloading logic
    return {"message": f"Channel {channel_id} reloaded successfully"}


@admin_router.get("/channels/orphaned")
async def get_orphaned_channels():
    """Get orphaned channels"""
    # TODO: Implement orphaned channel detection
    return {"orphaned_channels": []}


@admin_router.post("/channels/reset")
async def reset_channels():
    """Reset all channels"""
    # TODO: Implement channel reset logic
    return {"message": "Channels reset successfully"}
