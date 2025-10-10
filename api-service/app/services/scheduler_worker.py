"""
Scheduler Worker Service - Executes scheduled jobs

This service runs as a background task and processes due scheduler jobs,
executing the appropriate actions based on the job's action_type.

Key responsibilities:
- Poll for due jobs at regular intervals
- Execute refresh_scene actions by calling channel APIs
- Distribute generated images to assigned displays
- Track execution status and handle failures
"""
import asyncio
import base64
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Removed unused sqlalchemy imports (Session, and_) to reduce dependencies

from ..db.base import SessionLocal
from ..db.models import SchedulerJob, SchedulerJobSceneAssignment, Scene, DisplayClient
from ..schemas.scheduler import ExecutionStatus, TriggerReason
from ..services.scheduler_service import SchedulerService
from ..services.mdns_discovery import mdns_discovery_service
from ..services.mqtt.publisher import mqtt_scene_service
from ..config import settings
from ..services.display_last_image import display_last_image_store
from ..services.display_image_persistence import DisplayImagePersistenceService
from ..services.scene_refresh_service import scene_refresh_service, SceneRefreshResult
from ..services.image_swap import save_swap_image, prune_swap

logger = logging.getLogger(__name__)

# Track last content hash per scene/subchannel across runs to avoid re-sending
# identical images when channel instances are re-created and report distribution_mode="new".
# Key: f"{scene_id}:{subchannel_id or ''}"
_last_scene_content_hash: dict[str, str] = {}


# -----------------------------------------------------
# Custom exception types to classify failure domains
# -----------------------------------------------------
class ChannelRequestError(Exception):
    """Raised when a channel plugin request fails (logic / plugin layer)."""


class ImageConversionError(Exception):
    """Raised when converting or persisting image data fails."""


class DistributionError(Exception):
    """Raised when distributing image data to displays encounters a non-recoverable issue."""


def _convert_image_to_url(image_info: dict[str, Any]) -> str | None:
    """
    Convert image information from a channel to a publicly accessible URL.
    
    Args:
        image_info: Image information from channel response
        
    Returns:
        URL string if conversion is successful, None otherwise
    """
    try:
        base_url = settings.public_base_url  # External-facing base URL

        # Case 1: "image" key present
        img_val = image_info.get("image")
        if isinstance(img_val, str):
            # Heuristic for base64: long-ish string and either common prefixes or no early slash
            if (
                len(img_val) > 100
                and (
                    img_val.startswith(("/9j/", "iVBORw0KGgo", "R0lGOD", "UklGR"))
                    or (not img_val.startswith("/") and "/" not in img_val[:50])
                )
            ):
                return _save_base64_and_get_url(image_info, base_url)

            # Treat as file path (absolute or relative within channels)
            image_path = img_val.strip()
            if image_path.startswith("/"):
                relative_path = image_path.lstrip("/")
                return f"{base_url}/channels/{relative_path}"
            return f"{base_url}/channels/{image_path}"

        # Case 2: filename provided separately
        filename = image_info.get("filename")
        if filename:
            return f"{base_url}/channels/photo_frame/uploads/{filename}"

        logger.error(
            "Unable to determine image URL from channel response - no image path, base64 content, or filename found"
        )
        return None
    except (OSError, ValueError, KeyError) as e:
        logger.error("Error converting image to URL: %s", e)
        return None


def _save_base64_and_get_url(image_info: dict[str, Any], base_url: str) -> str | None:
    """
    Save base64 image data to a file and return the URL to access it.
    
    Args:
        image_info: Image information containing base64 data
        api_hostname: API hostname for URL construction
        api_port: API port for URL construction
        
    Returns:
        URL string if successful, None otherwise
    """
    try:
        
        # Get base64 data
        image_data = image_info.get("image", "")
        if not image_data:
            return None
            
        # Get additional info for filename
        image_id = image_info.get("image_id", "unknown")
        filename = image_info.get("filename", f"image_{image_id}.jpg")
        
        # Ensure we have a proper extension
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            # Try to detect format from base64 header
            if image_data.startswith('/9j/'):
                filename += '.jpg'
            elif image_data.startswith('iVBORw0KGgo'):
                filename += '.png'
            elif image_data.startswith('R0lGOD'):
                filename += '.gif'
            else:
                filename += '.jpg'  # Default to jpg
        
        # Resolve temp directory preference:
        # 1. settings.scheduler_temp_directory (absolute or relative)
        # 2. Fallback: <channels_directory>/scheduler_temp
        raw_temp = getattr(settings, "scheduler_temp_directory", "scheduler_temp")
        temp_dir = Path(raw_temp)
        if not temp_dir.is_absolute():
            # Interpret relative path as relative to current working directory (consistent with previous behavior)
            before = temp_dir
            temp_dir = temp_dir.resolve()
            logger.debug("Resolved relative scheduler_temp_directory: %s -> %s", before, temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Scheduler temp directory in use: raw=%s resolved=%s", raw_temp, temp_dir)
        
        # Create unique filename to avoid conflicts
        timestamp = str(int(uuid.uuid4().int >> 64))  # Use part of UUID as timestamp
        temp_filename = f"{timestamp}_{filename}"
        temp_file_path = temp_dir / temp_filename
        
        # Decode and save base64 data
        try:
            decoded_data = base64.b64decode(image_data)
            with open(temp_file_path, 'wb') as f:
                f.write(decoded_data)
                
            logger.info("Saved base64 image to temporary file: %s (size=%d bytes)", temp_file_path, len(decoded_data))

            # Determine how to expose the file. If temp_dir is *inside* the channels_directory
            # hierarchy, compute its relative path. Otherwise, mirror into channels/scheduler_temp.
            channels_root = Path(settings.channels_directory).resolve()
            try:
                relative_within_channels = temp_file_path.relative_to(channels_root)
                # Served directly under /channels/<relative>
                url = f"{base_url}/channels/{relative_within_channels.as_posix()}"
                logger.debug(
                    "Temp image is within channels root; using direct relative path: %s -> %s",
                    temp_file_path,
                    url,
                )
                return url
            except ValueError:
                # Not under channels root – mirror copy
                mirror_dir = channels_root / "scheduler_temp"
                mirror_dir.mkdir(parents=True, exist_ok=True)
                mirror_path = mirror_dir / temp_filename
                try:
                    # Copy the file (avoid shutil for minimal deps)
                    with open(temp_file_path, 'rb') as src, open(mirror_path, 'wb') as dst:
                        dst.write(src.read())
                    url = f"{base_url}/channels/scheduler_temp/{temp_filename}"
                    logger.info(
                        "Mirrored scheduler image into channels: %s (origin %s) url=%s",
                        mirror_path,
                        temp_file_path,
                        url,
                    )
                    return url
                except Exception as mirror_err:
                    logger.error(
                        "Failed to mirror scheduler image into channels: %s (origin %s)",
                        mirror_err,
                        temp_file_path,
                    )
                    return None
            
        except Exception as decode_error:
            logger.error("Failed to decode base64 image data: %s", decode_error)
            return None
            
    except (OSError, ValueError, base64.binascii.Error) as e:
        logger.error("Error saving base64 image: %s", e)
        return None


class SchedulerWorker:
    """Background worker for executing scheduled jobs"""
    
    def __init__(self):
        self.running = False
        self._task = None
        self.poll_interval = 30  # Check for due jobs every 30 seconds
        # Cleanup bookkeeping
        self._last_cleanup_monotonic: float = 0.0
        self._cleanup_interval_seconds: int = 300  # run cleanup at most every 5 minutes
        # Persisted image retention bookkeeping
        self._last_image_retention_monotonic: float = 0.0
        
    async def start(self):
        """Start the scheduler worker"""
        if self.running:
            logger.warning("Scheduler worker is already running")
            return
            
        self.running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info("Scheduler worker started")
        
    async def stop(self):
        """Stop the scheduler worker"""
        if not self.running:
            return
            
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler worker stopped")
        
    async def _worker_loop(self):
        """Main worker loop that processes due jobs"""
        logger.info("Scheduler worker loop started (polling every %ss)", self.poll_interval)
        
        while self.running:
            # Guardrail: we intentionally keep a loop-level exception barrier so a single
            # unhandled error does not terminate the scheduler background task.
            try:
                self._maybe_cleanup_temp_images()  # best-effort
                self._maybe_prune_persisted_images()  # best-effort DB pruning
                await self._process_due_jobs()
            except (OSError, TimeoutError) as e:
                logger.error("Scheduler worker loop transient error: %s", e, exc_info=True)
            except Exception as e:  # noqa: BLE001 - final safety net (see comment above)
                logger.exception("Scheduler worker loop unexpected error: %s", e)
            
            # Wait for the next polling interval
            await asyncio.sleep(self.poll_interval)
    
    async def _process_due_jobs(self):
        """Process all jobs that are due for execution."""
        with SessionLocal() as db:
            scheduler_service = SchedulerService(db)
            try:
                due_jobs = await scheduler_service.get_due_jobs(limit=50)
            except Exception as e:  # noqa: BLE001 - DB / service layer unexpected
                logger.exception("scheduler.jobs.fetch_failed: %s", e)
                return

            if not due_jobs:
                # Diagnostic: log periodic idle state with earliest upcoming job
                try:
                    # Fetch a small sample of upcoming jobs to compute earliest next_run_at
                    upcoming = (
                        db.query(SchedulerJob)
                        .filter(SchedulerJob.enabled)
                        .order_by(SchedulerJob.next_run_at.asc())
                        .limit(5)
                        .all()
                    )
                    if upcoming:
                        earliest = upcoming[0].next_run_at
                        total_enabled = (
                            db.query(SchedulerJob)
                            .filter(SchedulerJob.enabled)
                            .count()
                        )
                        logger.debug(
                            "scheduler.jobs.idle no_due_jobs earliest_next_run=%s total_enabled=%d sample=%s",
                            earliest,
                            total_enabled,
                            [j.id for j in upcoming],
                        )
                    else:
                        logger.debug("scheduler.jobs.idle no_enabled_jobs")
                except Exception:  # noqa: BLE001
                    # Avoid breaking the loop for diagnostics
                    pass
                return

            logger.info("scheduler.jobs.processing count=%d", len(due_jobs))

            for job in due_jobs:
                try:
                    await self._execute_job(job, scheduler_service)
                except ChannelRequestError as e:
                    logger.error("scheduler.job.channel_error job_id=%s error=%s", job.id, e)
                except ImageConversionError as e:
                    logger.error("scheduler.job.image_error job_id=%s error=%s", job.id, e)
                except DistributionError as e:
                    logger.error("scheduler.job.distribution_error job_id=%s error=%s", job.id, e)
                except Exception as e:  # noqa: BLE001
                    logger.exception("scheduler.job.unexpected job_id=%s error=%s", job.id, e)
    
    async def _execute_job(
        self,
        job: SchedulerJob,
        scheduler_service: SchedulerService,
        *,
        trigger_reason: TriggerReason = TriggerReason.SCHEDULED,
        worker_id: str = "scheduler-worker"
    ) -> str | None:
        """Execute a single scheduler job.

        Returns the execution_id created for this run (or None if lock failed).
        """
        locked = await scheduler_service.lock_job(job.id)
        if not locked:
            logger.warning("Could not lock job %s, skipping", job.id)
            return None

        execution_id = await scheduler_service.start_execution(
            job.id,
            worker_id=worker_id,
            trigger_reason=trigger_reason,
        )

        try:
            logger.info(
                "Executing job %s (%s) - action=%s trigger=%s", job.id, job.name, job.action_type, trigger_reason.value
            )

            if job.action_type == "refresh_scene":
                result = await self._execute_refresh_scene(job, scheduler_service)
            else:
                logger.warning("Unknown action type: %s", job.action_type)
                result = {"success": False, "error": f"Unknown action type: {job.action_type}"}

            status = ExecutionStatus.SUCCESS if result.get("success") else ExecutionStatus.FAILED
            await scheduler_service.complete_execution(
                execution_id,
                status,
                output_data=result,
                error_message=result.get("error"),
                affected_scenes=result.get("affected_scenes", []),
            )
            logger.info("Job %s completed status=%s", job.id, status.value)
        except (ChannelRequestError, ImageConversionError, DistributionError) as e:
            await scheduler_service.complete_execution(
                execution_id,
                ExecutionStatus.FAILED,
                error_message=str(e),
            )
            logger.error("Job %s domain failure: %s", job.id, e)
        except Exception as e:  # noqa: BLE001 - unexpected internal failure
            await scheduler_service.complete_execution(
                execution_id,
                ExecutionStatus.FAILED,
                error_message=str(e),
            )
            logger.error("Job %s execution failed: %s", job.id, e, exc_info=True)
        finally:
            await scheduler_service.unlock_job(job.id)
        return execution_id

    async def run_job_immediately(
        self,
        job_id: str,
        *,
        trigger_reason: TriggerReason = TriggerReason.MANUAL,
        force: bool = False,
    ) -> str | None:
        """Convenience method to execute a job immediately bypassing the poll delay.

        Returns execution_id on success, or None if job not found / not permitted.
        """
        with SessionLocal() as db:
            scheduler_service = SchedulerService(db)
            job = db.query(SchedulerJob).filter(SchedulerJob.id == job_id).first()
            if not job:
                logger.warning("Immediate run requested for missing job %s", job_id)
                return None
            if (not job.enabled) and (not force):
                logger.info("Immediate run skipped; job %s disabled and force not set", job_id)
                return None
            return await self._execute_job(
                job,
                scheduler_service,
                trigger_reason=trigger_reason,
                worker_id="manual-trigger",
            )

    # -----------------------------------------------------
    # Retention / cleanup support
    # -----------------------------------------------------
    def _maybe_cleanup_temp_images(self) -> None:
        """Delete old scheduler temp images according to retention policy.

        Runs at most every self._cleanup_interval_seconds to avoid excessive disk scans.
        Disabled if scheduler_temp_max_age_minutes <= 0.
        """
        now_mono = time.monotonic()
        if now_mono - self._last_cleanup_monotonic < self._cleanup_interval_seconds:
            return
        self._last_cleanup_monotonic = now_mono

        # Determine retention
        max_age_min = getattr(settings, "scheduler_temp_max_age_minutes", 1440)
        if max_age_min <= 0:
            return  # disabled

        temp_root_raw = getattr(settings, "scheduler_temp_directory", "scheduler_temp")
        temp_root = Path(temp_root_raw).resolve()
        if not temp_root.exists() or not temp_root.is_dir():
            return
        cutoff_ts = datetime.now(timezone.utc).timestamp() - (max_age_min * 60)
        removed = 0
        inspected = 0
        try:
            for path in temp_root.iterdir():
                if not path.is_file():
                    continue
                inspected += 1
                try:
                    stat = path.stat()
                except FileNotFoundError:  # race
                    continue
                except Exception:  # noqa: BLE001
                    logger.debug("scheduler.cleanup.stat_error", extra={"path": str(path)})
                    continue
                if stat.st_mtime < cutoff_ts:
                    try:
                        path.unlink()
                        removed += 1
                    except FileNotFoundError:
                        continue
                    except Exception:  # noqa: BLE001
                        logger.debug("scheduler.cleanup.unlink_error", extra={"path": str(path)})
                        continue
        except Exception:  # noqa: BLE001
            logger.debug("scheduler.cleanup.iter_error", exc_info=True)
            return
        if inspected:
            logger.info(
                "scheduler.cleanup.summary",
                extra={
                    "dir": str(temp_root),
                    "removed": removed,
                    "inspected": inspected,
                    "max_age_min": max_age_min,
                },
            )
        # Also prune swap directory (lightweight) every cleanup cycle
        try:
            prune_swap(max_files_per_display=25)
        except Exception:  # noqa: BLE001
            pass
    
    def _maybe_prune_persisted_images(self) -> None:
        """Prune persisted display scene images according to retention settings.

        Uses simple per-(display,scene,subchannel) cap implemented in service layer.
        Runs at most every settings.display_image_retention_interval_seconds.
        """
        if not getattr(settings, "display_image_retention_enabled", True):
            return
        interval = getattr(settings, "display_image_retention_interval_seconds", 600)
        now_mono = time.monotonic()
        if now_mono - self._last_image_retention_monotonic < interval:
            return
        self._last_image_retention_monotonic = now_mono

        max_per_pair = getattr(settings, "display_image_retention_max_per_pair", 10)
        if max_per_pair <= 0:
            return

        try:
            with SessionLocal() as db:
                svc = DisplayImagePersistenceService(db)
                deleted = svc.prune_retention(max_per_pair=max_per_pair)
                if deleted:
                    logger.info(
                        "persist.images.retention pruned=%d max_per_pair=%d", deleted, max_per_pair
                    )
                else:
                    logger.debug(
                        "persist.images.retention nothing_to_prune max_per_pair=%d", max_per_pair
                    )
        except Exception as e:  # noqa: BLE001
            logger.debug("persist.images.retention.error err=%s", e)
    
    async def _execute_refresh_scene(self, job: SchedulerJob, scheduler_service: SchedulerService) -> dict[str, Any]:
        """Execute a refresh_scene action"""
        try:
            # Get scene assignments for this job
            assignments = await scheduler_service.get_job_assignments(job.id)
            
            if not assignments:
                return {
                    "success": False,
                    "error": "No scene assignments found for job"
                }
            
            affected_scenes = []
            results = []
            
            for assignment in assignments:
                try:
                    scene_result = await self._refresh_single_scene(assignment)
                    results.append(scene_result)
                    if scene_result.get("success"):
                        affected_scenes.append(assignment.scene_id)
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        "refresh_scene.assignment_failed scene_id=%s err=%s", assignment.scene_id, e
                    )
                    results.append({
                        "scene_id": assignment.scene_id,
                        "success": False,
                        "error": str(e)
                    })
            
            # Determine overall success
            successful_scenes = sum(1 for r in results if r.get("success"))
            total_scenes = len(results)
            
            return {
                "success": successful_scenes > 0,
                "affected_scenes": affected_scenes,
                "scene_results": results,
                "summary": f"Refreshed {successful_scenes}/{total_scenes} scenes"
            }
            
        except (ChannelRequestError, ImageConversionError, DistributionError) as e:
            logger.error("refresh_scene.domain_error job_id=%s error=%s", job.id, e)
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("refresh_scene.unexpected job_id=%s error=%s", job.id, e)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _refresh_single_scene(self, assignment: SchedulerJobSceneAssignment) -> dict[str, Any]:
        """Refresh a single scene delegating to SceneRefreshService.

        Returns legacy dict structure for backward compatibility with existing
        scheduler execution aggregation logic.
        """
        result: SceneRefreshResult = await scene_refresh_service.refresh_scene(
            assignment.scene_id,
            trigger_reason="scheduler",
            force=False,
        )
        # Map to legacy shape expected by caller
        return {
            "scene_id": result.scene_id,
            "success": result.status == "ok",
            "channel_id": result.channel_id,
            "subchannel_id": result.subchannel_id,
            "displays_updated": result.displays_updated,
            "errors": result.errors,
            "skipped_reason": result.skipped_reason,
            "image_url": result.image_url,
            "status": result.status,
        }
    
    async def _request_channel_image(
        self,
        channel_id: str,
        subchannel_id: str | None = None,
    _refresh_method: str = "content_refresh",  # unused legacy parameter (kept for backward compat)
        *,
        resolution: list[int] | None = None,
        orientation: str | None = None,
    ) -> dict[str, Any]:
        """Request an image from a channel using the unified render helper.

        Returns dict with success flag and normalized image structure under 'image'.
        """
        from app.services.channel_render_shared import request_channel_image_unified, ChannelRenderError

        # Build base payload; scheduler requests should mark distribution=new to force fresh renders
        res = resolution if (resolution and len(resolution) == 2) else [800, 600]
        base_payload: dict[str, Any] = {
            "settings": {
                "resolution": res,
                "orientation": orientation or None,  # let helper infer if None
                "distribution": "new",
            },
        }
        if subchannel_id:
            # Accept multiple keys; helper will normalize
            base_payload["gallery_id"] = subchannel_id
            base_payload.setdefault("settings", {})["subChannelId"] = subchannel_id

        try:
            unified = await request_channel_image_unified(channel_id, base_payload)
        except ChannelRenderError as ce:  # noqa: BLE001
            raise ChannelRequestError(str(ce)) from ce
        except Exception as e:  # noqa: BLE001
            raise ChannelRequestError(str(e)) from e

        # Adapt unified structure to legacy caller expectation
        return {
            "success": True,
            "image": {
                "bytes": unified.get("bytes"),
                "content_type": unified.get("content_type"),
                "width": unified.get("width"),
                "height": unified.get("height"),
                "orientation": unified.get("orientation"),
                "distribution_mode": unified.get("distribution_mode"),
                "sha256": unified.get("sha256"),
                "gallery_id": unified.get("gallery_id"),
            },
        }


    # ----------------------------------------------
    # Display collection & grouping helpers
    # ----------------------------------------------
    def _collect_assigned_displays(self, scene: Scene) -> list[dict[str, Any]]:
        """Gather displays (discovered + DB) assigned to a scene with resolution & orientation.

        Returns list of dicts: {device_id, width, height, orientation}
        """
        collected: dict[str, dict[str, Any]] = {}

        # mDNS discovered displays
        if mdns_discovery_service.is_running:
            try:
                discovered = mdns_discovery_service.get_discovered_displays()
                for d in discovered:
                    if d.assigned_scene_id == scene.id or d.assigned_scene_id == str(scene.id):
                        w, h = self._parse_resolution_string(d.resolution)
                        orientation = d.properties.get("orientation", "landscape")
                        # Fill missing dims using orientation-appropriate defaults
                        if not (w and h and w > 0 and h > 0):
                            if orientation == "portrait":
                                w, h = 600, 800
                            elif orientation == "square":
                                w, h = 600, 600
                            else:
                                w, h = 800, 600
                        # Swap dims if they don't match the orientation's aspect
                        if orientation == "portrait" and w > h:
                            w, h = h, w
                        elif orientation == "landscape" and h > w:
                            w, h = h, w
                        collected[d.display_id] = {
                            "device_id": d.hostname or d.display_id,
                            "width": w,
                            "height": h,
                            "orientation": orientation,
                        }
            except Exception as e:  # noqa: BLE001
                logger.debug("collect_discovered.error scene=%s err=%s", scene.id, e)

        # DB displays
        with SessionLocal() as db:
            db_displays = db.query(DisplayClient).filter(
                DisplayClient.assigned_scene_id == scene.id
            ).all()
            for display in db_displays:
                if display.id in collected:
                    continue  # prefer discovered
                orientation = display.orientation or "landscape"
                w = display.width or 0
                h = display.height or 0
                if not (w and h and w > 0 and h > 0):
                    if orientation == "portrait":
                        w, h = 600, 800
                    elif orientation == "square":
                        w, h = 600, 600
                    else:
                        w, h = 800, 600
                if orientation == "portrait" and w > h:
                    w, h = h, w
                elif orientation == "landscape" and h > w:
                    w, h = h, w
                collected[display.id] = {
                    "device_id": display.hostname or display.id,
                    "width": w,
                    "height": h,
                    "orientation": orientation,
                }

        # Normalize orientation by aspect to avoid conflicting values
        normalized: list[dict[str, Any]] = []
        for d in collected.values():
            w, h = d.get("width") or 0, d.get("height") or 0
            inferred = "square" if w == h else ("portrait" if h > w else "landscape")
            normalized.append({**d, "orientation": inferred})
        return normalized

    @staticmethod
    def _parse_resolution_string(res_str: str | None) -> tuple[int, int]:
        if not res_str or "x" not in res_str:
            return 800, 600
        try:
            w_str, h_str = res_str.lower().split("x", 1)
            w = int(w_str)
            h = int(h_str)
            if w <= 0 or h <= 0:
                return 800, 600
            return w, h
        except ValueError:
            return 800, 600
    
    async def _distribute_to_displays(self, scene: Scene, image_response: dict[str, Any]) -> dict[str, Any]:
        """Distribute the generated image to displays assigned to this scene"""
        try:
            displays_updated = 0
            errors = []
            
            # Find displays assigned to this scene
            assigned_displays = []
            
            # Check discovered displays via mDNS
            if mdns_discovery_service.is_running:
                discovered_displays = mdns_discovery_service.get_discovered_displays()
                for display in discovered_displays:
                    if (display.assigned_scene_id == scene.id or 
                        display.assigned_scene_id == str(scene.id)):
                        assigned_displays.append({
                            "id": display.display_id,
                            "hostname": display.hostname,
                            "type": "discovered",
                            "current_scene_id": display.assigned_scene_id
                        })
            
            # Also check database displays (fallback)
            with SessionLocal() as db:
                db_displays = db.query(DisplayClient).filter(
                    DisplayClient.assigned_scene_id == scene.id
                ).all()
                
                for display in db_displays:
                    # Avoid duplicates
                    if not any(d["id"] == display.id for d in assigned_displays):
                        assigned_displays.append({
                            "id": display.id,
                            "hostname": display.hostname,
                            "type": "database",
                            "current_scene_id": display.assigned_scene_id
                        })
            
            if not assigned_displays:
                logger.info("No displays assigned to scene %s", scene.id)
                return {
                    "displays_updated": 0,
                    "errors": ["No displays assigned to scene"]
                }
            
            logger.info(
                "Distributing to %d displays for scene %s", len(assigned_displays), scene.id
            )
            
            # Extract image information; new pipeline may provide raw bytes directly under image_response["image"]["bytes"]
            image_info = image_response.get("image", {})
            distribution_mode = image_info.get("distribution_mode")
            # Prefer nested sha256; fall back to top-level if provided
            candidate_hash: str | None = None
            try:
                candidate_hash = (
                    (image_info or {}).get("sha256")
                    or image_response.get("sha256")
                )
            except Exception:  # noqa: BLE001
                candidate_hash = None

            # Preferred: if bytes provided emit per-display swap files; else fallback to legacy URL conversion
            raw_bytes = None
            content_type = None
            if isinstance(image_info, dict):
                raw_bytes = image_info.get("bytes")
                content_type = image_info.get("content_type") or image_info.get("mime_type")

            # We will build a per-display mapping of URLs so each display has its own path (avoids overwrite collisions)
            per_display_urls: dict[str, str] = {}
            base_seed_url: str | None = None

            swap_path = None  # ensure defined for later image_path usage
            if raw_bytes:
                # We'll defer writing until after deciding distribution necessity; capture bytes length for logs
                base_seed_url = "bytes://pending"  # marker for diagnostics
            else:
                # Legacy path: attempt URL conversion from string/image field
                converted = _convert_image_to_url(image_info)
                if not converted:
                    return {
                        "displays_updated": 0,
                        "errors": ["Unable to convert image to accessible URL"]
                    }
                base_seed_url = converted
            
            # For new content, always distribute. For existing content, only if scene assignments need updates
            should_distribute = False

            # Hash-based gating: if hash unchanged, treat as existing even if channel reports 'new'
            scene_key = f"{scene.id}:{scene.channels[0].get('subchannel_id') if scene.channels else ''}"
            last_hash = _last_scene_content_hash.get(scene_key)
            content_unchanged = bool(candidate_hash and last_hash and candidate_hash == last_hash)

            if distribution_mode == "new":
                if content_unchanged:
                    logger.info(
                        "distribution.skipped unchanged hash for scene %s (mode=new, displays=%d)",
                        scene.id,
                        len(assigned_displays),
                    )
                    # Defer to 'existing' path logic: only distribute if scene assignment mismatches
                    distribution_mode = "existing"
                else:
                    # New content available - distribute
                    should_distribute = True
                    logger.info(
                        "New content available for scene %s distributing to %d displays",
                        scene.id,
                        len(assigned_displays),
                    )
            elif distribution_mode in ["existing", "cached"]:
                # No new content, check if any displays need scene assignment updates
                for display in assigned_displays:
                    current_scene = display.get("current_scene_id")
                    target_scene = str(scene.id)
                    if current_scene != target_scene and current_scene != scene.id:
                        should_distribute = True
                        logger.info("Display %s needs scene assignment update", display["id"])
                        break
                
                if not should_distribute:
                    logger.info(
                        "No new content and all displays have correct scene assignment; skipping distribution"
                    )
                    return {
                        "displays_updated": 0,
                        "errors": [],
                        "message": "No distribution needed - content unchanged and displays up to date"
                    }
            else:
                # Unknown distribution mode, be conservative and distribute
                should_distribute = True
                logger.warning(
                    "Unknown distribution mode '%s', distributing to be safe", distribution_mode
                )
            
            # Send display_image commands to each display via MQTT
            for display in assigned_displays:
                try:
                    if mqtt_scene_service.is_connected():
                        device_id = display["hostname"] or display["id"]
                        assignment_id = f"display-{uuid.uuid4().hex[:8]}"
                        # Determine or create per-display swap URL if raw bytes available
                        if raw_bytes:
                            swap_path, swap_url, _written = save_swap_image(
                                scene_id=str(scene.id),
                                display_id=device_id,
                                image_bytes=raw_bytes,
                                content_type=content_type,
                            )
                            if not swap_url:
                                errors.append(f"swap_save_failed:{device_id}")
                                continue
                            per_display_urls[device_id] = swap_url
                            use_url = swap_url
                        else:
                            use_url = base_seed_url  # identical for all displays legacy path

                        logger.debug(
                            "Sending display_image command to display %s url=%s raw_bytes=%s", 
                            device_id,
                            use_url,
                            bool(raw_bytes),
                        )
                        success = await mqtt_scene_service.send_display_image(
                            device_id=device_id,
                            image_url=use_url,
                            assignment_id=assignment_id,
                        )
                        
                        if success:
                            displays_updated += 1
                            logger.debug(
                                "Sent display_image command to display %s", display["id"]
                            )
                            # Record last image metadata (width/height unknown here unless channel provided)
                            display_last_image_store.update(
                                device_id=device_id,
                                assignment_id=assignment_id,
                                image_url=use_url,
                                image_width=image_info.get("width") if isinstance(image_info, dict) else None,
                                image_height=image_info.get("height") if isinstance(image_info, dict) else None,
                                image_format=image_info.get("format") if isinstance(image_info, dict) else None,
                                scene_id=str(scene.id),
                                subchannel_id=scene.channels[0].get("subchannel_id") if scene.channels else None,
                                image_path=str(swap_path) if raw_bytes and swap_path else None,
                            )
                            # Persist record
                            try:
                                logger.debug(
                                    "persist.image.attempt device=%s scene=%s assignment=%s url=%s",
                                    device_id,
                                    scene.id,
                                    assignment_id,
                                    use_url,
                                )
                                with SessionLocal() as p_db:
                                    persistence = DisplayImagePersistenceService(p_db)
                                    rec = persistence.store_distribution_image(
                                        display_id=device_id,
                                        scene_id=str(scene.id),
                                        subchannel_id=scene.channels[0].get("subchannel_id") if scene.channels else None,
                                        assignment_id=assignment_id,
                                        image_url=use_url,
                                        width=image_info.get("width") if isinstance(image_info, dict) else None,
                                        height=image_info.get("height") if isinstance(image_info, dict) else None,
                                        image_format=image_info.get("format") if isinstance(image_info, dict) else None,
                                        source="distribution",
                                        retain_history=True,
                                    )
                                    logger.info(
                                        "persist.image stored device=%s scene=%s id=%s thumb=%s read_only=%s",
                                        device_id,
                                        scene.id,
                                        getattr(rec, 'id', None),
                                        getattr(rec, 'thumbnail_path', None),
                                        getattr(persistence, 'read_only_mode', None),
                                    )
                            except Exception as perr:  # noqa: BLE001
                                logger.warning("persist.image failure device=%s err=%s", device_id, perr)
                        else:
                            errors.append(f"MQTT send failed for display {display['id']}")
                    else:
                        errors.append("MQTT service not connected")
                        
                except Exception as e:  # noqa: BLE001
                    errors.append(f"Error sending to display {display['id']}: {e}")
                    logger.error("distribution.send_error display=%s err=%s", display["id"], e)
            
            # After distribution, optionally prune swap directory (best-effort)
            if getattr(settings, "display_swap_enabled", True):
                try:
                    prune_swap(
                        max_files_per_display=getattr(
                            settings,
                            "display_swap_max_files_per_display",
                            25,
                        )
                    )
                except Exception:  # noqa: BLE001
                    pass

            # Update last hash only if we actually distributed or if we have a candidate hash and
            # there was no need to distribute but content remains the same (keeps baseline correct).
            if candidate_hash:
                try:
                    if displays_updated > 0 or content_unchanged:
                        _last_scene_content_hash[scene_key] = candidate_hash
                except Exception:  # noqa: BLE001
                    pass

            return {
                "displays_updated": displays_updated,
                "errors": errors,
                "image_url": base_seed_url if not raw_bytes else None,
                "swap_distributed": bool(raw_bytes),
            }
            
        except (ImageConversionError, ChannelRequestError) as e:
            logger.error("distribution.domain_error scene_id=%s error=%s", scene.id, e)
            return {
                "displays_updated": 0,
                "errors": [str(e)]
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("distribution.unexpected scene_id=%s error=%s", scene.id, e)
            return {
                "displays_updated": 0,
                "errors": [str(e)]
            }


# Global instance
scheduler_worker = SchedulerWorker()
