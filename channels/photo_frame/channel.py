"""
Photo Frame Channel - Gallery-based photo display with random selection
Embedded plugin for the new Mimir plugin architecture
"""

from typing import Dict, Any, Optional, Tuple, List
import json
import datetime
import os
import random
from pathlib import Path
from PIL import Image
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import base64
import io

class PhotoFrameChannel:
    """Photo frame channel with gallery support and random image selection"""
    
    def __init__(self, channel_dir: str):
        self.channel_dir = Path(channel_dir)
        self.config_path = self.channel_dir / "config.json"
        self.gallery_dir = self.channel_dir / "gallery"
        self.gallery_dir.mkdir(exist_ok=True)
        self._config = None
        self._router = None
        
    @property
    def id(self) -> str:
        return "photo_frame"
    
    @property
    def config(self) -> dict:
        if self._config is None:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
            else:
                # Default configuration
                self._config = {
                    "id": "photo_frame",
                    "name": "Photo Frame Channel",
                    "version": "1.0.0",
                    "description": "Displays photos from gallery in a photo frame style with randomization",
                    "settings": {
                        "randomize": {
                            "type": "checkbox",
                            "label": "Randomize Image Selection",
                            "default": True
                        },
                        "frame_style": {
                            "type": "select",
                            "label": "Frame Style",
                            "default": "classic",
                            "enum": ["classic", "modern", "vintage", "minimal"]
                        }
                    }
                }
                self._save_config()
                
        return self._config
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def discover_gallery_images(self) -> List[str]:
        """Scan gallery directory and return list of available images"""
        if not self.gallery_dir.exists():
            return []
        
        images = []
        for file_path in self.gallery_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                images.append(file_path.name)
        
        return sorted(images)
    
    async def request_image(self, request_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate a random image from the gallery for display
        
        Args:
            request_data: Optional request parameters
            
        Returns:
            Dictionary with image data (base64 encoded)
        """
        try:
            available_images = self.discover_gallery_images()
            
            if not available_images:
                # Return a placeholder image if no gallery images exist
                placeholder = self._create_placeholder_image()
                return {
                    "success": True,
                    "image": placeholder,
                    "filename": "placeholder.jpg",
                    "message": "No images in gallery, showing placeholder"
                }
            
            # Select random image
            settings = request_data.get("settings", {}) if request_data else {}
            randomize = settings.get("randomize", True)
            
            if randomize:
                selected_image = random.choice(available_images)
            else:
                # Use first image if not randomizing
                selected_image = available_images[0]
            
            # Load and encode the image
            image_path = self.gallery_dir / selected_image
            with open(image_path, 'rb') as f:
                image_data = f.read()
                image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            return {
                "success": True,
                "image": image_b64,
                "filename": selected_image,
                "total_images": len(available_images),
                "message": f"Selected {selected_image} from {len(available_images)} images"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to generate image: {str(e)}"
            }
    
    def _create_placeholder_image(self) -> str:
        """Create a placeholder image when no gallery images exist"""
        try:
            # Create a simple placeholder image
            img = Image.new("RGB", (800, 600), color=(240, 240, 240))
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=90)
            img_data = buffer.getvalue()
            return base64.b64encode(img_data).decode('utf-8')
            
        except Exception as e:
            print(f"Error creating placeholder: {e}")
            return ""
    
    async def render_image(self, resolution: Tuple[int, int], orientation: str, settings: dict) -> str:
        """
        Generate and save an image for display at specified resolution
        
        Args:
            resolution: (width, height) in pixels
            orientation: "landscape" or "portrait"  
            settings: User configuration settings
            
        Returns:
            Path to generated image file
        """
        try:
            # Get a random image from gallery
            result = await self.request_image({"settings": settings})
            
            if not result.get("success"):
                raise Exception(result.get("error", "Failed to get image"))
            
            # Create resolution-specific directory
            width, height = resolution
            resolution_folder = f"{width}x{height}"
            resolution_dir = self.channel_dir / "current" / resolution_folder
            resolution_dir.mkdir(parents=True, exist_ok=True)
            
            # Decode base64 image
            image_data = base64.b64decode(result["image"])
            img = Image.open(io.BytesIO(image_data))
            
            # Resize to requested resolution
            img_resized = img.resize(resolution, Image.Resampling.LANCZOS)
            
            # Save the image
            output_path = resolution_dir / "current.jpg"
            img_resized.save(output_path, 'JPEG', quality=95)
            
            print(f"✅ Generated photo frame image {resolution_folder}/current.jpg")
            
            return f"current/{resolution_folder}/current.jpg"
            
        except Exception as e:
            print(f"❌ Error rendering photo frame image: {e}")
            # Create fallback image
            width, height = resolution
            resolution_folder = f"{width}x{height}"
            resolution_dir = self.channel_dir / "current" / resolution_folder
            resolution_dir.mkdir(parents=True, exist_ok=True)
            
            fallback_img = Image.new("RGB", resolution, color=(200, 200, 200))
            output_path = resolution_dir / "current.jpg"
            fallback_img.save(output_path, 'JPEG', quality=95)
            
            return f"current/{resolution_folder}/current.jpg"
    
    async def validate_settings(self, settings: dict) -> Dict[str, str]:
        """Validate channel settings"""
        errors = {}
        
        # Validate frame style
        frame_style = settings.get('frame_style')
        if frame_style:
            valid_styles = ["classic", "modern", "vintage", "minimal"]
            if frame_style not in valid_styles:
                errors['frame_style'] = f"Frame style must be one of: {', '.join(valid_styles)}"
        
        return errors
    
    def get_status(self) -> dict:
        """Get current channel status"""
        try:
            available_images = self.discover_gallery_images()
            
            return {
                "active": True,
                "healthy": True,
                "lastUpdate": datetime.datetime.now().isoformat(),
                "lastError": None,
                "version": self.config.get("version", "1.0.0"),
                "galleryImages": len(available_images),
                "availableImages": available_images[:10],  # Limit for performance
                "totalImages": len(available_images)
            }
        except Exception as e:
            return {
                "active": False,
                "healthy": False,
                "lastUpdate": datetime.datetime.now().isoformat(),
                "lastError": str(e),
                "version": "unknown",
                "galleryImages": 0,
                "availableImages": [],
                "totalImages": 0
            }
    
    def get_manifest(self) -> Dict[str, Any]:
        """Get channel manifest with capabilities"""
        return {
            "id": self.id,
            "name": self.config.get("name", "Photo Frame Channel"),
            "version": self.config.get("version", "1.0.0"),
            "description": self.config.get("description", "Photo frame channel"),
            "capabilities": {
                "supports_upload": True,
                "supports_gallery": True,
                "supports_randomization": True,
                "image_formats": ["jpg", "jpeg", "png", "gif"],
                "max_file_size": "10MB"
            },
            "settings": self.config.get("settings", {}),
            "status": self.get_status()
        }
    
    def get_router(self) -> Optional[APIRouter]:
        """Get API router for channel-specific endpoints"""
        if self._router is None:
            self._router = APIRouter()
            
            @self._router.get("/manifest")
            async def get_manifest():
                """Get channel manifest and capabilities"""
                return self.get_manifest()
            
            @self._router.post("/request_image")
            async def request_image(request_data: Dict[str, Any] = None):
                """Request a random image from the gallery"""
                return await self.request_image(request_data)
            
            @self._router.get("/gallery")
            async def list_gallery():
                """List all images in the gallery"""
                images = self.discover_gallery_images()
                return {
                    "images": images,
                    "total": len(images),
                    "galleryPath": str(self.gallery_dir)
                }
            
            @self._router.post("/upload")
            async def upload_image(
                file: UploadFile = File(...),
                filename: Optional[str] = Form(None)
            ):
                """Upload a new image to the gallery"""
                try:
                    # Validate file type
                    if not file.content_type.startswith('image/'):
                        raise HTTPException(status_code=400, detail="File must be an image")
                    
                    # Determine filename
                    if filename:
                        save_filename = filename
                    else:
                        save_filename = file.filename or f"upload_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    
                    # Ensure filename has proper extension
                    if not save_filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        save_filename += '.jpg'
                    
                    # Save the file
                    file_path = self.gallery_dir / save_filename
                    
                    with open(file_path, 'wb') as f:
                        content = await file.read()
                        f.write(content)
                    
                    return {
                        "success": True,
                        "filename": save_filename,
                        "size": len(content),
                        "message": f"Successfully uploaded {save_filename}"
                    }
                    
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
        
        return self._router

# Export the channel class for plugin discovery
ChannelClass = PhotoFrameChannel
