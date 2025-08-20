"""
Enhanced Image Generation Architecture for Mimir API

This implements a background scheduler that respects channel update frequencies
while providing fast API responses through intelligent caching.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

class ImageGenerationScheduler:
    """
    Background scheduler that generates images based on channel update schedules
    """
    
    def __init__(self):
        self.image_cache: Dict[str, dict] = {}
        self.generation_in_progress: Dict[str, bool] = {}
        self.running = False
        
    async def start(self):
        """Start the background image generation scheduler"""
        self.running = True
        asyncio.create_task(self._scheduler_loop())
        
    async def _scheduler_loop(self):
        """Main scheduler loop - checks every minute for updates needed"""
        while self.running:
            try:
                await self._check_and_generate_images()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(60)
                
    async def _check_and_generate_images(self):
        """Check all channels and generate images if needed"""
        # Get all active channels from database
        channels = await self._get_active_channels()
        
        for channel in channels:
            if await self._should_generate_image(channel):
                await self._generate_image_background(channel)
                
    async def _should_generate_image(self, channel) -> bool:
        """Determine if channel needs new image based on update schedule"""
        channel_id = channel['id']
        
        # Check if generation already in progress
        if self.generation_in_progress.get(channel_id, False):
            return False
            
        # Get last generation time
        cached_entry = self.image_cache.get(channel_id)
        if not cached_entry:
            return True  # No cache, need to generate
            
        # Check if enough time has passed based on channel schedule
        last_generated = cached_entry['timestamp']
        update_schedule = channel['config'].get('update_schedule', {})
        
        interval_seconds = self._parse_schedule_to_seconds(update_schedule)
        time_since_last = time.time() - last_generated
        
        return time_since_last >= interval_seconds
        
    def _parse_schedule_to_seconds(self, schedule: dict) -> int:
        """Convert channel update_schedule to seconds"""
        unit = schedule.get('unit', 'hours')
        duration = schedule.get('duration', 1)
        
        multipliers = {
            'seconds': 1,
            'minutes': 60, 
            'hours': 3600,
            'days': 86400
        }
        
        return duration * multipliers.get(unit, 3600)  # Default to hours
        
    async def _generate_image_background(self, channel):
        """Generate image for channel in background"""
        channel_id = channel['id']
        
        try:
            self.generation_in_progress[channel_id] = True
            
            # Get channel implementation
            channel_impl = await self._get_channel_implementation(channel_id)
            if not channel_impl:
                return
                
            # Get current settings
            settings = await self._get_channel_settings(channel_id)
            
            # Generate image using channel's render_image method
            image_path = await channel_impl.render_image(
                resolution=(1920, 1080),  # Default resolution
                orientation='landscape',
                settings=settings
            )
            
            # Update cache
            self.image_cache[channel_id] = {
                'image_path': image_path,
                'timestamp': time.time(),
                'settings_hash': hash(str(settings))
            }
            
            # Broadcast update event
            await self._broadcast_image_updated(channel_id, image_path)
            
        except Exception as e:
            print(f"Error generating image for {channel_id}: {e}")
        finally:
            self.generation_in_progress[channel_id] = False
            
    async def get_latest_image(self, channel_id: str) -> Optional[str]:
        """Get latest cached image, generate on-demand if needed"""
        cached_entry = self.image_cache.get(channel_id)
        
        if cached_entry:
            return cached_entry['image_path']
            
        # No cached image, generate immediately
        channel = await self._get_channel_by_id(channel_id)
        if channel:
            await self._generate_image_background(channel)
            # Return cached result after generation
            cached_entry = self.image_cache.get(channel_id)
            if cached_entry:
                return cached_entry['image_path']
                
        return None
        
    async def invalidate_cache(self, channel_id: str):
        """Invalidate cache when settings change"""
        if channel_id in self.image_cache:
            del self.image_cache[channel_id]
            
    # Placeholder methods - these would integrate with your existing system
    async def _get_active_channels(self):
        """Get all active channels from database"""
        pass
        
    async def _get_channel_implementation(self, channel_id: str):
        """Get channel implementation instance"""
        pass
        
    async def _get_channel_settings(self, channel_id: str):
        """Get current channel settings"""
        pass
        
    async def _get_channel_by_id(self, channel_id: str):
        """Get channel data by ID"""
        pass
        
    async def _broadcast_image_updated(self, channel_id: str, image_path: str):
        """Broadcast WebSocket event for image updates"""
        pass

# Global scheduler instance
image_scheduler = ImageGenerationScheduler()

# Integration with existing API endpoints
@app.on_event("startup")
async def startup_image_scheduler():
    """Start the image generation scheduler on app startup"""
    await image_scheduler.start()

@app.get("/api/channels/{channel_id}/latest_image")
async def get_channel_latest_image(channel_id: str):
    """Get the latest cached image for a channel"""
    image_path = await image_scheduler.get_latest_image(channel_id)
    if image_path:
        return {"image_path": image_path, "cached": True}
    else:
        raise HTTPException(status_code=404, detail="No image available")

@app.post("/api/channels/{channel_id}/settings")
async def update_channel_settings_with_invalidation(
    channel_id: str, 
    settings: Dict[str, Any], 
    db: Session = Depends(get_db)
):
    """Update settings and invalidate image cache"""
    # ... existing settings update logic ...
    
    # Invalidate image cache to trigger regeneration
    await image_scheduler.invalidate_cache(channel_id)
    
    return {"message": "Settings updated, image will regenerate"}
