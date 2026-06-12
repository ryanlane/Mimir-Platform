"""
Admin endpoints for monitoring system status and background jobs
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.core.scheduler import scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
async def health_check():
    """Health check endpoint for admin monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scheduler_running": scheduler_service.is_running() if scheduler_service else False
    }


@router.get("/jobs")
async def list_jobs():
    """List all scheduled jobs with their status"""
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not available"
        )

    try:
        jobs = []
        for job in scheduler_service.scheduler.get_jobs():
            job_info = {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "max_instances": job.max_instances,
                "misfire_grace_time": job.misfire_grace_time,
                "coalesce": job.coalesce,
                "executor": job.executor,
                "pending": job.pending
            }
            jobs.append(job_info)

        return {
            "jobs": jobs,
            "total_jobs": len(jobs),
            "scheduler_state": scheduler_service.scheduler.state
        }
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving jobs: {str(e)}"
        ) from e


@router.get("/jobs/{job_id}")
async def get_job_details(job_id: str):
    """Get detailed information about a specific job"""
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not available"
        )

    try:
        job = scheduler_service.scheduler.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        return {
            "id": job.id,
            "name": job.name,
            "func": f"{job.func.__module__}.{job.func.__name__}",
            "trigger": str(job.trigger),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "max_instances": job.max_instances,
            "misfire_grace_time": job.misfire_grace_time,
            "coalesce": job.coalesce,
            "executor": job.executor,
            "pending": job.pending,
            "args": job.args,
            "kwargs": job.kwargs
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving job: {str(e)}"
        ) from e


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str):
    """Manually trigger a job to run immediately"""
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not available"
        )

    try:
        job = scheduler_service.scheduler.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        # Schedule the job to run immediately
        scheduler_service.scheduler.modify_job(job_id, next_run_time=datetime.now(timezone.utc))

        return {
            "message": f"Job {job_id} scheduled to run immediately",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error running job: {str(e)}"
        ) from e


@router.delete("/jobs/{job_id}")
async def pause_job(job_id: str):
    """Pause a scheduled job"""
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not available"
        )

    try:
        job = scheduler_service.scheduler.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        scheduler_service.scheduler.pause_job(job_id)

        return {
            "message": f"Job {job_id} paused",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausing job: {str(e)}"
        ) from e


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """Resume a paused job"""
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not available"
        )

    try:
        job = scheduler_service.scheduler.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        scheduler_service.scheduler.resume_job(job_id)

        return {
            "message": f"Job {job_id} resumed",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming job: {str(e)}"
        ) from e


@router.get("/scheduler/status")
async def scheduler_status():
    """Get detailed scheduler status and statistics"""
    if not scheduler_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not available"
        )

    try:
        scheduler = scheduler_service.scheduler
        jobs = scheduler.get_jobs()

        # Count jobs by state
        running_jobs = [j for j in jobs if j.next_run_time is not None]
        paused_jobs = [j for j in jobs if j.next_run_time is None]

        return {
            "scheduler_state": scheduler.state,
            "running": scheduler.running,
            "total_jobs": len(jobs),
            "running_jobs": len(running_jobs),
            "paused_jobs": len(paused_jobs),
            "executors": list(scheduler._executors.keys()),
            "job_stores": list(scheduler._jobstores.keys()),
            "timezone": str(scheduler.timezone),
            "uptime_seconds": (
                datetime.now(timezone.utc) - scheduler_service._start_time
            ).total_seconds() if hasattr(scheduler_service, '_start_time') else 0
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving scheduler status: {str(e)}"
        ) from e
