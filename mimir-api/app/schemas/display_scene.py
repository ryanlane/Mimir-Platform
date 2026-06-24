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
Display-Scene relationship schemas
Enhanced schemas for managing display-scene assignments
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DisplaySceneAssignment(BaseModel):
    """Enhanced scene assignment for displays"""
    scene_id: str = Field(alias="sceneId")
    override_settings: dict[str, Any] | None = Field(None, alias="overrideSettings")
    priority: int | None = 1  # Priority for bulk assignments

    class Config:
        populate_by_name = True


class DisplaySceneResponse(BaseModel):
    """Response schema for display-scene assignment"""
    display_id: str = Field(alias="displayId")
    display_name: str = Field(alias="displayName")
    scene_id: str | None = Field(None, alias="sceneId")
    scene_name: str | None = Field(None, alias="sceneName")
    assigned_at: datetime | None = Field(None, alias="assignedAt")
    is_active: bool = Field(alias="isActive")
    override_settings: dict[str, Any] | None = Field(None, alias="overrideSettings")

    class Config:
        populate_by_name = True


class SceneDisplayStats(BaseModel):
    """Statistics about displays assigned to a scene"""
    total_assigned: int = Field(alias="totalAssigned")
    online_displays: int = Field(alias="onlineDisplays")
    offline_displays: int = Field(alias="offlineDisplays")
    last_updated: datetime | None = Field(None, alias="lastUpdated")

    class Config:
        populate_by_name = True


class SceneWithDisplays(BaseModel):
    """Scene response with display assignment information"""
    id: str
    name: str
    channels: list[dict[str, Any]]
    overlay: dict[str, Any] | None = None
    schedule: dict[str, Any] | None = None
    distribution_mode: str | None = Field("MIRROR", alias="distributionMode")
    is_active: bool = Field(alias="isActive")
    display_stats: SceneDisplayStats = Field(alias="displayStats")
    assigned_displays: list[DisplaySceneResponse] = Field(alias="assignedDisplays")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    class Config:
        populate_by_name = True


class BulkSceneAssignment(BaseModel):
    """Bulk scene assignment to multiple displays"""
    display_ids: list[str] = Field(alias="displayIds")
    scene_id: str = Field(alias="sceneId")
    override_previous: bool = Field(True, alias="overridePrevious")

    class Config:
        populate_by_name = True


class BulkAssignmentResult(BaseModel):
    """Result of bulk scene assignment"""
    successful_assignments: list[str] = Field(alias="successfulAssignments")
    failed_assignments: list[dict[str, str]] = Field(alias="failedAssignments")
    total_processed: int = Field(alias="totalProcessed")
    success_count: int = Field(alias="successCount")
    error_count: int = Field(alias="errorCount")

    class Config:
        populate_by_name = True


class DisplayLocationGroup(BaseModel):
    """Group displays by location for batch operations"""
    location: str
    display_count: int = Field(alias="displayCount")
    displays: list[DisplaySceneResponse]
    assigned_scene: str | None = Field(None, alias="assignedScene")

    class Config:
        populate_by_name = True


class SceneActivationStatus(BaseModel):
    """Status of scene activation across displays"""
    scene_id: str = Field(alias="sceneId")
    scene_name: str = Field(alias="sceneName")
    target_displays: list[str] = Field(alias="targetDisplays")
    activated_displays: list[str] = Field(alias="activatedDisplays")
    failed_displays: list[str] = Field(alias="failedDisplays")
    activation_timestamp: datetime = Field(alias="activationTimestamp")

    class Config:
        populate_by_name = True


class DisplayContentStatus(BaseModel):
    """Current content status for a display"""
    display_id: str = Field(alias="displayId")
    current_scene_id: str | None = Field(None, alias="currentSceneId")
    content_hash: str | None = Field(None, alias="contentHash")
    last_content_update: datetime | None = Field(None, alias="lastContentUpdate")
    sync_status: str = "unknown"  # "synced", "pending", "error", "unknown"

    class Config:
        populate_by_name = True
