"""
Scheduler-related schemas for API requests and responses
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

from .common import TimestampMixin


class FrequencyUnit(str, Enum):
    """Available frequency units for scheduling"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class ActionType(str, Enum):
    """Types of actions a scheduler job can perform"""
    REFRESH_SCENE = "refresh_scene"
    WEBHOOK = "webhook"
    CUSTOM = "custom"


class RefreshMethod(str, Enum):
    """Methods for refreshing scene content"""
    CONTENT_REFRESH = "content_refresh"
    FULL_RELOAD = "full_reload"


class TriggerReason(str, Enum):
    """Reasons for triggering a scheduler job"""
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    RETRY = "retry"


class ExecutionStatus(str, Enum):
    """Execution status values"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SchedulerJobBase(BaseModel):
    """Base scheduler job schema"""
    name: str = Field(..., description="Human-readable job name")
    description: Optional[str] = Field(None, description="Job description")
    enabled: bool = Field(True, description="Whether the job is enabled")
    freq_unit: FrequencyUnit = Field(..., description="Frequency unit")
    freq_value: int = Field(..., ge=1, description="Frequency value (e.g., 5 for '5 minutes')")
    timezone_name: Optional[str] = Field(None, description="Timezone for scheduling")
    jitter_seconds: int = Field(15, ge=0, le=300, description="Jitter to add to schedule")
    run_timeout_seconds: int = Field(90, ge=10, le=3600, description="Execution timeout")
    action_type: ActionType = Field(ActionType.REFRESH_SCENE, description="Type of action to perform")
    action_config: Optional[Dict[str, Any]] = Field(None, description="Action-specific configuration")


class SchedulerJobCreate(SchedulerJobBase):
    """Schema for creating scheduler jobs"""
    scene_ids: List[str] = Field(..., description="Scene IDs to associate with this job")
    refresh_method: RefreshMethod = Field(RefreshMethod.CONTENT_REFRESH, description="How to refresh scenes")


class SchedulerJobUpdate(BaseModel):
    """Schema for updating scheduler jobs"""
    name: Optional[str] = Field(None, description="Human-readable job name")
    description: Optional[str] = Field(None, description="Job description")
    enabled: Optional[bool] = Field(None, description="Whether the job is enabled")
    freq_unit: Optional[FrequencyUnit] = Field(None, description="Frequency unit")
    freq_value: Optional[int] = Field(None, ge=1, description="Frequency value")
    timezone_name: Optional[str] = Field(None, description="Timezone for scheduling")
    jitter_seconds: Optional[int] = Field(None, ge=0, le=300, description="Jitter to add")
    run_timeout_seconds: Optional[int] = Field(None, ge=10, le=3600, description="Execution timeout")
    action_type: Optional[ActionType] = Field(None, description="Type of action to perform")
    action_config: Optional[Dict[str, Any]] = Field(None, description="Action-specific configuration")


class SceneAssignmentCreate(BaseModel):
    """Schema for creating scene assignments"""
    scene_id: str = Field(..., description="Scene ID to assign")
    refresh_method: RefreshMethod = Field(RefreshMethod.CONTENT_REFRESH, description="How to refresh scene")
    priority: int = Field(100, ge=1, le=1000, description="Assignment priority")


class SceneAssignmentUpdate(BaseModel):
    """Schema for updating scene assignments"""
    refresh_method: Optional[RefreshMethod] = Field(None, description="How to refresh scene")
    priority: Optional[int] = Field(None, ge=1, le=1000, description="Assignment priority")


class SceneAssignmentResponse(BaseModel):
    """Schema for scene assignment responses"""
    id: str
    job_id: str
    scene_id: str
    refresh_method: RefreshMethod
    priority: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class SchedulerJobResponse(SchedulerJobBase, TimestampMixin):
    """Schema for scheduler job responses"""
    id: str
    next_run_at: datetime
    last_run_at: Optional[datetime] = None
    locked_until: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    last_success_at: Optional[datetime] = None
    approx_interval_seconds: Optional[int] = None
    last_output: Optional[Dict[str, Any]] = None
    scene_assignments: List[SceneAssignmentResponse] = []
    
    class Config:
        from_attributes = True


class SchedulerExecutionResponse(BaseModel):
    """Schema for execution history responses"""
    id: str
    job_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: ExecutionStatus
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_duration_ms: Optional[int] = None
    affected_scenes: Optional[List[str]] = None
    worker_id: Optional[str] = None
    trigger_reason: TriggerReason = TriggerReason.SCHEDULED
    
    class Config:
        from_attributes = True


class SchedulerJobStatusResponse(BaseModel):
    """Detailed status response for a scheduler job"""
    job: SchedulerJobResponse
    recent_executions: List[SchedulerExecutionResponse]
    is_due: bool
    is_locked: bool
    next_execution_estimate: Optional[datetime] = None


class SchedulerJobListResponse(BaseModel):
    """Response for listing scheduler jobs"""
    jobs: List[SchedulerJobResponse]
    total: int
    limit: int
    offset: int


class ManualTriggerRequest(BaseModel):
    """Request to manually trigger a scheduler job"""
    force: bool = Field(False, description="Force execution even if job is disabled")
    trigger_reason: TriggerReason = Field(TriggerReason.MANUAL, description="Reason for manual trigger")


class ManualTriggerResponse(BaseModel):
    """Response for manual job trigger"""
    execution_id: str
    job_id: str
    triggered_at: datetime
    message: str


class SchedulerStatsResponse(BaseModel):
    """Response with scheduler statistics"""
    total_jobs: int
    enabled_jobs: int
    disabled_jobs: int
    jobs_due_now: int
    jobs_locked: int
    jobs_with_failures: int
    recent_executions: int
    success_rate_24h: Optional[float] = None


class BulkJobOperationRequest(BaseModel):
    """Request for bulk operations on scheduler jobs"""
    job_ids: List[str] = Field(..., description="List of job IDs to operate on")
    operation: str = Field(..., description="Operation to perform: enable, disable, trigger")
    force: bool = Field(False, description="Force trigger even if job disabled/locked (trigger op only)")
    immediate: bool = Field(True, description="Execute trigger immediately instead of just scheduling (trigger op only)")


class BulkJobOperationResponse(BaseModel):
    """Response for bulk job operations"""
    successful_jobs: List[str]
    failed_jobs: List[Dict[str, str]]  # job_id -> error_message
    total_processed: int
    message: str