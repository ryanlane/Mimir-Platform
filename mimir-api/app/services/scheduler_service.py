"""
Service for managing scheduled jobs and their execution
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..db.models import (
    SchedulerJob, SchedulerJobSceneAssignment, SchedulerExecution, Scene, FrequencyUnit
)
from ..schemas.scheduler import (
    SchedulerJobCreate, SchedulerJobUpdate, ExecutionStatus, TriggerReason
)
from .scheduler_math import (
    now_utc, compute_approx_seconds, next_fire_time, 
    calculate_next_run_with_backoff, is_job_due, is_job_locked,
    get_execution_duration_ms
)


class SchedulerService:
    """Service for managing scheduler jobs and executions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_job(self, job_data: SchedulerJobCreate) -> SchedulerJob:
        """Create a new scheduler job with scene assignments"""
        # Validate that all scenes exist
        existing_scenes = self.db.query(Scene).filter(
            Scene.id.in_(job_data.scene_ids)
        ).all()
        
        if len(existing_scenes) != len(job_data.scene_ids):
            missing_scenes = set(job_data.scene_ids) - {s.id for s in existing_scenes}
            raise ValueError(f"Scenes not found: {missing_scenes}")
        
        # Create the job
        job_id = str(uuid.uuid4())
        
        # Calculate initial next run time
        now = now_utc()
        next_run = now + timedelta(seconds=30)  # Start in 30 seconds for immediate testing
        
        job = SchedulerJob(
            id=job_id,
            name=job_data.name,
            description=job_data.description,
            enabled=job_data.enabled,
            freq_unit=job_data.freq_unit.value,
            freq_value=job_data.freq_value,
            approx_interval_seconds=compute_approx_seconds(
                job_data.freq_unit, 
                job_data.freq_value
            ),
            timezone_name=job_data.timezone_name,
            next_run_at=next_run,
            jitter_seconds=job_data.jitter_seconds,
            run_timeout_seconds=job_data.run_timeout_seconds,
            action_type=job_data.action_type.value,
            action_config=job_data.action_config or {}
        )
        
        self.db.add(job)
        self.db.flush()  # Get the job ID
        
        # Create scene assignments
        for scene_id in job_data.scene_ids:
            assignment = SchedulerJobSceneAssignment(
                id=str(uuid.uuid4()),
                job_id=job.id,
                scene_id=scene_id,
                refresh_method=job_data.refresh_method.value
            )
            self.db.add(assignment)
        
        self.db.commit()
        
        # Populate scene assignments on the returned job
        assignments = await self.get_job_assignments(job.id)
        job.scene_assignments = assignments
        
        return job
    
    async def update_job(self, job_id: str, updates: SchedulerJobUpdate) -> SchedulerJob:
        """Update an existing scheduler job"""
        job = self.db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Update basic fields
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(job, field):
                if field in ['freq_unit', 'action_type'] and hasattr(value, 'value'):
                    setattr(job, field, value.value)
                else:
                    setattr(job, field, value)
        
        # Recalculate next run if frequency changed
        if updates.freq_unit or updates.freq_value:
            job.next_run_at = next_fire_time(job)
            job.approx_interval_seconds = compute_approx_seconds(
                FrequencyUnit(job.freq_unit),
                job.freq_value
            )
        
        job.updated_at = now_utc()
        self.db.commit()
        
        # Populate scene assignments on the returned job
        assignments = await self.get_job_assignments(job.id)
        job.scene_assignments = assignments
        
        return job
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a scheduler job and all its assignments"""
        job = self.db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
        if not job:
            return False
        
        # Delete scene assignments first
        self.db.query(SchedulerJobSceneAssignment).filter(
            SchedulerJobSceneAssignment.job_id == job_id
        ).delete()
        
        # Delete execution history
        self.db.query(SchedulerExecution).filter(
            SchedulerExecution.job_id == job_id
        ).delete()
        
        # Delete the job
        self.db.delete(job)
        self.db.commit()
        return True
    
    async def add_scene_assignment(
        self, 
        job_id: str, 
        scene_id: str,
        refresh_method: str = "content_refresh",
        priority: int = 100
    ) -> SchedulerJobSceneAssignment:
        """Add a scene assignment to an existing job"""
        # Validate job and scene exist
        job = self.db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        scene = self.db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise ValueError(f"Scene {scene_id} not found")
        
        # Check if assignment already exists
        existing = self.db.query(SchedulerJobSceneAssignment).filter(
            and_(
                SchedulerJobSceneAssignment.job_id == job_id,
                SchedulerJobSceneAssignment.scene_id == scene_id
            )
        ).first()
        
        if existing:
            raise ValueError(f"Scene {scene_id} already assigned to job {job_id}")
        
        assignment = SchedulerJobSceneAssignment(
            id=str(uuid.uuid4()),
            job_id=job_id,
            scene_id=scene_id,
            refresh_method=refresh_method,
            priority=priority
        )
        
        self.db.add(assignment)
        self.db.commit()
        return assignment
    
    async def remove_scene_assignment(self, job_id: str, scene_id: str) -> bool:
        """Remove a scene assignment from a job"""
        assignment = self.db.query(SchedulerJobSceneAssignment).filter(
            and_(
                SchedulerJobSceneAssignment.job_id == job_id,
                SchedulerJobSceneAssignment.scene_id == scene_id
            )
        ).first()
        
        if not assignment:
            return False
        
        self.db.delete(assignment)
        self.db.commit()
        return True
    
    async def get_due_jobs(self, limit: int = 10) -> List[SchedulerJob]:
        """Get jobs that are due to run and not locked"""
        now = now_utc()
        
        return self.db.query(SchedulerJob).filter(
            and_(
                SchedulerJob.enabled == True,
                SchedulerJob.next_run_at <= now,
                or_(
                    SchedulerJob.locked_until.is_(None),
                    SchedulerJob.locked_until < now
                )
            )
        ).limit(limit).all()
    
    async def lock_job(self, job_id: str) -> bool:
        """Lock a job for execution"""
        job = self.db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
        if not job:
            return False
        
        now = now_utc()
        lock_until = now + timedelta(seconds=job.run_timeout_seconds)
        
        job.locked_until = lock_until
        self.db.commit()
        return True
    
    async def unlock_job(self, job_id: str) -> bool:
        """Unlock a job after execution"""
        job = self.db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
        if not job:
            return False
        
        job.locked_until = None
        self.db.commit()
        return True
    
    async def start_execution(
        self, 
        job_id: str, 
        worker_id: str,
        trigger_reason: TriggerReason = TriggerReason.SCHEDULED
    ) -> str:
        """Start a new execution for a job"""
        execution_id = str(uuid.uuid4())
        
        execution = SchedulerExecution(
            id=execution_id,
            job_id=job_id,
            started_at=now_utc(),
            status=ExecutionStatus.PENDING.value,
            worker_id=worker_id,
            trigger_reason=trigger_reason.value
        )
        
        self.db.add(execution)
        self.db.commit()
        return execution_id
    
    async def complete_execution(
        self,
        execution_id: str,
        status: ExecutionStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        affected_scenes: Optional[List[str]] = None
    ) -> bool:
        """Complete an execution with results"""
        execution = self.db.query(SchedulerExecution).filter(
            SchedulerExecution.id == execution_id
        ).first()
        
        if not execution:
            return False
        
        completed_at = now_utc()
        execution.completed_at = completed_at
        execution.status = status.value
        execution.output_data = output_data
        execution.error_message = error_message
        execution.affected_scenes = affected_scenes
        execution.execution_duration_ms = get_execution_duration_ms(
            execution.started_at, completed_at
        )
        
        # Update the job based on execution result
        job = self.db.query(SchedulerJob).filter(
            SchedulerJob.id == execution.job_id
        ).first()
        
        if job:
            if status == ExecutionStatus.SUCCESS:
                job.last_success_at = completed_at
                job.last_output = output_data
                job.consecutive_failures = 0
                job.last_error = None
                job.next_run_at = next_fire_time(job)
            else:
                job.consecutive_failures += 1
                job.last_error = error_message
                job.next_run_at = calculate_next_run_with_backoff(job)
            
            job.last_run_at = completed_at
        
        self.db.commit()
        return True
    
    async def get_job_assignments(self, job_id: str) -> List[SchedulerJobSceneAssignment]:
        """Get all scene assignments for a job"""
        return self.db.query(SchedulerJobSceneAssignment).filter(
            SchedulerJobSceneAssignment.job_id == job_id
        ).order_by(SchedulerJobSceneAssignment.priority).all()
    
    async def get_scene_assignments(self, scene_id: str) -> List[SchedulerJobSceneAssignment]:
        """Get all jobs assigned to a scene"""
        return self.db.query(SchedulerJobSceneAssignment).filter(
            SchedulerJobSceneAssignment.scene_id == scene_id
        ).order_by(SchedulerJobSceneAssignment.priority).all()
    
    async def get_execution_history(
        self, 
        job_id: str, 
        limit: int = 50,
        status_filter: Optional[ExecutionStatus] = None
    ) -> List[SchedulerExecution]:
        """Get execution history for a job"""
        query = self.db.query(SchedulerExecution).filter(
            SchedulerExecution.job_id == job_id
        )
        
        if status_filter:
            query = query.filter(SchedulerExecution.status == status_filter.value)
        
        return query.order_by(
            SchedulerExecution.started_at.desc()
        ).limit(limit).all()
    
    async def get_scheduler_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        total_jobs = self.db.query(SchedulerJob).count()
        enabled_jobs = self.db.query(SchedulerJob).filter(
            SchedulerJob.enabled == True
        ).count()
        
        now = now_utc()
        
        # Jobs due now
        jobs_due = self.db.query(SchedulerJob).filter(
            and_(
                SchedulerJob.enabled == True,
                SchedulerJob.next_run_at <= now
            )
        ).count()
        
        # Jobs locked
        jobs_locked = self.db.query(SchedulerJob).filter(
            and_(
                SchedulerJob.locked_until.isnot(None),
                SchedulerJob.locked_until > now
            )
        ).count()
        
        # Jobs with failures
        jobs_with_failures = self.db.query(SchedulerJob).filter(
            SchedulerJob.consecutive_failures > 0
        ).count()
        
        # Recent executions (last 24 hours)
        day_ago = now - timedelta(hours=24)
        recent_executions = self.db.query(SchedulerExecution).filter(
            SchedulerExecution.started_at >= day_ago
        ).count()
        
        # Success rate calculation
        success_rate = None
        if recent_executions > 0:
            successful_executions = self.db.query(SchedulerExecution).filter(
                and_(
                    SchedulerExecution.started_at >= day_ago,
                    SchedulerExecution.status == ExecutionStatus.SUCCESS.value
                )
            ).count()
            success_rate = (successful_executions / recent_executions) * 100
        
        return {
            "total_jobs": total_jobs,
            "enabled_jobs": enabled_jobs,
            "disabled_jobs": total_jobs - enabled_jobs,
            "jobs_due_now": jobs_due,
            "jobs_locked": jobs_locked,
            "jobs_with_failures": jobs_with_failures,
            "recent_executions": recent_executions,
            "success_rate_24h": success_rate
        }