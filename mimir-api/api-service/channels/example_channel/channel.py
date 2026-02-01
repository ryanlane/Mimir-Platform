"""
Example Channel - Enhanced implementation with dynamic asset discovery and image conversion
"""

from typing import Dict, Any, Optional, Tuple
import json
import datetime
import os
from pathlib import Path
from PIL import Image
from fastapi import APIRouter

class ExampleChannel:
    """Enhanced example channel with dynamic asset discovery and image conversion"""
    
    def __init__(self, channel_dir: str):
        self.channel_dir = Path(channel_dir)
        self.config_path = self.channel_dir / "config.json"
        self._config = None
        self._router = None
        self._last_assets_scan = None
        
    @property
    def id(self) -> str:
        return "example_channel"
    
    def discover_assets(self) -> list:
        """Scan assets directory and return list of available images"""
        assets_dir = self.channel_dir / "assets"
        if not assets_dir.exists():
            return []
        
        images = []
        for file_path in assets_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                # Skip current.jpg as it's generated
                if file_path.name != 'current.jpg':
                    images.append(file_path.stem)  # filename without extension
        
        return sorted(images)
    
    def update_config_with_assets(self) -> bool:
        """Update config.json with discovered assets if changed"""
        try:
            current_assets = self.discover_assets()
            
            # Get current enum values from config
            current_enum = self.config.get("settings", {}).get("image_choice", {}).get("enum", [])
            
            # Check if assets have changed
            if set(current_assets) != set(current_enum) and current_assets:
                # Update config with new assets
                if "settings" not in self.config:
                    self.config["settings"] = {}
                if "image_choice" not in self.config["settings"]:
                    self.config["settings"]["image_choice"] = {
                        "type": "select",
                        "label": "Image to Display",
                        "default": current_assets[0] if current_assets else "image1"
                    }
                
                self.config["settings"]["image_choice"]["enum"] = current_assets
                
                # Update default if current default is not in new list
                current_default = self.config["settings"]["image_choice"].get("default")
                if current_default not in current_assets and current_assets:
                    self.config["settings"]["image_choice"]["default"] = current_assets[0]
                
                # Save updated config
                try:
                    with open(self.config_path, 'w') as f:
                        json.dump(self.config, f, indent=2)
                    self._last_assets_scan = datetime.datetime.now()
                    return True
                except Exception as e:
                    print(f"❌ Error updating config for example_channel: {e}")
                    return False
            
            return False
        except Exception as e:
            print(f"❌ Error in update_config_with_assets for example_channel: {e}")
            return False
        
    @property
    def config(self) -> dict:
        if self._config is None:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
            else:
                self._config = {}
        
        # Periodically check for new assets (every 5 minutes)
        now = datetime.datetime.now()
        if (self._last_assets_scan is None or 
            (now - self._last_assets_scan).total_seconds() > 300):
            self.update_config_with_assets()
            
        return self._config
    
    async def create_current_image(self, settings: dict) -> bool:
        """Create current.jpg from selected image with conversion"""
        assets_dir = self.channel_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        
        image_choice = settings.get("image_choice", "image1")
        output_path = assets_dir / "current.jpg"
        
        # Try to find the source image
        for ext in [".jpg", ".jpeg", ".png"]:
            source_path = assets_dir / f"{image_choice}{ext}"
            if source_path.exists():
                try:
                    # Open and convert image
                    with Image.open(source_path) as img:
                        # Convert to RGB (handles PNG transparency)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # Save as JPEG
                        img.save(output_path, 'JPEG', quality=95)
                        return True
                except Exception as e:
                    print(f"Error converting image {source_path}: {e}")
                    continue
        
        # If no image found, create a fallback
        try:
            fallback_img = Image.new("RGB", (800, 600), color=(200, 200, 200))
            fallback_img.save(output_path, 'JPEG', quality=95)
            return True
        except Exception as e:
            print(f"Error creating fallback image: {e}")
            return False

    async def render_image(self, resolution: Tuple[int, int], orientation: str, settings: dict) -> str:
        """
        Generate and save selected image with resolution-based folder structure.
        Creates images in current/{width}x{height}/ subfolders for efficient sharing.
        """
        # First create the base current.jpg from selected image
        await self.create_current_image(settings)
        
        # Create resolution-specific directory
        width, height = resolution
        resolution_folder = f"{width}x{height}"
        resolution_dir = self.channel_dir / "current" / resolution_folder
        resolution_dir.mkdir(parents=True, exist_ok=True)
        
        # Set paths
        assets_dir = self.channel_dir / "assets"
        source_path = assets_dir / "current.jpg"
        output_path = resolution_dir / "current.jpg"
        
        print(f"🎯 Rendering example channel image for resolution {width}x{height}")
        
        if source_path.exists():
            try:
                with Image.open(source_path) as img:
                    # Resize to the requested resolution
                    img_resized = img.resize(resolution, Image.Resampling.LANCZOS)
                    img_resized.save(output_path, 'JPEG', quality=95)
                    
                    print(f"✅ Generated {resolution_folder}/current.jpg ({output_path.stat().st_size} bytes)")
                    
                    # Update the legacy current.jpg for backward compatibility
                    legacy_current = self.channel_dir / "current.jpg"
                    img_resized.save(legacy_current, 'JPEG', quality=95)
                    print(f"📄 Updated legacy current.jpg for backward compatibility")
                    
            except Exception as e:
                print(f"❌ Error processing image for resolution {resolution}: {e}")
                # Fall back to copying source without resize
                import shutil
                shutil.copy2(source_path, output_path)
                print(f"🔄 Used unresized image as fallback")
        else:
            print(f"⚠️  Source image not found: {source_path}")
            return f"current/{resolution_folder}/current.jpg"
        
        return f"current/{resolution_folder}/current.jpg"
    
    async def validate_settings(self, settings: dict) -> Dict[str, str]:
        """Validate settings"""
        errors = {}
        
        # Check if selected image exists
        image_choice = settings.get('image_choice')
        if image_choice:
            available_images = self.discover_assets()
            if image_choice not in available_images:
                errors['image_choice'] = f"Image '{image_choice}' not found in assets"
        
        # Validate update interval
        update_interval_value = settings.get('update_interval_value')
        if update_interval_value is not None:
            try:
                interval = int(update_interval_value)
                if interval < 1:
                    errors['update_interval_value'] = "Update interval must be at least 1"
            except (ValueError, TypeError):
                errors['update_interval_value'] = "Update interval must be a valid number"
        
        return errors
    
    def get_status(self) -> dict:
        try:
            available_images = self.discover_assets()
            assets_dir = self.channel_dir / "assets"
            current_exists = (assets_dir / "current.jpg").exists()
            
            return {
                "active": True,
                "lastUpdate": datetime.datetime.now().isoformat(),
                "lastError": None,
                "usingFallback": False,
                "version": self.config.get("version", "1.0.0"),
                "availableImages": available_images,
                "currentImageExists": current_exists,
                "assetsCount": len(available_images)
            }
        except Exception as e:
            print(f"❌ Error in example_channel get_status(): {str(e)}")
            return {
                "active": False,
                "lastUpdate": datetime.datetime.now().isoformat(),
                "lastError": f"Status check failed: {str(e)}",
                "usingFallback": True,
                "version": "unknown",
                "availableImages": [],
                "currentImageExists": False,
                "assetsCount": 0
            }
    
    def get_router(self) -> Optional[APIRouter]:
        """Get API router for channel-specific endpoints"""
        if self._router is None:
            self._router = APIRouter()
            
            @self._router.get("/assets")
            async def list_assets():
                """List available asset images"""
                return {
                    "images": self.discover_assets(),
                    "hasCurrentImage": (self.channel_dir / "assets" / "current.jpg").exists()
                }
            
            @self._router.post("/refresh_assets")
            async def refresh_assets():
                """Force refresh of asset discovery"""
                updated = self.update_config_with_assets()
                return {
                    "updated": updated,
                    "assets": self.discover_assets()
                }
        
        return self._router

ChannelClass = ExampleChannel
