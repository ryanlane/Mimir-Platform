"""
Display-Scene relationship schemas
Enhanced schemas for managing display-scene assignments
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.common import TimestampMixin


class DisplaySceneAssignment(BaseModel):
    """Enhanced scene assignment for displays"""
    scene_id: str = Field(alias="sceneId")
    override_settings: Optional[Dict[str, Any]] = Field(None, alias="overrideSettings")
    priority: Optional[int] = 1  # Priority for bulk assignments
    
    class Config:
        populate_by_name = True


class DisplaySceneResponse(BaseModel):
    """Response schema for display-scene assignment"""
    display_id: str = Field(alias="displayId")
    display_name: str = Field(alias="displayName")
    scene_id: Optional[str] = Field(None, alias="sceneId") 
    scene_name: Optional[str] = Field(None, alias="sceneName")
    assigned_at: Optional[datetime] = Field(None, alias="assignedAt")
    is_active: bool = Field(alias="isActive")
    override_settings: Optional[Dict[str, Any]] = Field(None, alias="overrideSettings")
    
    class Config:
        populate_by_name = True


class SceneDisplayStats(BaseModel):
    """Statistics about displays assigned to a scene"""
    total_assigned: int = Field(alias="totalAssigned")
    online_displays: int = Field(alias="onlineDisplays")
    offline_displays: int = Field(alias="offlineDisplays")
    last_updated: Optional[datetime] = Field(None, alias="lastUpdated")
    
    class Config:
        populate_by_name = True


class SceneWithDisplays(BaseModel):
    """Scene response with display assignment information"""
    id: str
    name: str
    channels: List[Dict[str, Any]]
    overlay: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None
    distribution_mode: Optional[str] = Field("MIRROR", alias="distributionMode")
    is_active: bool = Field(alias="isActive")
    display_stats: SceneDisplayStats = Field(alias="displayStats")
    assigned_displays: List[DisplaySceneResponse] = Field(alias="assignedDisplays")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    
    class Config:
        populate_by_name = True


class BulkSceneAssignment(BaseModel):
    """Bulk scene assignment to multiple displays"""
    display_ids: List[str] = Field(alias="displayIds")
    scene_id: str = Field(alias="sceneId")
    override_previous: bool = Field(True, alias="overridePrevious")
    
    class Config:
        populate_by_name = True


class BulkAssignmentResult(BaseModel):
    """Result of bulk scene assignment"""
    successful_assignments: List[str] = Field(alias="successfulAssignments")
    failed_assignments: List[Dict[str, str]] = Field(alias="failedAssignments")
    total_processed: int = Field(alias="totalProcessed")
    success_count: int = Field(alias="successCount")
    error_count: int = Field(alias="errorCount")
    
    class Config:
        populate_by_name = True


class DisplayLocationGroup(BaseModel):
    """Group displays by location for batch operations"""
    location: str
    display_count: int = Field(alias="displayCount")
    displays: List[DisplaySceneResponse]
    assigned_scene: Optional[str] = Field(None, alias="assignedScene")
    
    class Config:
        populate_by_name = True


class SceneActivationStatus(BaseModel):
    """Status of scene activation across displays"""
    scene_id: str = Field(alias="sceneId")
    scene_name: str = Field(alias="sceneName")
    target_displays: List[str] = Field(alias="targetDisplays")
    activated_displays: List[str] = Field(alias="activatedDisplays")
    failed_displays: List[str] = Field(alias="failedDisplays")
    activation_timestamp: datetime = Field(alias="activationTimestamp")
    
    class Config:
        populate_by_name = True


class DisplayContentStatus(BaseModel):
    """Current content status for a display"""
    display_id: str = Field(alias="displayId")
    current_scene_id: Optional[str] = Field(None, alias="currentSceneId")
    content_hash: Optional[str] = Field(None, alias="contentHash")
    last_content_update: Optional[datetime] = Field(None, alias="lastContentUpdate")
    sync_status: str = "unknown"  # "synced", "pending", "error", "unknown"
    
    class Config:
        populate_by_name = True
