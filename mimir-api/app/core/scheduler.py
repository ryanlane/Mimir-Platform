"""
Modern Job Scheduler Service
Replaces ad-hoc asyncio.create_task() calls with durable APScheduler-based background jobs
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class SchedulerService:
    """Modern background job scheduler using APScheduler"""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        
    def setup_scheduler(self):
        """Initialize the APScheduler with memory job store"""
        try:
            # Create job store using memory to avoid serialization issues
            jobstore = MemoryJobStore()
            
            # Configure scheduler
            self.scheduler = AsyncIOScheduler(
                jobstores={'default': jobstore},
                timezone='UTC',
                job_defaults={
                    'coalesce': True,        # Combine multiple missed runs into one
                    'max_instances': 1,      # Prevent multiple instances of same job
                    'misfire_grace_time': 60 # Allow 60s grace for missed jobs
                }
            )
            
            # Add event listeners for monitoring
            self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
            self.scheduler.add_listener(self._job_missed, EVENT_JOB_MISSED)
            
            logger.info("APScheduler initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup scheduler: {e}")
            return False
    
    async def start(self):
        """Start the scheduler"""
        if self.scheduler and not self.is_running:
            try:
                self._start_time = datetime.now(timezone.utc)
                self.scheduler.start()
                self.is_running = True
                logger.info("APScheduler started")
                
                # Setup default jobs
                await self._setup_default_jobs()
                
            except Exception as e:
                logger.error(f"Failed to start scheduler: {e}")
                raise
    
    async def stop(self):
        """Stop the scheduler gracefully"""
        if self.scheduler and self.is_running:
            try:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("APScheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")
    
    async def _setup_default_jobs(self):
        """Setup the standard background jobs"""
        
        # Distribution monitoring job (replaces the old asyncio.create_task)
        if settings.distribution_enabled:
            self.scheduler.add_job(
                func=self._distribution_monitoring_job,
                trigger='interval',
                seconds=30,  # Every 30 seconds
                id='distribution_monitoring',
                replace_existing=True,
                jitter=5  # Add 0-5 second jitter to prevent thundering herd
            )
            logger.info("Scheduled distribution monitoring job (30s interval)")
        
        # mDNS discovery monitoring job 
        if settings.mdns_discovery_enabled:
            self.scheduler.add_job(
                func=self._mdns_monitoring_job,
                trigger='interval', 
                seconds=settings.mdns_update_interval,
                id='mdns_monitoring',
                replace_existing=True,
                jitter=3
            )
            logger.info(f"Scheduled mDNS monitoring job ({settings.mdns_update_interval}s interval)")
        
        # Plugin discovery job (periodic refresh)
        self.scheduler.add_job(
            func=self._plugin_refresh_job,
            trigger='interval',
            minutes=10,  # Every 10 minutes
            id='plugin_refresh',
            replace_existing=True
        )
        logger.info("Scheduled plugin refresh job (10m interval)")
        
        # Database cleanup job (daily)
        self.scheduler.add_job(
            func=self._database_cleanup_job,
            trigger='cron',
            hour=2,  # 2 AM daily
            id='database_cleanup',
            replace_existing=True
        )
        logger.info("Scheduled database cleanup job (daily 2 AM)")
    
    async def _distribution_monitoring_job(self):
        """Background job for distribution performance monitoring"""
        try:
            from app.services.distribution import distribution_service
            from app.core.metrics import metrics
            
            # Get distribution status for all active scenes
            overview = await distribution_service.get_distribution_overview()
            
            if overview.get("status") == "success":
                # Record metrics
                total_scenes = overview.get("total_scenes", 0)
                active_distributions = overview.get("active_distributions", 0)
                
                logger.debug(f"Distribution monitoring: {total_scenes} scenes, {active_distributions} active")
                
                # The actual broadcasting to WebSocket clients is handled by the distribution service
                # This job just ensures the monitoring loop continues to run
                await distribution_service.monitor_distribution_performance()
                
            else:
                logger.warning(f"Distribution monitoring failed: {overview.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Distribution monitoring job failed: {e}")
            # Don't re-raise - let the job continue on next interval
    
    async def _mdns_monitoring_job(self):
        """Background job for mDNS discovery health monitoring"""
        try:
            from app.services.mdns_discovery import mdns_discovery_service
            from app.core.metrics import metrics
            
            if mdns_discovery_service.is_running:
                # This triggers the internal monitoring loop that checks for offline displays
                stats = mdns_discovery_service.get_discovery_stats()
                
                logger.debug(f"mDNS monitoring: {stats.get('total_discovered', 0)} total, "
                           f"{stats.get('online_displays', 0)} online")
                
            else:
                logger.warning("mDNS discovery service not running")
                
        except Exception as e:
            logger.error(f"mDNS monitoring job failed: {e}")
    
    async def _plugin_refresh_job(self):
        """Background job to refresh plugin discovery"""
        try:
            from app.services.plugin_discovery import plugin_discovery_service
            
            # Refresh plugin discovery periodically
            # This helps detect new plugins that may have been added
            plugins = await plugin_discovery_service.discover_plugins()
            logger.debug(f"Plugin refresh: {len(plugins)} plugins discovered")
            
        except Exception as e:
            logger.error(f"Plugin refresh job failed: {e}")
    
    async def _database_cleanup_job(self):
        """Background job for database maintenance"""
        try:
            from app.db.base import SessionLocal
            
            # Example cleanup operations
            with SessionLocal() as db:
                # Clean up old job executions (keep last 1000)
                cleanup_query = """
                DELETE FROM apscheduler_jobs 
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id FROM apscheduler_jobs 
                        ORDER BY next_run_time DESC 
                        LIMIT 1000
                    ) t
                )
                """
                # Note: This is a simple example - adjust based on your needs
                
            logger.info("Database cleanup completed")
            
        except Exception as e:
            logger.error(f"Database cleanup job failed: {e}")
    
    def _job_executed(self, event):
        """Handle successful job execution"""
        logger.debug(f"Job '{event.job_id}' executed successfully")
    
    def _job_error(self, event):
        """Handle job execution errors"""
        logger.error(f"Job '{event.job_id}' failed: {event.exception}")
    
    def _job_missed(self, event):
        """Handle missed job executions"""
        logger.warning(f"Job '{event.job_id}' missed execution")
    
    def add_job(self, func, trigger, **kwargs):
        """Add a custom job to the scheduler"""
        if self.scheduler:
            return self.scheduler.add_job(func, trigger, **kwargs)
        else:
            raise RuntimeError("Scheduler not initialized")
    
    def remove_job(self, job_id: str):
        """Remove a job from the scheduler"""
        if self.scheduler:
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"Removed job: {job_id}")
            except Exception as e:
                logger.error(f"Failed to remove job {job_id}: {e}")
    
    def get_jobs(self) -> Dict[str, Any]:
        """Get information about all scheduled jobs"""
        if not self.scheduler:
            return {}
        
        jobs = {}
        for job in self.scheduler.get_jobs():
            jobs[job.id] = {
                'id': job.id,
                'name': job.name,
                'func': str(job.func),
                'trigger': str(job.trigger),
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'coalesce': job.coalesce,
                'max_instances': job.max_instances
            }
        return jobs

# Global scheduler service instance
scheduler_service = SchedulerService()
