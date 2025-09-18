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
import httpx
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..db.base import SessionLocal
from ..db.models import SchedulerJob, SchedulerJobSceneAssignment, Scene, DisplayClient
from ..schemas.scheduler import ExecutionStatus, TriggerReason
from ..services.scheduler_service import SchedulerService
from ..services.mdns_discovery import mdns_discovery_service
from ..services.mqtt.publisher import mqtt_scene_service
from ..services.plugin_discovery import plugin_discovery_service

logger = logging.getLogger(__name__)


class SchedulerWorker:
    """Background worker for executing scheduled jobs"""
    
    def __init__(self):
        self.running = False
        self._task = None
        self.poll_interval = 30  # Check for due jobs every 30 seconds
        
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
            try:
                await self._process_due_jobs()
            except Exception as e:
                logger.error(f"Error in scheduler worker loop: {e}", exc_info=True)
            
            # Wait for the next polling interval
            await asyncio.sleep(self.poll_interval)
    
    async def _process_due_jobs(self):
        """Process all jobs that are due for execution"""
        try:
            with SessionLocal() as db:
                scheduler_service = SchedulerService(db)
                due_jobs = await scheduler_service.get_due_jobs(limit=50)
                
                if not due_jobs:
                    return
                
                logger.info(f"Processing {len(due_jobs)} due jobs")
                
                for job in due_jobs:
                    try:
                        await self._execute_job(job, scheduler_service)
                    except Exception as e:
                        logger.error(f"Failed to execute job {job.id}: {e}", exc_info=True)
                        
        except Exception as e:
            logger.error(f"Error processing due jobs: {e}", exc_info=True)
    
    async def _execute_job(self, job: SchedulerJob, scheduler_service: SchedulerService):
        """Execute a single scheduler job"""
        # Lock the job to prevent concurrent execution
        locked = await scheduler_service.lock_job(job.id)
        if not locked:
            logger.warning(f"Could not lock job {job.id}, skipping")
            return
        
        # Start execution tracking
        execution_id = await scheduler_service.start_execution(
            job.id, 
            worker_id="scheduler-worker",
            trigger_reason=TriggerReason.SCHEDULED
        )
        
        try:
            logger.info(f"Executing job {job.id} ({job.name}) - action: {job.action_type}")
            
            if job.action_type == "refresh_scene":
                result = await self._execute_refresh_scene(job, scheduler_service)
            else:
                logger.warning(f"Unknown action type: {job.action_type}")
                result = {
                    "success": False,
                    "error": f"Unknown action type: {job.action_type}"
                }
            
            # Complete execution tracking
            status = ExecutionStatus.SUCCESS if result.get("success") else ExecutionStatus.FAILED
            await scheduler_service.complete_execution(
                execution_id,
                status,
                output_data=result,
                error_message=result.get("error"),
                affected_scenes=result.get("affected_scenes", [])
            )
            
            logger.info(f"Job {job.id} completed with status: {status.value}")
            
        except Exception as e:
            # Mark execution as failed
            await scheduler_service.complete_execution(
                execution_id,
                ExecutionStatus.FAILED,
                error_message=str(e)
            )
            logger.error(f"Job {job.id} execution failed: {e}", exc_info=True)
            
        finally:
            # Always unlock the job
            await scheduler_service.unlock_job(job.id)
    
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
            
        except Exception as e:
            logger.error(f"Error executing refresh_scene: {e}", exc_info=True)
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
                
                # Request image from channel
                image_response = await self._request_channel_image(
                    channel_id, subchannel_id, assignment.refresh_method
                )
                
                if not image_response.get("success"):
                    return {
                        "scene_id": assignment.scene_id,
                        "success": False,
                        "error": f"Channel image request failed: {image_response.get('error', 'Unknown error')}"
                    }
                
                # Distribute image to displays assigned to this scene
                distribution_result = await self._distribute_to_displays(scene, image_response)
                
                return {
                    "scene_id": assignment.scene_id,
                    "success": True,
                    "channel_id": channel_id,
                    "subchannel_id": subchannel_id,
                    "image_info": image_response.get("image", {}),
                    "displays_updated": distribution_result.get("displays_updated", 0),
                    "distribution_errors": distribution_result.get("errors", [])
                }
                
        except Exception as e:
            logger.error(f"Error refreshing scene {assignment.scene_id}: {e}", exc_info=True)
            return {
                "scene_id": assignment.scene_id,
                "success": False,
                "error": str(e)
            }
    
    async def _request_channel_image(
        self, 
        channel_id: str, 
        subchannel_id: Optional[str] = None,
        refresh_method: str = "content_refresh"
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
            request_data = {
                "settings": {
                    "resolution": [800, 600],  # Default resolution
                    "orientation": "landscape",
                    "distribution": "new"  # Always get new content for scheduled refreshes
                }
            }
            
            # Add subchannel/gallery information if specified
            if subchannel_id:
                request_data["gallery_id"] = subchannel_id
                request_data["settings"]["subChannelId"] = subchannel_id
            
            # Call the channel's request_image method
            logger.info(f"Requesting image from channel {channel_id} with subchannel {subchannel_id}")
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
                
        except Exception as e:
            logger.error(f"Error requesting image from channel {channel_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
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
                            "type": "discovered"
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
                            "type": "database"
                        })
            
            if not assigned_displays:
                logger.info(f"No displays assigned to scene {scene.id}")
                return {
                    "displays_updated": 0,
                    "errors": ["No displays assigned to scene"]
                }
            
            logger.info(f"Distributing to {len(assigned_displays)} displays for scene {scene.id}")
            
            # Extract image information
            image_info = image_response.get("image", {})
            image_path = image_info.get("image")  # This should be the path to the image
            
            if not image_path:
                return {
                    "displays_updated": 0,
                    "errors": ["No image path in channel response"]
                }
            
            # Send image to each display via MQTT
            for display in assigned_displays:
                try:
                    if mqtt_scene_service.is_connected():
                        # For now, we'll send a scene refresh command
                        # In the future, this could send the actual image data
                        success = await mqtt_scene_service.assign_scene_to_device(
                            device_id=display["hostname"] or display["id"],
                            scene_id=str(scene.id),
                            assignment_id=f"refresh-{uuid.uuid4().hex[:8]}"
                        )
                        
                        if success:
                            displays_updated += 1
                            logger.info(f"Sent refresh command to display {display['id']}")
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
                "image_path": image_path
            }
            
        except Exception as e:
            logger.error(f"Error distributing to displays: {e}", exc_info=True)
            return {
                "displays_updated": 0,
                "errors": [str(e)]
            }


# Global instance
scheduler_worker = SchedulerWorker()