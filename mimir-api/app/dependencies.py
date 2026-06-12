"""
Dependency injection for Mimir API
Provides FastAPI dependencies for services and infrastructure components
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.infrastructure.database.connection import get_db


def get_channel_service(db: Session = Depends(get_db)):
    """Get channel service instance with database dependency"""
    from app.core.services.channel_service import ChannelService
    return ChannelService(db)


def get_scene_service(db: Session = Depends(get_db)):
    """Get scene service instance with database dependency"""
    from app.core.services.scene_service import SceneService
    return SceneService(db)


def get_display_service(db: Session = Depends(get_db)):
    """Get display service instance with database dependency"""
    from app.core.services.display_service import DisplayService
    return DisplayService(db)


def get_channel_manager():
    """Get channel manager instance"""
    from app.infrastructure.channels.manager import ChannelManager
    return ChannelManager()


def get_websocket_manager():
    """Get WebSocket manager instance"""
    from app.infrastructure.websocket.manager import WebSocketManager
    return WebSocketManager()
