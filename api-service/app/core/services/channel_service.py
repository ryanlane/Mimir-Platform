"""
Channel Service
Business logic for channel management operations
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.infrastructure.database.models import Channel


class ChannelService:
    """Service class for channel operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_channels(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Get paginated list of channels"""
        total = self.db.query(Channel).count()
        channels = self.db.query(Channel).offset(offset).limit(limit).all()
        
        result = []
        for c in channels:
            result.append({
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "relLogoImagePath": c.rel_logo_image_path,
                "version": c.version,
                "settingsType": c.settings_type,
                "status": c.status,
                "schemaVersion": c.schema_version,
                "permissions": c.permissions or [],
                "hasUI": bool(c.ui_config),
                "hasAssets": bool(c.assets_config),
                "channelDir": c.channel_dir
            })
        
        return {
            "channels": result,
            "meta": {
                "total": total,
                "limit": limit,
                "offset": offset
            }
        }
    
    def get_channel_by_id(self, channel_id: str) -> Optional[Channel]:
        """Get channel by ID"""
        return self.db.query(Channel).filter(Channel.id == channel_id).first()
    
    def get_channel_config(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel configuration"""
        channel = self.get_channel_by_id(channel_id)
        if not channel:
            return None
        
        return {
            "id": channel.id,
            "name": channel.name,
            "description": channel.description,
            "version": channel.version,
            "settings_type": channel.settings_type,
            "config_schema": channel.config_schema,
            "ui_config": channel.ui_config,
            "assets_config": channel.assets_config,
            "permissions": channel.permissions or [],
            "schema_version": channel.schema_version
        }
    
    def get_channel_settings(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get channel settings"""
        channel = self.get_channel_by_id(channel_id)
        if not channel:
            return None
        
        return channel.current_settings or {}
    
    def update_channel_settings(self, channel_id: str, settings: Dict[str, Any]) -> bool:
        """Update channel settings"""
        channel = self.get_channel_by_id(channel_id)
        if not channel:
            return False
        
        channel.current_settings = settings
        self.db.commit()
        return True
    
    def update_channel_status(self, channel_id: str, status: Dict[str, Any]) -> bool:
        """Update channel status"""
        channel = self.get_channel_by_id(channel_id)
        if not channel:
            return False
        
        channel.status = status
        self.db.commit()
        return True
    
    def create_channel(self, channel_data: Dict[str, Any]) -> Channel:
        """Create a new channel"""
        channel = Channel(**channel_data)
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return channel
    
    def delete_channel(self, channel_id: str) -> bool:
        """Delete channel by ID"""
        channel = self.get_channel_by_id(channel_id)
        if not channel:
            return False
        
        self.db.delete(channel)
        self.db.commit()
        return True
