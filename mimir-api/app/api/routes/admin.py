"""
Health and Admin API Routes
FastAPI router for health checks and administrative endpoints
"""
import io
import logging
import os
import socket
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.metrics import get_metrics_content
from app.core.scheduler import scheduler_service
from app.db.base import SessionLocal
from app.db.models import DisplaySceneImage
from app.services.display_image_persistence import DisplayImagePersistenceService
from app.services.image_swap import list_scene_swap, prune_swap, swap_summary
from app.services.mqtt.presence import mqtt_presence_service
from app.services.plugin_manager import plugin_manager_service

logger = logging.getLogger(__name__)

health_router = APIRouter(tags=["health"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Sensitive key substrings to redact
SENSITIVE_SUBSTRINGS = [
    'SECRET', 'PASSWORD', 'TOKEN', 'KEY', 'PASS', 'API_KEY', 'AUTH', 'CLIENT_SECRET'
]

def _should_redact(key: str) -> bool:
    upper = key.upper()
    return any(part in upper for part in SENSITIVE_SUBSTRINGS)


class MqttTestRequest(BaseModel):
    url: str | None = Field(None, description="MQTT broker URL (e.g., mqtt://host:1883)")
    host: str | None = Field(None, description="MQTT broker host override")
    port: int | None = Field(None, description="MQTT broker port override")
    timeout_ms: int | None = Field(3000, description="Connection timeout in ms")


@admin_router.post("/mqtt/test")
async def test_mqtt_broker(req: MqttTestRequest):
    """Test TCP connectivity to an MQTT broker host/port."""
    host = req.host
    port: int | None = req.port

    raw_url = (req.url or "").strip()
    if raw_url:
        # Allow host:port without scheme
        if "://" not in raw_url:
            trimmed = raw_url.split("/")[0]
            if ":" in trimmed:
                host_part, port_part = trimmed.rsplit(":", 1)
                host = host or (host_part.strip() or None)
                if port is None and port_part.isdigit():
                    port = int(port_part)
            else:
                host = host or trimmed
        else:
            parsed = urlparse(raw_url)
            host = host or parsed.hostname
            if port is None:
                if parsed.port:
                    port = parsed.port
                elif parsed.scheme in ("mqtts", "ssl", "tls"):
                    port = 8883
                elif parsed.scheme in ("mqtt", "tcp"):
                    port = 1883

    if not host:
        host = settings.mqtt_public_host or settings.mqtt_broker_host
    if port is None:
        port = settings.mqtt_public_port or settings.mqtt_broker_port

    if not host or not port:
        raise HTTPException(status_code=400, detail="MQTT host/port could not be resolved")

    timeout = max(0.5, float(req.timeout_ms or 3000) / 1000.0)
    start = time.monotonic()
    try:
        conn = socket.create_connection((host, int(port)), timeout=timeout)
        conn.close()
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "host": host,
            "port": int(port),
            "message": f"Connection failed: {exc}",
        }
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return {
        "success": True,
        "host": host,
        "port": int(port),
        "latency_ms": elapsed_ms,
        "message": f"Connected in {elapsed_ms}ms",
    }

@lru_cache(maxsize=1)
def _candidate_env_files() -> list[dict[str, Any]]:
    """Return metadata about likely environment files for diagnostics."""
    paths = [
        '/etc/mimir/mimir-api.env',
        '/etc/mimir/.env',
        '/var/opt/mimir/mimir-api/.env',
        '.env'
    ]
    result: list[dict[str, Any]] = []
    for p in paths:
        try:
            exists = os.path.exists(p)
            size = os.path.getsize(p) if exists else None
            result.append({
                'path': p,
                'exists': exists,
                'size_bytes': size
            })
        except Exception as e:  # noqa: BLE001
            result.append({'path': p, 'exists': False, 'error': str(e)})
    return result

@admin_router.get('/config/env', summary='Inspect effective environment & settings')
async def get_environment_config(include_values: bool = True, expose_secrets: bool = False):
    """Diagnostic endpoint: Show effective application settings & environment variables.

    WARNING: This endpoint is intended for administrative debugging. By default
    sensitive values (passwords, tokens, secrets) are redacted. To attempt to
    expose full values (NOT RECOMMENDED in production), pass `expose_secrets=true`.

    Query Params:
      - include_values: bool (default True) include setting/env values (redacted as needed)
      - expose_secrets: bool (default False) if True AND settings.debug=True, secrets will be shown.
        If debug is False this flag is ignored for safety.
    """
    # Build settings dump via pydantic model export
    try:
        settings_dict = settings.model_dump()
    except Exception:  # Fallback if model_dump unavailable
        settings_dict = settings.__dict__

    debug_mode = getattr(settings, 'debug', False)
    allow_full = bool(expose_secrets and debug_mode)

    def redact_value(k: str, v: Any):
        if v is None:
            return None
        if not include_values:
            return 'hidden'
        if allow_full:
            return v
        if _should_redact(k):
            # Preserve length for debugging
            s = str(v)
            if len(s) <= 4:
                return '****'
            return s[:2] + '****' + s[-2:]
        return v

    redacted_settings = {k: redact_value(k, v) for k, v in settings_dict.items()}

    env_items = {}
    for k, v in os.environ.items():
        env_items[k] = redact_value(k, v)

    response = {
        'debug': debug_mode,
        'secrets_exposed': allow_full,
        'settings': redacted_settings,
        'environment': env_items,
        'candidate_env_files': _candidate_env_files(),
        'redaction_policy': {
            'sensitive_substrings': SENSITIVE_SUBSTRINGS,
            'applied': not allow_full,
        }
    }
    return response


def get_db():
    """Database session dependency for admin endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _check_database() -> dict:
    """Probe the database with a real query."""
    t0 = time.monotonic()
    try:
        db = SessionLocal()
        try:
            db.execute(__import__("sqlalchemy").text("SELECT 1"))
            return {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
        finally:
            db.close()
    except Exception as exc:
        return {"status": "error", "error": str(exc), "latency_ms": round((time.monotonic() - t0) * 1000, 1)}


async def _check_redis() -> dict:
    """PING the Redis broker."""
    if not settings.redis_enabled:
        return {"status": "disabled"}
    t0 = time.monotonic()
    try:
        import redis.asyncio as aioredis  # type: ignore
        dsn = settings.redis_dsn or f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
        r = aioredis.from_url(dsn, socket_connect_timeout=2, socket_timeout=2)
        await r.ping()
        await r.aclose()
        return {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "latency_ms": round((time.monotonic() - t0) * 1000, 1)}


async def _check_mqtt() -> dict:
    """Verify the MQTT broker is reachable via a real TCP connect."""
    if not settings.mqtt_enabled:
        return {"status": "disabled"}
    host = settings.mqtt_broker_host
    port = settings.mqtt_broker_port
    t0 = time.monotonic()
    try:
        # presence service tells us whether the internal client is connected
        connected = getattr(mqtt_presence_service, "is_running", False)
        if callable(connected):
            connected = connected()
        # Also do a quick TCP probe so we can report broker reachability
        # independently of the internal client state
        loop = __import__("asyncio").get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: socket.create_connection((host, port), timeout=2).close(),
        )
        return {
            "status": "ok",
            "broker": f"{host}:{port}",
            "presence_client": "connected" if connected else "disconnected",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {
            "status": "error",
            "broker": f"{host}:{port}",
            "error": str(exc),
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }


async def _check_websocket() -> dict:
    """Report live WebSocket connection counts from the in-process manager."""
    try:
        from app.services.websocket_manager import websocket_manager
        stats = websocket_manager.get_connection_stats()
        return {
            "status": "ok",
            "total_connections": stats["total_connections"],
            "dashboard_connections": stats["dashboard_connections"],
            "display_connections": stats["display_connections"],
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _check_scheduler() -> dict:
    try:
        running = scheduler_service.is_running() if scheduler_service else False
        jobs = scheduler_service.get_job_count() if running else 0
        return {"status": "running" if running else "stopped", "jobs": jobs}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@health_router.get("/health")
@health_router.head("/health")
async def health_check():
    """Deep health check — probes every backing service and returns a unified status.

    HTTP 200 means the API itself is up. Inspect each component's ``status``
    field to determine whether individual dependencies are healthy.
    Overall ``status`` is ``"degraded"`` when any enabled component reports an error.
    """
    import asyncio as _asyncio

    db_check, redis_check, mqtt_check, ws_check = await _asyncio.gather(
        _check_database(),
        _check_redis(),
        _check_mqtt(),
        _check_websocket(),
    )
    scheduler_check = _check_scheduler()

    components = {
        "database": db_check,
        "redis": redis_check,
        "mqtt": mqtt_check,
        "websocket": ws_check,
        "scheduler": scheduler_check,
    }

    # Overall status: degraded if any enabled component has an error
    overall = "ok"
    for v in components.values():
        if v.get("status") == "error":
            overall = "degraded"
            break

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **components,
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


# ---------------------------------------------------------------------------
# Plugin Installation & Management
# ---------------------------------------------------------------------------


async def _broadcast_sources_changed(action: str, plugin_id: str | None) -> None:
    """Notify dashboard clients that the source list has changed."""
    try:
        from app.services.websocket_manager import websocket_manager
        await websocket_manager.emit_event(
            "sources_changed",
            {"action": action, "plugin_id": plugin_id},
            audience="dashboards",
        )
    except Exception as exc:
        logger.warning("Failed to broadcast sources_changed (%s): %s", action, exc)


@admin_router.post("/channels/install", summary="Install a channel plugin")
async def install_channel(
    request: Request,
    file: UploadFile | None = File(None),
    git_url: str | None = Form(None),
):
    """Install a channel plugin from a ZIP upload or Git URL.

    Send either:
    - A multipart form with a ``file`` field containing a ``.zip`` archive, OR
    - A multipart form with a ``git_url`` field containing a Git repository URL, OR
    - A JSON body with ``{"git_url": "..."}``
    """
    app = request.app

    # If neither form field is provided, try parsing a JSON body
    if file is None and git_url is None:
        try:
            body = await request.json()
            git_url = body.get("git_url")
        except Exception:
            pass

    if file and file.filename:
        try:
            result = await plugin_manager_service.install_from_zip(file, app)
            await _broadcast_sources_changed("installed", result.get("plugin_id"))
            return {"status": "installed", **result}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Install from ZIP failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Installation failed: {exc}") from exc
    elif git_url:
        try:
            result = await plugin_manager_service.install_from_git(git_url, app)
            await _broadcast_sources_changed("installed", result.get("plugin_id"))
            return {"status": "installed", **result}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("Install from Git failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Installation failed: {exc}") from exc
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a ZIP file upload or a git_url",
        )


@admin_router.delete("/channels/{channel_id}", summary="Uninstall a channel plugin")
async def uninstall_channel(channel_id: str, request: Request):
    """Uninstall a channel plugin: unload from server and remove from disk."""
    try:
        result = await plugin_manager_service.uninstall(channel_id, request.app)
        await _broadcast_sources_changed("uninstalled", channel_id)
        return {"status": "uninstalled", **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Uninstall failed for %s: %s", channel_id, exc)
        raise HTTPException(status_code=500, detail=f"Uninstall failed: {exc}") from exc


@admin_router.post("/channels/{channel_id}/update", summary="Update a channel plugin from its git source")
async def update_channel(channel_id: str, request: Request):
    """Re-clone the plugin from its stored git URL, preserve data/, and hot-reload."""
    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass
    git_url_override = body.get("git_url")
    try:
        result = await plugin_manager_service.update_plugin(channel_id, request.app, git_url=git_url_override)
        await _broadcast_sources_changed("updated", channel_id)
        return {"status": "updated", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Update failed for %s: %s", channel_id, exc)
        raise HTTPException(status_code=500, detail=f"Update failed: {exc}") from exc


@admin_router.post("/channels/{channel_id}/disable", summary="Disable a channel plugin")
async def disable_channel(channel_id: str, request: Request):
    """Disable a running channel plugin (keeps files on disk)."""
    try:
        result = await plugin_manager_service.disable(channel_id, request.app)
        await _broadcast_sources_changed("disabled", channel_id)
        return {"status": "disabled", **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Disable failed for %s: %s", channel_id, exc)
        raise HTTPException(status_code=500, detail=f"Disable failed: {exc}") from exc


@admin_router.post("/channels/{channel_id}/enable", summary="Enable a disabled channel plugin")
async def enable_channel(channel_id: str, request: Request):
    """Re-enable a previously disabled channel plugin."""
    try:
        result = await plugin_manager_service.enable(channel_id, request.app)
        await _broadcast_sources_changed("enabled", channel_id)
        return {"status": "enabled", **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Enable failed for %s: %s", channel_id, exc)
        raise HTTPException(status_code=500, detail=f"Enable failed: {exc}") from exc


@admin_router.get("/channels/disabled", summary="List disabled channel plugin IDs")
async def list_disabled_channels():
    """Return the list of currently disabled plugin IDs."""
    return {"disabled": plugin_manager_service.get_disabled_plugins()}


# ---------------------------------------------------------------------------
# Dev Channel Management
# ---------------------------------------------------------------------------


@admin_router.get("/dev/channels", summary="List dev-linked channels")
async def list_dev_channels():
    """Return all dev-linked channel entries."""
    return {"dev_channels": plugin_manager_service.get_dev_channels()}


@admin_router.post("/dev/channels", summary="Link a dev channel")
async def link_dev_channel(request: Request):
    """Link a local directory as a dev channel.

    Body: ``{ "path": "/absolute/path/to/plugin" }``
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from None

    path = body.get("path")
    if not path or not isinstance(path, str):
        raise HTTPException(status_code=400, detail="'path' field is required and must be a string")

    try:
        result = await plugin_manager_service.link_dev_channel(path, request.app)
        return {"status": "linked", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Link dev channel failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Link failed: {exc}") from exc


@admin_router.delete("/dev/channels/{channel_id}", summary="Unlink a dev channel")
async def unlink_dev_channel(channel_id: str, request: Request):
    """Unlink a dev channel (does not delete files on disk)."""
    try:
        result = await plugin_manager_service.unlink_dev_channel(channel_id, request.app)
        return {"status": "unlinked", **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unlink dev channel failed for %s: %s", channel_id, exc)
        raise HTTPException(status_code=500, detail=f"Unlink failed: {exc}") from exc


@admin_router.post("/dev/channels/{channel_id}/reload", summary="Reload a dev channel")
async def reload_dev_channel(channel_id: str, request: Request):
    """Manually reload a dev channel (unload + re-load)."""
    try:
        result = await plugin_manager_service.reload_dev_channel(channel_id, request.app)
        return {"status": "reloaded", **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Reload dev channel failed for %s: %s", channel_id, exc)
        raise HTTPException(status_code=500, detail=f"Reload failed: {exc}") from exc


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
        ) from e


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
        ) from e


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
        ) from e


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
        ) from e


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
        ) from e


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
        ) from e


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
        ) from e


# ---------------------------------------------------------------------------
# Display Image Persistence – Status & Maintenance
# ---------------------------------------------------------------------------

class BackfillThumbnailsRequest(BaseModel):
    limit: int = Field(100, ge=1, le=2000, description="Maximum rows to process (ignored if regenerate_all=true)")
    force: bool = Field(False, description="Regenerate thumbnails even if a thumbnail_path already exists")
    dry_run: bool = Field(False, description="Report what would be done without writing changes")
    regenerate_all: bool = Field(False, description="Backfill across all rows (not just missing thumbnails)")


class TestPersistRequest(BaseModel):
    display_id: str
    scene_id: str
    image_url: str
    subchannel_id: str | None = None
    assignment_id: str | None = Field(None, description="Optional explicit assignment id; auto-generated if missing")
    width: int | None = None
    height: int | None = None
    image_format: str | None = None

@admin_router.post("/display-images/test-persist")
async def test_persist_display_image(body: TestPersistRequest, db: Session = Depends(get_db)):
    """Manually persist an image record (diagnostics / backfill helper).

    This bypasses channel + MQTT distribution to validate persistence logic.
    """
    svc = DisplayImagePersistenceService(db)
    assignment_id = body.assignment_id or f"manual-{uuid.uuid4().hex[:8]}"
    try:
        rec = svc.store_distribution_image(
            display_id=body.display_id,
            scene_id=body.scene_id,
            subchannel_id=body.subchannel_id,
            assignment_id=assignment_id,
            image_url=body.image_url,
            width=body.width,
            height=body.height,
            image_format=body.image_format,
            source="manual-test",
            retain_history=True,
        )
        return {
            "ok": True,
            "id": rec.id,
            "display_id": rec.display_id,
            "scene_id": rec.scene_id,
            "thumbnail_path": rec.thumbnail_path,
            "thumbnail_url": rec.thumbnail_path,
            "read_only_mode": svc.read_only_mode,
            "stored_local_path": rec.stored_local_path,
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Persist failed: {e}") from e


@admin_router.get("/db/info")
async def get_db_info():
    """Return active database configuration & file presence (SQLite diagnostics)."""
    import os
    import pathlib
    import sqlite3

    from app.config import settings as cfg
    url = cfg.database_url
    resolved_path = None
    size = None
    tables = []
    if url.startswith("sqlite"):
        # Extract path after last ':' and slashes handling
        # Variants: sqlite:///relative.db  sqlite:////absolute/path.db
        raw = url.split('sqlite:///', 1)[-1]
        # If starts with '/', it's absolute
        if raw.startswith('/'):
            resolved_path = raw
        else:
            resolved_path = str(pathlib.Path(raw).resolve())
        if os.path.exists(resolved_path):
            size = os.path.getsize(resolved_path)
            try:
                conn = sqlite3.connect(resolved_path)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                conn.close()
            except Exception:  # noqa: BLE001
                pass
    return {
        "database_url": url,
        "resolved_path": resolved_path,
        "file_exists": bool(resolved_path and os.path.exists(resolved_path)),
        "file_size": size,
        "has_display_scene_images": "display_scene_images" in tables,
        "tables_sample": tables[:15],
    }


@admin_router.get("/display-images/status")
async def get_display_images_status(db: Session = Depends(get_db)):
    """Return operational status of the persisted display images feature.

    Provides directory info, mode flags, counts, and sample records to aid diagnostics.
    """
    svc = DisplayImagePersistenceService(db)
    media_root: Path = svc.media_root
    configured_dir = getattr(settings, "display_images_directory", None)

    total_rows = db.query(DisplaySceneImage).count()
    missing_q = db.query(DisplaySceneImage).filter(DisplaySceneImage.thumbnail_path.is_(None))
    rows_missing = missing_q.count()
    sample_missing = [
        {
            "id": r.id,
            "display_id": r.display_id,
            "scene_id": r.scene_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in missing_q.order_by(DisplaySceneImage.created_at.desc()).limit(5).all()
    ]
    recent_rows = [
        {
            "id": r.id,
            "display_id": r.display_id,
            "scene_id": r.scene_id,
            "has_thumb": bool(r.thumbnail_path),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in db.query(DisplaySceneImage).order_by(DisplaySceneImage.created_at.desc()).limit(5).all()
    ]

    exists = media_root.exists()
    writable = os.access(media_root, os.W_OK) if exists else False

    return {
        "configured_dir": configured_dir,
        "resolved_path": str(media_root),
        "exists": exists,
        "writable": writable,
        "read_only_mode": svc.read_only_mode,
        "thumb_dimensions": {
            "max_width": svc.thumb_max_width,
            "max_height": svc.thumb_max_height,
        },
        "retention": {
            "enabled": getattr(settings, "display_image_retention_enabled", False),
            "max_per_pair": getattr(settings, "display_image_retention_max_per_pair", None),
            "prune_interval_seconds": getattr(settings, "display_image_retention_interval_seconds", None),
        },
        "counts": {
            "total_rows": total_rows,
            "rows_missing_thumbnails": rows_missing,
        },
        "samples": {
            "missing_thumbnails": sample_missing,
            "recent": recent_rows,
        },
    }


@admin_router.post("/display-images/backfill-thumbnails")
async def backfill_display_image_thumbnails(body: BackfillThumbnailsRequest, db: Session = Depends(get_db)):
    """Generate thumbnails for persisted images missing them (or force regenerate).

    Safeguards:
    - Respects read_only_mode (unless dry_run=True).
    - Limit controls batch size; set regenerate_all to ignore missing-only filtering.
    - Force allows regenerating existing thumbnails.
    - Dry run avoids making filesystem or DB changes.
    """
    svc = DisplayImagePersistenceService(db)
    if svc.read_only_mode and not body.dry_run:
        raise HTTPException(
            status_code=409,
            detail="Persistence service is in read-only mode; cannot write thumbnails (use dry_run).",
        )

    # Build base query
    q = db.query(DisplaySceneImage).order_by(DisplaySceneImage.created_at.desc())
    if not body.regenerate_all and not body.force:
        # Only rows missing thumbnails
        q = q.filter(DisplaySceneImage.thumbnail_path.is_(None))
    elif not body.regenerate_all and body.force:
        # Rows that currently have thumbnails (to regenerate) OR missing
        # Simpler: operate over all rows but limit
        pass
    # If regenerate_all True: operate over all rows regardless

    rows = q.limit(None if body.regenerate_all else body.limit).all()
    attempted = len(rows)
    generated = 0
    skipped_download = 0
    failures = 0
    results = []

    if body.dry_run:
        return {
            "dry_run": True,
            "attempted": attempted,
            "would_process_ids": [r.id for r in rows[:50]],
            "read_only_mode": svc.read_only_mode,
        }

    for r in rows:
        try:
            # Skip if already has thumb and not forcing
            if r.thumbnail_path and not body.force:
                continue
            # Download original image
            resp = requests.get(r.image_url, timeout=15)
            if resp.status_code != 200:
                skipped_download += 1
                continue
            binary = resp.content
            try:
                with Image.open(io.BytesIO(binary)) as im:
                    im.thumbnail((svc.thumb_max_width, svc.thumb_max_height))
                    rel_dir = Path(r.scene_id) / r.display_id
                    abs_dir = svc.media_root / rel_dir
                    abs_dir.mkdir(parents=True, exist_ok=True)
                    thumb_filename = f"{r.id}.thumb.jpg"
                    thumb_path = abs_dir / thumb_filename
                    im.convert("RGB").save(thumb_path, "JPEG", quality=75, optimize=True)
                    r.thumbnail_path = str(thumb_path)
                    generated += 1
                    results.append({"id": r.id, "thumbnail_path": r.thumbnail_path})
            except Exception as pil_err:  # noqa: BLE001
                failures += 1
                logger.debug("backfill.thumbnail PIL failure id=%s err=%s", r.id, pil_err)
        except Exception as e:  # noqa: BLE001
            failures += 1
            logger.debug("backfill.thumbnail failure id=%s err=%s", r.id, e)

    try:
        db.commit()
    except Exception as commit_err:  # noqa: BLE001
        logger.error("backfill.thumbnail commit failure err=%s", commit_err)
        raise HTTPException(status_code=500, detail="Failed to commit thumbnail updates") from commit_err

    return {
        "dry_run": False,
        "attempted": attempted,
        "generated": generated,
        "skipped_download": skipped_download,
        "failures": failures,
        "force": body.force,
        "regenerate_all": body.regenerate_all,
        "processed_sample": results[:20],
        "read_only_mode": svc.read_only_mode,
    }


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
        ) from e


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
        ) from e


@admin_router.post("/mqtt/publish/{device_id}")
async def publish_device_status(device_id: str, status: str, metadata: dict[str, Any] | None = None):
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
        ) from e

@admin_router.get("/debug/discovery")
async def debug_discovery_service():
    """Debug endpoint to see discovery service state"""
    from app.services.mdns_discovery import mdns_discovery_service

    discovered = mdns_discovery_service.get_discovered_displays()

    debug_data = {
        "discovered_displays": [],
        "display_id_mappings": mdns_discovery_service.display_id_to_service_name.copy(),
        "mqtt_last_heartbeat": {k: v.isoformat() for k, v in mdns_discovery_service.mqtt_last_heartbeat.items()},
        "service_running": mdns_discovery_service.is_running,
        "offline_timeout": mdns_discovery_service.offline_timeout
    }

    for display in discovered:
        debug_data["discovered_displays"].append({
            "service_name": display.service_name,
            "display_id": display.display_id,
            "display_name": display.display_name,
            "hostname": display.hostname,
            "is_online": display.is_online,
            "last_seen": display.last_seen.isoformat(),
            "assigned_scene_id": display.assigned_scene_id,
            "assigned_subchannel_id": display.assigned_subchannel_id
        })

    return debug_data


# ---------------------------------------------------------------------------
# Image Swap (ephemeral per-display files) Administration
# ---------------------------------------------------------------------------

@admin_router.get("/swap/summary", summary="Swap storage summary")
async def get_swap_summary():
    if not getattr(settings, "display_swap_enabled", True):
        return {"enabled": False, "message": "Swap storage disabled"}
    data = swap_summary()
    data.update({
        "enabled": True,
        "max_files_per_display": getattr(settings, "display_swap_max_files_per_display", None),
    })
    return data


@admin_router.get("/swap/scene/{scene_id}", summary="List swap files for scene")
async def get_swap_scene(scene_id: str):
    if not getattr(settings, "display_swap_enabled", True):
        raise HTTPException(status_code=400, detail="Swap storage disabled")
    return list_scene_swap(scene_id)


@admin_router.post("/swap/prune", summary="Force prune swap storage")
async def prune_swap_now(max_files_per_display: int | None = None):
    if not getattr(settings, "display_swap_enabled", True):
        raise HTTPException(status_code=400, detail="Swap storage disabled")
    cap = max_files_per_display or getattr(settings, "display_swap_max_files_per_display", 25)
    deleted = prune_swap(max_files_per_display=cap)
    return {"deleted": deleted, "max_files_per_display": cap}


@admin_router.get("/swap/config", summary="Swap configuration")
async def get_swap_config():
    return {
        "enabled": getattr(settings, "display_swap_enabled", True),
        "max_files_per_display": getattr(settings, "display_swap_max_files_per_display", 25),
        "prune_on_cleanup": getattr(settings, "display_swap_prune_on_cleanup", True),
        "media_mount": "/media",
        "notes": "Swap files live under /media/swap/<scene>/<display>/.",
    }
