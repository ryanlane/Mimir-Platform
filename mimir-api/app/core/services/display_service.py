"""
Display Service
Business logic for display client management operations
"""
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models import DisplayClient, DisplayStatus


class DisplayService:
    """Service class for display operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_display_clients(self) -> list[dict[str, Any]]:
        """Get all display clients"""
        clients = self.db.query(DisplayClient).all()

        result = []
        for client in clients:
            result.append({
                "id": client.id,
                "name": client.name,
                "description": client.description,
                "location": client.location,
                "resolution": client.resolution,
                "supported_formats": client.supported_formats,
                "orientation": client.orientation,
                "refresh_rate_hz": client.refresh_rate_hz,
                "client_version": client.client_version,
                "is_online": client.is_online,
                "last_seen": client.last_seen,
                "last_image_fetch": client.last_image_fetch,
                "assigned_scene_id": client.assigned_scene_id,
                "current_image_path": client.current_image_path,
                "settings": client.settings,
                "tags": client.tags
            })

        return result

    def get_display_client_by_id(self, client_id: str) -> DisplayClient | None:
        """Get display client by ID"""
        return self.db.query(DisplayClient).filter(DisplayClient.id == client_id).first()

    def create_display_client(self, client_data: dict[str, Any]) -> DisplayClient:
        """Create a new display client"""
        client = DisplayClient(
            id=client_data["id"],
            name=client_data["name"],
            description=client_data.get("description"),
            location=client_data.get("location"),
            resolution=client_data.get("resolution"),
            supported_formats=client_data.get("supported_formats"),
            orientation=client_data.get("orientation", "landscape"),
            refresh_rate_hz=client_data.get("refresh_rate_hz"),
            client_version=client_data.get("client_version"),
            settings=client_data.get("settings"),
            tags=client_data.get("tags", []),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def update_display_client(self, client_id: str, client_data: dict[str, Any]) -> DisplayClient | None:
        """Update display client"""
        client = self.get_display_client_by_id(client_id)
        if not client:
            return None

        # Update client attributes
        for key, value in client_data.items():
            if hasattr(client, key):
                setattr(client, key, value)

        client.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(client)
        return client

    def update_client_status(self, client_id: str, is_online: bool) -> bool:
        """Update client online status"""
        client = self.get_display_client_by_id(client_id)
        if not client:
            return False

        client.is_online = is_online
        client.last_seen = datetime.utcnow()
        client.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def assign_scene_to_client(self, client_id: str, scene_id: str) -> bool:
        """Assign a scene to a display client"""
        client = self.get_display_client_by_id(client_id)
        if not client:
            return False

        client.assigned_scene_id = scene_id
        client.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def update_image_fetch_time(self, client_id: str) -> bool:
        """Update the last image fetch time for a client"""
        client = self.get_display_client_by_id(client_id)
        if not client:
            return False

        client.last_image_fetch = datetime.utcnow()
        self.db.commit()
        return True

    def delete_display_client(self, client_id: str) -> bool:
        """Delete display client"""
        client = self.get_display_client_by_id(client_id)
        if not client:
            return False

        self.db.delete(client)
        self.db.commit()
        return True

    def get_display_status(self) -> dict[str, Any] | None:
        """Get display status"""
        status = self.db.query(DisplayStatus).first()
        if not status:
            return None

        return {
            "id": status.id,
            "hardware": status.hardware,
            "current_scene": status.current_scene,
            "current_image": status.current_image,
            "resolution": status.resolution
        }

    def update_display_status(self, status_data: dict[str, Any]) -> bool:
        """Update display status"""
        status = self.db.query(DisplayStatus).first()
        if not status:
            # Create new status record
            status = DisplayStatus(
                hardware=status_data.get("hardware"),
                current_scene=status_data.get("current_scene"),
                current_image=status_data.get("current_image"),
                resolution=status_data.get("resolution")
            )
            self.db.add(status)
        else:
            # Update existing status
            if "hardware" in status_data:
                status.hardware = status_data["hardware"]
            if "current_scene" in status_data:
                status.current_scene = status_data["current_scene"]
            if "current_image" in status_data:
                status.current_image = status_data["current_image"]
            if "resolution" in status_data:
                status.resolution = status_data["resolution"]

        self.db.commit()
        return True
