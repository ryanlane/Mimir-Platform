"""
Database models for Mimir API
SQLAlchemy ORM models representing the core domain entities
"""
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Channel(Base):
    """Channel model representing content sources"""
    __tablename__ = "channels"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    version = Column(String, default="1.0.0")
    settings_type = Column(String, default="simple")
    config_schema = Column(JSON, nullable=True)
    current_settings = Column(JSON, nullable=True)
    status = Column(JSON, nullable=True)
    rel_logo_image_path = Column(String, nullable=True)
    # v2.1 additions
    schema_version = Column(String, default="2.1")
    permissions = Column(JSON, nullable=True)
    ui_config = Column(JSON, nullable=True)
    assets_config = Column(JSON, nullable=True)
    integrity_hashes = Column(JSON, nullable=True)
    channel_dir = Column(String, nullable=True)


class Scene(Base):
    """Scene model representing content presentation configurations"""
    __tablename__ = "scenes"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    channels = Column(JSON)
    image_fit = Column(String, default="cover")
    overlay = Column(JSON, nullable=True)
    schedule = Column(JSON, nullable=True)
    theme = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)


class Overlay(Base):
    """Overlay model representing UI overlays for displays"""
    __tablename__ = "overlays"

    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    description = Column(String)
    channel = Column(JSON, nullable=True)
    path_root = Column(String, nullable=True)


class DisplayStatus(Base):
    """Display status model for hardware status tracking"""
    __tablename__ = "display_status"

    id = Column(Integer, primary_key=True, index=True)
    hardware = Column(JSON)
    current_scene = Column(String, nullable=True)
    current_image = Column(JSON, nullable=True)
    resolution = Column(JSON)


class DisplayClient(Base):
    """Display client model representing connected display devices"""
    __tablename__ = "display_clients"

    id = Column(String, primary_key=True, index=True)  # UUID
    name = Column(String, nullable=False)  # Human-readable name
    description = Column(String, nullable=True)
    location = Column(String, nullable=True)  # Physical location
    hostname = Column(String, nullable=True)  # System hostname (e.g., "colorframe05")

    # Client capabilities
    resolution = Column(JSON, nullable=True)  # [width, height]
    supported_formats = Column(JSON, nullable=True)  # ["jpg", "png", "gif"]
    orientation = Column(String, default="landscape")  # "landscape", "portrait"
    refresh_rate_hz = Column(Integer, nullable=True)  # Display refresh rate
    client_version = Column(String, nullable=True)  # Client software version

    # Network capabilities
    webhook_port = Column(Integer, nullable=True)  # Webhook server port for manual updates
    redis_distribution = Column(Boolean, default=False)  # Supports Redis distribution
    content_claiming = Column(Boolean, default=False)  # Supports content claiming

    # Connection status
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    last_image_fetch = Column(DateTime, nullable=True)  # When client last fetched image
    websocket_connection_id = Column(String, nullable=True)

    # Current assignment
    assigned_scene_id = Column(String, nullable=True)  # ForeignKey to scenes
    current_image_path = Column(String, nullable=True)  # Path to current scene image

    # Configuration
    settings = Column(JSON, nullable=True)  # Display-specific settings
    tags = Column(JSON, nullable=True)  # ["lobby", "conference-room", "kiosk"]

    # Metadata
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
