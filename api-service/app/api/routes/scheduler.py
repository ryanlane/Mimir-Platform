"""
API endpoints for scheduler management
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.models import SchedulerJob, SchedulerExecution
from app.schemas.scheduler import (
    SchedulerJobCreate, SchedulerJobUpdate, SchedulerJobResponse,
    SchedulerJobListResponse, SchedulerJobStatusResponse,
    ManualTriggerRequest, ManualTriggerResponse,
    SceneAssignmentCreate, SceneAssignmentUpdate, SceneAssignmentResponse,
    SchedulerStatsResponse, BulkJobOperationRequest, BulkJobOperationResponse,
    ExecutionStatus, TriggerReason
)
from app.services.scheduler_service import SchedulerService
from app.services.scheduler_math import now_utc, is_job_due, is_job_locked

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/jobs", response_model=SchedulerJobResponse)
async def create_scheduler_job(
    job_data: SchedulerJobCreate,
    db: Session = Depends(get_db)
):
    """Create a new scheduler job with scene assignments"""
    service = SchedulerService(db)
    
    try:
        job = await service.create_job(job_data)
        return job
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs", response_model=SchedulerJobListResponse)
async def list_scheduler_jobs(
    enabled_only: bool = Query(True, description="Only return enabled jobs"),
    limit: int = Query(50, ge=1, le=200, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    db: Session = Depends(get_db)
):
    """List scheduler jobs with pagination"""
    query = db.query(SchedulerJob)
    
    if enabled_only:
        query = query.filter(SchedulerJob.enabled == True)
    
    total = query.count()
    jobs = query.offset(offset).limit(limit).all()
    
    return SchedulerJobListResponse(
        jobs=jobs,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/jobs/{job_id}", response_model=SchedulerJobResponse)
async def get_scheduler_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific scheduler job by ID"""
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Scheduler job not found")
    
    return job


@router.put("/jobs/{job_id}", response_model=SchedulerJobResponse)
async def update_scheduler_job(
    job_id: str,
    updates: SchedulerJobUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing scheduler job"""
    service = SchedulerService(db)
    
    try:
        job = await service.update_job(job_id, updates)
        return job
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/jobs/{job_id}")
async def delete_scheduler_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Delete a scheduler job"""
    service = SchedulerService(db)
    
    success = await service.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scheduler job not found")
    
    return {"message": f"Scheduler job {job_id} deleted successfully"}


@router.get("/jobs/{job_id}/status", response_model=SchedulerJobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed status and recent execution history for a job"""
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Scheduler job not found")
    
    service = SchedulerService(db)
    recent_executions = await service.get_execution_history(job_id, limit=10)
    
    return SchedulerJobStatusResponse(
        job=job,
        recent_executions=recent_executions,
        is_due=is_job_due(job),
        is_locked=is_job_locked(job),
        next_execution_estimate=job.next_run_at
    )


@router.post("/jobs/{job_id}/scenes", response_model=SceneAssignmentResponse)
async def add_scene_to_job(
    job_id: str,
    assignment_data: SceneAssignmentCreate,
    db: Session = Depends(get_db)
):
    """Add a scene assignment to an existing job"""
    service = SchedulerService(db)
    
    try:
        assignment = await service.add_scene_assignment(
            job_id,
            assignment_data.scene_id,
            assignment_data.refresh_method.value,
            assignment_data.priority
        )
        return assignment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/jobs/{job_id}/scenes/{scene_id}")
async def remove_scene_from_job(
    job_id: str,
    scene_id: str,
    db: Session = Depends(get_db)
):
    """Remove a scene assignment from a job"""
    service = SchedulerService(db)
    
    success = await service.remove_scene_assignment(job_id, scene_id)
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"Scene assignment not found for job {job_id} and scene {scene_id}"
        )
    
    return {"message": f"Scene {scene_id} removed from job {job_id}"}


@router.get("/jobs/{job_id}/scenes", response_model=List[SceneAssignmentResponse])
async def get_job_scene_assignments(
    job_id: str,
    db: Session = Depends(get_db)
):
    """Get all scene assignments for a job"""
    # Verify job exists
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Scheduler job not found")
    
    service = SchedulerService(db)
    assignments = await service.get_job_assignments(job_id)
    return assignments


@router.post("/jobs/{job_id}/trigger", response_model=ManualTriggerResponse)
async def trigger_job_manually(
    job_id: str,
    trigger_data: ManualTriggerRequest,
    db: Session = Depends(get_db)
):
    """Manually trigger a scheduler job execution"""
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Scheduler job not found")
    
    if not job.enabled and not trigger_data.force:
        raise HTTPException(
            status_code=400, 
            detail="Job is disabled. Use force=true to override."
        )
    
    if is_job_locked(job) and not trigger_data.force:
        raise HTTPException(
            status_code=400,
            detail="Job is currently locked. Use force=true to override."
        )
    
    # Start execution record
    service = SchedulerService(db)
    execution_id = await service.start_execution(
        job_id, 
        worker_id="manual-trigger",
        trigger_reason=trigger_data.trigger_reason
    )
    
    # TODO: Queue the job for immediate execution by the worker
    # This would integrate with your worker system
    
    return ManualTriggerResponse(
        execution_id=execution_id,
        job_id=job_id,
        triggered_at=now_utc(),
        message="Job queued for manual execution"
    )


@router.get("/jobs/{job_id}/executions")
async def get_job_executions(
    job_id: str,
    limit: int = Query(50, ge=1, le=200, description="Number of executions to return"),
    status_filter: Optional[ExecutionStatus] = Query(None, description="Filter by execution status"),
    db: Session = Depends(get_db)
):
    """Get execution history for a job"""
    # Verify job exists
    job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Scheduler job not found")
    
    service = SchedulerService(db)
    executions = await service.get_execution_history(job_id, limit, status_filter)
    return executions


@router.get("/stats", response_model=SchedulerStatsResponse)
async def get_scheduler_stats(
    db: Session = Depends(get_db)
):
    """Get scheduler statistics"""
    service = SchedulerService(db)
    stats = await service.get_scheduler_stats()
    return SchedulerStatsResponse(**stats)


@router.get("/jobs/due-now")
async def get_due_jobs(
    limit: int = Query(10, ge=1, le=50, description="Maximum jobs to return"),
    db: Session = Depends(get_db)
):
    """Get jobs that are currently due to run (for worker consumption)"""
    service = SchedulerService(db)
    due_jobs = await service.get_due_jobs(limit)
    return {"due_jobs": due_jobs, "count": len(due_jobs)}


@router.post("/jobs/bulk-operation", response_model=BulkJobOperationResponse)
async def bulk_job_operation(
    operation_data: BulkJobOperationRequest,
    db: Session = Depends(get_db)
):
    """Perform bulk operations on multiple scheduler jobs"""
    service = SchedulerService(db)
    successful_jobs = []
    failed_jobs = []
    
    for job_id in operation_data.job_ids:
        try:
            job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
            if not job:
                failed_jobs.append({"job_id": job_id, "error": "Job not found"})
                continue
            
            if operation_data.operation == "enable":
                job.enabled = True
            elif operation_data.operation == "disable":
                job.enabled = False
            elif operation_data.operation == "trigger":
                if job.enabled or operation_data.get("force", False):
                    execution_id = await service.start_execution(
                        job_id,
                        worker_id="bulk-trigger",
                        trigger_reason=TriggerReason.MANUAL
                    )
                    # TODO: Queue for execution
                else:
                    failed_jobs.append({"job_id": job_id, "error": "Job is disabled"})
                    continue
            else:
                failed_jobs.append({"job_id": job_id, "error": f"Unknown operation: {operation_data.operation}"})
                continue
            
            successful_jobs.append(job_id)
            
        except Exception as e:
            failed_jobs.append({"job_id": job_id, "error": str(e)})
    
    db.commit()
    
    return BulkJobOperationResponse(
        successful_jobs=successful_jobs,
        failed_jobs=failed_jobs,
        total_processed=len(operation_data.job_ids),
        message=f"Bulk {operation_data.operation} completed: {len(successful_jobs)} successful, {len(failed_jobs)} failed"
    )


@router.get("/scenes/{scene_id}/jobs", response_model=List[SceneAssignmentResponse])
async def get_scene_scheduler_jobs(
    scene_id: str,
    db: Session = Depends(get_db)
):
    """Get all scheduler jobs assigned to a specific scene"""
    # Verify scene exists
    from ...db.models import Scene
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    service = SchedulerService(db)
    assignments = await service.get_scene_assignments(scene_id)
    return assignments