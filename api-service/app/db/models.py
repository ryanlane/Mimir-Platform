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


class FrequencyUnit(str, Enum):
    """Schedule frequency units"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


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
    """Scene configuration with channel assignments - simplified to match actual database schema"""
    __tablename__ = "scenes"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    channels = Column(JSON, nullable=False)  # List of channel configurations
    overlays = Column(JSON, nullable=True)  # Changed from 'overlay' to match DB
    timing_config = Column(JSON, nullable=True)  # Changed from 'schedule' to match DB
    is_active = Column(Boolean, index=True)
    
    # Redis integration: distribution mode
    distribution_mode = Column(String, index=True)
    
    # Content versioning for Redis integration
    content_hash = Column(String, nullable=True, index=True)
    content_epoch = Column(Integer, nullable=True, index=True)  # INTEGER not String
    
    # Metadata
    created_at = Column(DateTime, index=True)
    updated_at = Column(DateTime)
    
    # Indexes
    __table_args__ = (
        Index('ix_scenes_active_distribution', 'is_active', 'distribution_mode'),
        Index('ix_scenes_content_hash_epoch', 'content_hash', 'content_epoch'),
        Index('ix_scenes_content_epoch', 'content_epoch'),
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


class SchedulerJob(Base):
    """Independent scheduler jobs that can trigger scene refreshes"""
    __tablename__ = "scheduler_jobs"
    
    # Primary identification
    id = Column(String, primary_key=True, index=True)  # UUID
    name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    enabled = Column(Boolean, default=True, index=True)
    
    # Schedule configuration
    freq_unit = Column(String, nullable=False, index=True)  # FrequencyUnit values
    freq_value = Column(Integer, nullable=False)  # e.g., 5 minutes, 2 weeks
    approx_interval_seconds = Column(Integer, nullable=True)  # For metrics/UX
    
    # Timing control
    timezone_name = Column(String, nullable=True)  # For future "daily at 9am" features
    next_run_at = Column(DateTime, nullable=False, index=True)
    last_run_at = Column(DateTime, nullable=True, index=True)
    
    # Execution control and locking
    locked_until = Column(DateTime, nullable=True, index=True)
    run_timeout_seconds = Column(Integer, default=90)
    
    # Error handling and backoff
    consecutive_failures = Column(Integer, default=0, index=True)
    last_error = Column(String, nullable=True)
    jitter_seconds = Column(Integer, default=15)
    
    # Action configuration - what to do when triggered
    action_type = Column(String, default="refresh_scene", index=True)  # "refresh_scene", "webhook", etc.
    action_config = Column(JSON, nullable=True)  # Flexible action configuration
    
    # Output tracking
    last_success_at = Column(DateTime, nullable=True, index=True)
    last_output = Column(JSON, nullable=True)  # Store last execution result
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)
    
    # Indexes for efficient scheduler queries
    __table_args__ = (
        Index('ix_scheduler_jobs_due', 'enabled', 'next_run_at'),
        Index('ix_scheduler_jobs_locked', 'locked_until', 'next_run_at'),
        Index('ix_scheduler_jobs_failures', 'consecutive_failures', 'enabled'),
        Index('ix_scheduler_jobs_action', 'action_type', 'enabled'),
    )


class SchedulerJobSceneAssignment(Base):
    """Association between scheduler jobs and scenes"""
    __tablename__ = "scheduler_job_scene_assignments"
    
    id = Column(String, primary_key=True, index=True)  # UUID
    job_id = Column(String, nullable=False, index=True)  # Will be ForeignKey('scheduler_jobs.id')
    scene_id = Column(String, nullable=False, index=True)  # Will be ForeignKey('scenes.id')
    
    # Assignment configuration
    refresh_method = Column(String, default="content_refresh", index=True)  # "content_refresh", "full_reload"
    priority = Column(Integer, default=100, index=True)  # For ordering when multiple jobs target same scene
    
    # Metadata
    created_at = Column(DateTime, default=datetime.datetime.now, index=True)
    
    # Indexes and constraints
    __table_args__ = (
        Index('ix_scheduler_scene_assignments_job_scene', 'job_id', 'scene_id'),
        Index('ix_scheduler_scene_assignments_scene_priority', 'scene_id', 'priority'),
        UniqueConstraint('job_id', 'scene_id', name='uq_scheduler_job_scene'),
    )


class SchedulerExecution(Base):
    """Audit log for scheduler job executions"""
    __tablename__ = "scheduler_executions"
    
    id = Column(String, primary_key=True, index=True)  # UUID
    job_id = Column(String, nullable=False, index=True)  # Reference to SchedulerJob
    
    # Execution details
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)  # "pending", "success", "failed", "timeout"
    
    # Results
    output_data = Column(JSON, nullable=True)  # Execution results
    error_message = Column(String, nullable=True)
    execution_duration_ms = Column(Integer, nullable=True)
    affected_scenes = Column(JSON, nullable=True)  # List of scene IDs that were updated
    
    # Context
    worker_id = Column(String, nullable=True, index=True)  # For tracking which worker handled it
    trigger_reason = Column(String, default="scheduled", index=True)  # "scheduled", "manual", "retry"
    
    # Indexes
    __table_args__ = (
        Index('ix_scheduler_executions_job_status', 'job_id', 'status'),
        Index('ix_scheduler_executions_started', 'started_at'),
        Index('ix_scheduler_executions_worker', 'worker_id', 'started_at'),
    )


# TODO: Add proper foreign key relationships in a future migration
# class Scene(Base):
#     display_clients = relationship("DisplayClient", back_populates="assigned_scene")
# 
# class DisplayClient(Base):
#     assigned_scene = relationship("Scene", back_populates="display_clients")
