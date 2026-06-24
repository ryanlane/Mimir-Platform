# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Service Dependencies
Provides dependency injection for all services
"""
from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.caching import CacheService, cache_service
from app.services.channel_discovery import (
    ChannelDiscoveryService,
    channel_discovery_service,
)
from app.services.content import ContentService, content_service
from app.services.distribution import DistributionService, distribution_service
from app.services.plugin_discovery import (
    PluginDiscoveryService,
    plugin_discovery_service,
)
from app.services.scene_service import SceneService
from app.services.websocket import WebSocketService, websocket_service

# Global service instances (for services that don't need per-request state)


def get_channel_discovery_service() -> ChannelDiscoveryService:
    """Get channel discovery service instance"""
    return channel_discovery_service


def get_plugin_discovery_service() -> PluginDiscoveryService:
    """Get plugin discovery service instance"""
    return plugin_discovery_service


def get_websocket_service() -> WebSocketService:
    """Get WebSocket service instance"""
    return websocket_service


def get_distribution_service() -> DistributionService:
    """Get distribution service instance"""
    return distribution_service


def get_cache_service() -> CacheService:
    """Get cache service instance"""
    return cache_service


def get_content_service() -> ContentService:
    """Get content service instance"""
    return content_service


def get_scene_service(db: Session = Depends(get_session)) -> SceneService:
    """Get scene service instance with database dependency"""
    return SceneService(db)


# Alternative dependency functions for FastAPI dependency injection
def websocket_service_dependency() -> Generator[WebSocketService, None, None]:
    """FastAPI dependency for WebSocket service"""
    yield websocket_service


def channel_discovery_dependency() -> Generator[ChannelDiscoveryService, None, None]:
    """FastAPI dependency for channel discovery service"""
    yield channel_discovery_service


def plugin_discovery_dependency() -> Generator[PluginDiscoveryService, None, None]:
    """FastAPI dependency for plugin discovery service"""
    yield plugin_discovery_service


def distribution_dependency() -> Generator[DistributionService, None, None]:
    """FastAPI dependency for distribution service"""
    yield distribution_service


def cache_dependency() -> Generator[CacheService, None, None]:
    """FastAPI dependency for cache service"""
    yield cache_service


def content_dependency() -> Generator[ContentService, None, None]:
    """FastAPI dependency for content service"""
    yield content_service
