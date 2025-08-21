"""
Example Channel - Simple implementation for testing
"""

from typing import Dict, Any, Optional, Tuple
import json
import datetime
from pathlib import Path
from PIL import Image

class ExampleChannel:
    """Simple example channel for testing the v2.1 system"""
    
    def __init__(self, channel_dir: str):
        self.channel_dir = Path(channel_dir)
        self.config_path = self.channel_dir / "config.json"
        self._config = None
        
    @property
    def id(self) -> str:
        return "example_channel"
        
    @property
    def config(self) -> dict:
        if self._config is None:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
            else:
                self._config = {}
        return self._config
    


    async def render_image(self, resolution: Tuple[int, int], orientation: str, settings: dict) -> str:
        """Generate and save example image to assets/"""
        assets_dir = self.channel_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        filename = "current.jpg"
        output_path = assets_dir / filename

        # Create a blank image (or load/copy an existing one)
        img = Image.new("RGB", resolution, color=(200, 200, 200))
        img.save(output_path)

        return f"assets/{filename}"
    
    async def validate_settings(self, settings: dict) -> Dict[str, str]:
        """Validate settings"""
        errors = {}
        photo_source = settings.get('photo_source')
        if photo_source and photo_source not in ['local', 'unsplash', 'custom']:
            errors['photo_source'] = "Invalid photo source"
        return errors
    
    def get_status(self) -> dict:
        return {
            "active": True,
            "lastUpdate": datetime.datetime.now().isoformat(),
            "lastError": None,
            "usingFallback": False,
            "version": self.config.get("version", "1.0.0")
        }
    
    def get_router(self) -> Optional:
        return None

ChannelClass = ExampleChannel
