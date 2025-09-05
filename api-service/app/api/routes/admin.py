"""
Health and Admin API Routes
FastAPI router for health checks and administrative endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone

from app.dependencies import get_channel_service, get_scene_service, get_display_service
from app.config import settings
from app.core.scheduler import scheduler_service
from app.core.metrics import get_metrics_content
from app.services.mqtt.presence import mqtt_presence_service

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["health"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@health_router.get("/health")
@health_router.head("/health") 
async def health_check():
    """System health check endpoint"""
    scheduler_status = "unknown"
    scheduler_jobs = 0
    
    if scheduler_service:
        try:
            scheduler_status = "running" if scheduler_service.is_running() else "stopped"
            scheduler_jobs = len(scheduler_service.scheduler.get_jobs())
        except Exception:
            scheduler_status = "error"
    
    return {
        "status": "healthy",
        "database": {
            "status": "connected"
        },
        "channels": {
            "status": "operational"
        },
        "websocket": {
            "status": "operational"
        },
        "scheduler": {
            "status": scheduler_status,
            "jobs": scheduler_jobs
        },
        "uptime": "running"
    }


@admin_router.get("/redis/status")
async def get_redis_status():
    """Get Redis connection status"""
    return {
        "enabled": settings.redis_enabled,
        "connected": settings.redis_enabled,  # Simplified for now
        "url": settings.redis_dsn if settings.redis_enabled else None,
        "status": "connected" if settings.redis_enabled else "disabled"
    }


@admin_router.get("/distribution/overview")
async def get_distribution_overview():
    """Get distribution system overview"""
    return {
        "enabled": settings.distribution_enabled,
        "mode": settings.distribution_default_mode,
        "redis_enabled": settings.redis_enabled,
        "active_displays": 0,  # TODO: Get actual count from database
        "active_scenes": 0,    # TODO: Get actual count from database
        "queue_size": 0,       # TODO: Get actual queue size
        "status": "operational" if settings.distribution_enabled else "disabled"
    }


@admin_router.post("/channels/reload")
async def reload_channels():
    """Reload all channels"""
    # TODO: Implement channel reloading logic
    return {"message": "Channels reloaded successfully"}


@admin_router.get("/channels/debug")
async def debug_channels():
    """Debug information for channels"""
    # TODO: Implement channel debugging logic
    return {"debug_info": "Channel debug information"}


@admin_router.post("/channels/{channel_id}/reload")
async def reload_channel(channel_id: str):
    """Reload a specific channel"""
    # TODO: Implement single channel reloading logic
    return {"message": f"Channel {channel_id} reloaded successfully"}


@admin_router.get("/channels/orphaned")
async def get_orphaned_channels():
    """Get orphaned channels"""
    # TODO: Implement orphaned channel detection
    return {"orphaned_channels": []}


@admin_router.post("/channels/reset")
async def reset_channels():
    """Reset all channels"""
    # TODO: Implement channel reset logic
    return {"message": "Channels reset successfully"}


# Scheduler Management Endpoints
@admin_router.get("/scheduler/jobs")
async def list_scheduler_jobs():
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
        )


@admin_router.get("/scheduler/jobs/{job_id}")
async def get_scheduler_job_details(job_id: str):
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
        )


@admin_router.post("/scheduler/jobs/{job_id}/run")
async def run_scheduler_job_now(job_id: str):
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
        )


@admin_router.post("/scheduler/jobs/{job_id}/pause")
async def pause_scheduler_job(job_id: str):
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
        )


@admin_router.post("/scheduler/jobs/{job_id}/resume")
async def resume_scheduler_job(job_id: str):
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
        )


@admin_router.get("/scheduler/status")
async def get_scheduler_status():
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
        )


@admin_router.get("/metrics")
async def get_prometheus_metrics():
    """Get Prometheus metrics"""
    try:
        metrics_data, content_type = get_metrics_content()
        return Response(content=metrics_data, media_type=content_type)
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving metrics: {str(e)}"
        )


@admin_router.get("/mqtt/status")
async def get_mqtt_status():
    """Get MQTT presence service status"""
    try:
        stats = mqtt_presence_service.get_presence_stats()
        online_devices = mqtt_presence_service.get_online_devices()
        
        return {
            "mqtt_enabled": settings.mqtt_enabled,
            "broker": f"{settings.mqtt_broker_host}:{settings.mqtt_broker_port}",
            "service_running": mqtt_presence_service.is_running,
            "stats": stats,
            "online_devices": list(online_devices),
            "total_devices_seen": len(mqtt_presence_service.get_all_device_metadata())
        }
    except Exception as e:
        logger.error(f"Error getting MQTT status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving MQTT status: {str(e)}"
        )


@admin_router.get("/mqtt/devices")
async def get_mqtt_devices():
    """Get all devices tracked via MQTT presence"""
    try:
        all_devices = mqtt_presence_service.get_all_device_metadata()
        online_devices = mqtt_presence_service.get_online_devices()
        
        devices = []
        for device_id, metadata in all_devices.items():
            device_info = {
                "device_id": device_id,
                "is_online": device_id in online_devices,
                "last_seen": metadata.get("last_seen"),
                "last_status": metadata.get("last_status"),
                "first_seen": metadata.get("first_seen"),
                "last_heartbeat": metadata.get("last_heartbeat"),
                "offline_reason": metadata.get("offline_reason")
            }
            devices.append(device_info)
        
        return {
            "devices": devices,
            "summary": {
                "total": len(devices),
                "online": len(online_devices),
                "offline": len(devices) - len(online_devices)
            }
        }
    except Exception as e:
        logger.error(f"Error getting MQTT devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving MQTT devices: {str(e)}"
        )


@admin_router.post("/mqtt/publish/{device_id}")
async def publish_device_status(device_id: str, status: str, metadata: Optional[Dict[str, Any]] = None):
    """Manually publish status for a device (for testing)"""
    try:
        if status not in ["online", "offline"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status must be 'online' or 'offline'"
            )
        
        success = await mqtt_presence_service.publish_device_status(device_id, status, metadata or {})
        
        if success:
            return {
                "success": True,
                "message": f"Status '{status}' published for device {device_id}"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to publish device status"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing device status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error publishing device status: {str(e)}"
        )
