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
import uuid
import logging
import base64
import os  # May be used elsewhere; keep if referenced
import time
from datetime import UTC, datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from functools import partial

# Removed unused sqlalchemy imports (Session, and_) to reduce dependencies

from ..db.base import SessionLocal
from ..db.models import SchedulerJob, SchedulerJobSceneAssignment, Scene, DisplayClient
from ..schemas.scheduler import ExecutionStatus, TriggerReason
from ..services.scheduler_service import SchedulerService
from ..services.mdns_discovery import mdns_discovery_service
from ..services.mqtt.publisher import mqtt_scene_service
from ..services.plugin_discovery import plugin_discovery_service
from ..config import settings
from ..services.display_last_image import display_last_image_store

logger = logging.getLogger(__name__)


# -----------------------------------------------------
# Custom exception types to classify failure domains
# -----------------------------------------------------
class ChannelRequestError(Exception):
    """Raised when a channel plugin request fails (logic / plugin layer)."""


class ImageConversionError(Exception):
    """Raised when converting or persisting image data fails."""


class DistributionError(Exception):
    """Raised when distributing image data to displays encounters a non-recoverable issue."""


def _convert_image_to_url(image_info: Dict[str, Any]) -> Optional[str]:
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


def _save_base64_and_get_url(image_info: Dict[str, Any], base_url: str) -> Optional[str]:
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
        logger.info(f"Scheduler worker loop started (polling every {self.poll_interval}s)")
        
        while self.running:
            # Guardrail: we intentionally keep a loop-level exception barrier so a single
            # unhandled error does not terminate the scheduler background task.
            try:
                self._maybe_cleanup_temp_images()  # best-effort
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
    ) -> Optional[str]:
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
    ) -> Optional[str]:
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

        cutoff_ts = datetime.now(UTC).timestamp() - (max_age_min * 60)
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
    
    async def _execute_refresh_scene(self, job: SchedulerJob, scheduler_service: SchedulerService) -> Dict[str, Any]:
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
                except Exception as e:
                    logger.error(f"Failed to refresh scene {assignment.scene_id}: {e}")
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
    
    async def _refresh_single_scene(self, assignment: SchedulerJobSceneAssignment) -> Dict[str, Any]:
        """Refresh a single scene by requesting new content and distributing to displays"""
        try:
            # Get the scene
            with SessionLocal() as db:
                scene = db.query(Scene).filter(Scene.id == assignment.scene_id).first()
                if not scene:
                    return {
                        "scene_id": assignment.scene_id,
                        "success": False,
                        "error": "Scene not found"
                    }
                
                # Extract channel configuration from scene
                if not scene.channels:
                    return {
                        "scene_id": assignment.scene_id,
                        "success": False,
                        "error": "Scene has no channel configuration"
                    }
                
                # Assuming single channel model for now
                channel_config = scene.channels[0] if isinstance(scene.channels, list) else scene.channels
                channel_id = channel_config.get("channel_id")
                subchannel_id = channel_config.get("subchannel_id")
                
                if not channel_id:
                    return {
                        "scene_id": assignment.scene_id,
                        "success": False,
                        "error": "No channel_id in scene configuration"
                    }
                
                # Collect assigned displays with resolution/orientation info
                assigned_displays = self._collect_assigned_displays(scene)
                if not assigned_displays:
                    return {
                        "scene_id": assignment.scene_id,
                        "success": False,
                        "error": "No displays assigned to scene"
                    }

                # Group displays by (resolution, orientation)
                groups: Dict[Tuple[int, int, str], List[Dict[str, Any]]] = {}
                for d in assigned_displays:
                    key = (d["width"], d["height"], d["orientation"])
                    groups.setdefault(key, []).append(d)

                logger.info(
                    "scene.refresh.grouping scene_id=%s groups=%d", scene.id, len(groups)
                )

                total_displays_updated = 0
                all_errors: List[str] = []
                image_info_samples: List[Dict[str, Any]] = []

                # For each group request an appropriately sized image once
                for (w, h, orientation), display_group in groups.items():
                    try:
                        image_response = await self._request_channel_image(
                            channel_id,
                            subchannel_id,
                            assignment.refresh_method,
                            resolution=[w, h],
                            orientation=orientation,
                        )
                    except ChannelRequestError as e:
                        err = f"Channel image request failed for group {w}x{h}/{orientation}: {e}"
                        logger.error(err)
                        all_errors.append(err)
                        continue

                    if not image_response.get("success"):
                        err = f"Channel group request unsuccessful {w}x{h}/{orientation}: {image_response.get('error')}"
                        all_errors.append(err)
                        continue

                    image_info = image_response.get("image", {})
                    image_info_samples.append(image_info)

                    # Convert image to accessible URL
                    image_url = _convert_image_to_url(image_info)
                    if not image_url:
                        all_errors.append(
                            f"Unable to convert image to URL for group {w}x{h}/{orientation}"
                        )
                        continue

                    distribution_mode = image_info.get("distribution_mode")
                    # For simplicity we always distribute new/cached/existing here; policy refinement can be added later
                    for display in display_group:
                        device_id = display["device_id"]
                        try:
                            if mqtt_scene_service.is_connected():
                                assignment_id = f"display-{uuid.uuid4().hex[:8]}"
                                success = await mqtt_scene_service.send_display_image(
                                    device_id=device_id,
                                    image_url=image_url,
                                    assignment_id=assignment_id,
                                )
                                if success:
                                    total_displays_updated += 1
                                    display_last_image_store.update(
                                        device_id=device_id,
                                        assignment_id=assignment_id,
                                        image_url=image_url,
                                        image_width=w,
                                        image_height=h,
                                        image_format=None,
                                        scene_id=str(scene.id),
                                        subchannel_id=subchannel_id,
                                    )
                                else:
                                    all_errors.append(
                                        f"MQTT send failed device={device_id} group={w}x{h}/{orientation}"
                                    )
                            else:
                                all_errors.append("MQTT not connected")
                        except Exception as e:  # noqa: BLE001
                            all_errors.append(
                                f"Error sending to device {device_id}: {e}"
                            )

                return {
                    "scene_id": assignment.scene_id,
                    "success": total_displays_updated > 0,
                    "channel_id": channel_id,
                    "subchannel_id": subchannel_id,
                    "image_samples": image_info_samples[:3],  # include a few samples for inspection
                    "displays_updated": total_displays_updated,
                    "distribution_errors": all_errors,
                }
                
        except (ChannelRequestError, ImageConversionError, DistributionError) as e:
            logger.error("scene.refresh.domain_error scene_id=%s error=%s", assignment.scene_id, e)
            return {
                "scene_id": assignment.scene_id,
                "success": False,
                "error": str(e)
            }
        except Exception as e:  # noqa: BLE001
            logger.exception("scene.refresh.unexpected scene_id=%s error=%s", assignment.scene_id, e)
            return {
                "scene_id": assignment.scene_id,
                "success": False,
                "error": str(e)
            }
    
    async def _request_channel_image(
        self,
        channel_id: str,
        subchannel_id: Optional[str] = None,
        refresh_method: str = "content_refresh",
        *,
        resolution: Optional[List[int]] = None,
        orientation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request an image from a channel using the plugin system"""
        try:
            # Get the channel plugin
            plugin = plugin_discovery_service.get_plugin(channel_id)
            if not plugin or not plugin.instance:
                return {
                    "success": False,
                    "error": f"Channel plugin {channel_id} not found or not loaded"
                }
            
            # Prepare request data
            res = resolution if (resolution and len(resolution) == 2) else [800, 600]
            orient = orientation or "landscape"
            request_data: Dict[str, Any] = {
                "settings": {
                    "resolution": res,
                    "orientation": orient,
                    "distribution": "new",  # scheduler always requests fresh content per group
                }
            }
            
            # Add subchannel/gallery information if specified
            if subchannel_id:
                request_data["gallery_id"] = subchannel_id
                request_data["settings"]["subChannelId"] = subchannel_id
            
            # Call the channel's request_image method
            logger.info(
                "channel.request group channel=%s subchannel=%s resolution=%sx%s orientation=%s",
                channel_id,
                subchannel_id,
                res[0],
                res[1],
                orient,
            )
            image_response = await plugin.instance.request_image(request_data)
            
            if image_response and image_response.get("success"):
                return {
                    "success": True,
                    "image": image_response
                }
            else:
                return {
                    "success": False,
                    "error": f"Channel returned unsuccessful response: {image_response}"
                }
                
        except Exception as e:  # noqa: BLE001
            # Wrap in domain-specific error so caller can classify
            raise ChannelRequestError(str(e)) from e
            return {
                "success": False,
                "error": str(e)
            }

    # ----------------------------------------------
    # Display collection & grouping helpers
    # ----------------------------------------------
    def _collect_assigned_displays(self, scene: Scene) -> List[Dict[str, Any]]:
        """Gather displays (discovered + DB) assigned to a scene with resolution & orientation.

        Returns list of dicts: {device_id, width, height, orientation}
        """
        collected: Dict[str, Dict[str, Any]] = {}

        # mDNS discovered displays
        if mdns_discovery_service.is_running:
            try:
                discovered = mdns_discovery_service.get_discovered_displays()
                for d in discovered:
                    if d.assigned_scene_id == scene.id or d.assigned_scene_id == str(scene.id):
                        w, h = self._parse_resolution_string(d.resolution)
                        collected[d.display_id] = {
                            "device_id": d.hostname or d.display_id,
                            "width": w,
                            "height": h,
                            "orientation": d.properties.get("orientation", "landscape"),
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
                w = display.width or 800
                h = display.height or 600
                collected[display.id] = {
                    "device_id": display.hostname or display.id,
                    "width": w,
                    "height": h,
                    "orientation": display.orientation or "landscape",
                }

        return list(collected.values())

    @staticmethod
    def _parse_resolution_string(res_str: Optional[str]) -> Tuple[int, int]:
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
    
    async def _distribute_to_displays(self, scene: Scene, image_response: Dict[str, Any]) -> Dict[str, Any]:
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
                logger.info(f"No displays assigned to scene {scene.id}")
                return {
                    "displays_updated": 0,
                    "errors": ["No displays assigned to scene"]
                }
            
            logger.info(f"Distributing to {len(assigned_displays)} displays for scene {scene.id}")
            
            # Extract image information and convert to URL
            image_info = image_response.get("image", {})
            distribution_mode = image_info.get("distribution_mode")
            
            # Convert image to publicly accessible URL
            image_url = _convert_image_to_url(image_info)
            if not image_url:
                return {
                    "displays_updated": 0,
                    "errors": ["Unable to convert image to accessible URL"]
                }
            
            # For new content, always distribute. For existing content, only if scene assignments need updates
            should_distribute = False
            
            if distribution_mode == "new":
                # New content available - always distribute
                should_distribute = True
                logger.info(f"New content available for scene {scene.id}, distributing to {len(assigned_displays)} displays")
            elif distribution_mode in ["existing", "cached"]:
                # No new content, check if any displays need scene assignment updates
                for display in assigned_displays:
                    current_scene = display.get("current_scene_id")
                    target_scene = str(scene.id)
                    if current_scene != target_scene and current_scene != scene.id:
                        should_distribute = True
                        logger.info(f"Display {display['id']} needs scene assignment update")
                        break
                
                if not should_distribute:
                    logger.info(f"No new content and all displays have correct scene assignment, skipping distribution")
                    return {
                        "displays_updated": 0,
                        "errors": [],
                        "message": "No distribution needed - content unchanged and displays up to date"
                    }
            else:
                # Unknown distribution mode, be conservative and distribute
                should_distribute = True
                logger.warning(f"Unknown distribution mode '{distribution_mode}', distributing to be safe")
            
            # Send display_image commands to each display via MQTT

            # Send display_image commands to each display via MQTT
            for display in assigned_displays:
                try:
                    if mqtt_scene_service.is_connected():
                        device_id = display["hostname"] or display["id"]
                        assignment_id = f"display-{uuid.uuid4().hex[:8]}"
                        
                        # Send display_image command directly - this is the correct architecture
                        logger.debug(f"Sending display_image command to display {device_id}")
                        success = await mqtt_scene_service.send_display_image(
                            device_id=device_id,
                            image_url=image_url,
                            assignment_id=assignment_id,
                        )
                        
                        if success:
                            displays_updated += 1
                            logger.debug(f"Sent display_image command to display {display['id']}")
                            # Record last image metadata (width/height unknown here unless channel provided)
                            display_last_image_store.update(
                                device_id=device_id,
                                assignment_id=assignment_id,
                                image_url=image_url,
                                image_width=None,
                                image_height=None,
                                image_format=None,
                                scene_id=str(scene.id),
                                subchannel_id=scene.channels[0].get("subchannel_id") if scene.channels else None,
                            )
                        else:
                            errors.append(f"MQTT send failed for display {display['id']}")
                    else:
                        errors.append("MQTT service not connected")
                        
                except Exception as e:
                    error_msg = f"Error sending to display {display['id']}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            return {
                "displays_updated": displays_updated,
                "errors": errors,
                "image_url": image_url
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