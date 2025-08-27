"""
SQLAlchemy database models for Mimir API
Contains all database table definitions and relationships
"""
import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, JSON, 
    ForeignKey, create_engine, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# Create declarative base
Base = declarative_base()


class DistributionMode(str, Enum):
    """Content distribution modes for multi-display systems"""
    MIRROR = "MIRROR"                    # All displays show the same content (default)
    SEQUENTIAL = "SEQUENTIAL"            # Displays cycle through content in order
    RANDOM_UNIQUE = "RANDOM_UNIQUE"      # Displays get randomized content without duplication


class Channel(Base):
    """Channel configuration and metadata - simplified to match actual database schema"""
    __tablename__ = "channels"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String)
    version = Column(String)
    schema_version = Column(String, index=True)
    author = Column(String)
    license = Column(String)
    repo_url = Column(String)
    config = Column(JSON)
    manifest = Column(JSON)
    created_at = Column(DateTime, index=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_channels_name_version', 'name', 'version'),
        Index('ix_channels_created_at', 'created_at'),
        Index('ix_channels_schema_version', 'schema_version'),
    )


class Scene(Base):
    """Scene configuration with channel assignments"""
    __tablename__ = "scenes"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    channels = Column(JSON, nullable=False)  # List of channel configurations
    image_fit = Column(String, default="cover")
    overlay = Column(JSON, nullable=True)
    schedule = Column(JSON, nullable=True)
    theme = Column(String, nullable=True)
    is_active = Column(Boolean, default=False, index=True)
    
    # Redis integration: distribution mode
    distribution_mode = Column(String, default=DistributionMode.MIRROR.value, index=True)
    
    # Content versioning for Redis integration
    content_hash = Column(String, nullable=True, index=True)
    content_epoch = Column(String, nullable=True, index=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    # Indexes
    __table_args__ = (
        Index('ix_scenes_active_distribution', 'is_active', 'distribution_mode'),
        Index('ix_scenes_content_hash_epoch', 'content_hash', 'content_epoch'),
    )


class Overlay(Base):
    """Overlay configurations"""
    __tablename__ = "overlays"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(String)
    channel = Column(JSON, nullable=True)
    path_root = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class DisplayStatus(Base):
    """Legacy display status tracking"""
    __tablename__ = "display_status"
    
    id = Column(Integer, primary_key=True, index=True)
    hardware = Column(JSON)
    current_scene = Column(String, nullable=True, index=True)
    current_image = Column(JSON, nullable=True)
    resolution = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class DisplayClient(Base):
    """Connected display clients with capabilities and status"""
    __tablename__ = "display_clients"
    
    # Primary identification
    id = Column(String, primary_key=True, index=True)  # UUID
    name = Column(String, nullable=False, index=True)  # Human-readable name
    location = Column(String, nullable=True, index=True)  # Physical location
    
    # Display type and discovery
    display_type = Column(String, default="registered", index=True)  # "registered" or "discovered"
    discovery_method = Column(String, nullable=True, index=True)  # "manual", "mdns", "webhook"
    auto_discovered = Column(Boolean, default=False, index=True)  # True for mDNS discovered displays
    
    # Enhanced networking fields
    hostname = Column(String, nullable=True, index=True)  # System hostname for mDNS/networking
    webhook_port = Column(Integer, nullable=True)  # Port for webhook server
    redis_distribution = Column(Boolean, default=False, index=True)  # Supports Redis distribution
    content_claiming = Column(Boolean, default=False, index=True)  # Supports content claiming
    
    # Client capabilities - using old schema fields
    width = Column(Integer, nullable=True)  # Display width
    height = Column(Integer, nullable=True)  # Display height
    orientation = Column(String, default="landscape", index=True)  # "landscape", "portrait"
    client_version = Column(String, nullable=True, index=True)  # Client software version
    
    # Connection status
    is_online = Column(Boolean, default=False, index=True)
    last_seen = Column(DateTime, nullable=True, index=True)
    websocket_connection_id = Column(String, nullable=True, index=True)
    
    # Current assignment - Add proper foreign key relationship in future migration
    assigned_scene_id = Column(String, nullable=True, index=True)  # Will be ForeignKey('scenes.id')
    current_content_hash = Column(String, nullable=True)  # Current content hash
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)
    
    # Indexes and constraints
    __table_args__ = (
        Index('ix_display_clients_online_seen', 'is_online', 'last_seen'),
        Index('ix_display_clients_type_discovery', 'display_type', 'discovery_method'),
        Index('ix_display_clients_capabilities', 'redis_distribution', 'content_claiming'),
        Index('ix_display_clients_assigned_scene', 'assigned_scene_id'),
        UniqueConstraint('hostname', 'webhook_port', name='uq_display_clients_host_port'),
    )


class DistributionQueue(Base):
    """SQL fallback table for content distribution when Redis is unavailable"""
    __tablename__ = "distribution_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(String, index=True, nullable=False)  # Will be ForeignKey('scenes.id')
    content_id = Column(String, nullable=False, index=True)  # Content item identifier
    queue_position = Column(Integer, index=True)  # Position in queue for sequential mode
    
    # Claim tracking
    claimed_at = Column(DateTime, nullable=True, index=True)
    claimed_by = Column(String, nullable=True, index=True)  # Display ID that claimed this content
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)
    epoch_id = Column(String, nullable=True, index=True)  # Content epoch for tracking updates
    
    # Indexes and constraints
    __table_args__ = (
        Index('ix_distribution_queue_scene_position', 'scene_id', 'queue_position'),
        Index('ix_distribution_queue_claimed', 'claimed_by', 'claimed_at'),
        Index('ix_distribution_queue_epoch', 'epoch_id', 'created_at'),
        UniqueConstraint('scene_id', 'content_id', 'epoch_id', name='uq_distribution_queue_content'),
    )


class ContentLease(Base):
    """Audit table for tracking content assignments and leases"""
    __tablename__ = "content_leases"
    
    id = Column(Integer, primary_key=True, index=True)
    lease_id = Column(String, unique=True, index=True, nullable=False)  # Redis lease key
    scene_id = Column(String, index=True, nullable=False)  # Will be ForeignKey('scenes.id')
    display_id = Column(String, index=True, nullable=False)  # Will be ForeignKey('display_clients.id')
    content_id = Column(String, nullable=False, index=True)
    
    # Lease lifecycle
    assigned_at = Column(DateTime, default=datetime.datetime.now, index=True)
    acknowledged_at = Column(DateTime, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    # Status tracking
    status = Column(String, default="assigned", index=True)  # assigned, acknowledged, expired, released
    distribution_mode = Column(String, nullable=False, index=True)
    assignment_id = Column(String, nullable=True, index=True)  # Client-side assignment tracking
    
    # Indexes and constraints
    __table_args__ = (
        Index('ix_content_leases_scene_display', 'scene_id', 'display_id'),
        Index('ix_content_leases_status_expires', 'status', 'expires_at'),
        Index('ix_content_leases_active', 'status', 'assigned_at'),
        UniqueConstraint('scene_id', 'display_id', 'content_id', name='uq_content_leases_assignment'),
    )


# TODO: Add proper foreign key relationships in a future migration
# class Scene(Base):
#     display_clients = relationship("DisplayClient", back_populates="assigned_scene")
# 
# class DisplayClient(Base):
#     assigned_scene = relationship("Scene", back_populates="display_clients")
