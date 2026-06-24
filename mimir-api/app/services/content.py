# Copyright (C) 2026 Ryan Lane
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Content Management Service
Handles content processing, media serving, and file management
"""
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ContentService:
    """Service for managing content, media files, and processing"""

    def __init__(self):
        self.content_root = Path(settings.channels_directory)
        self.supported_image_formats = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        self.supported_video_formats = {'.mp4', '.webm', '.avi', '.mov', '.mkv'}
        self.max_file_size = 50 * 1024 * 1024  # 50MB default

    def compute_content_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of content file"""
        if not file_path.exists():
            return ""

        try:
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error computing hash for {file_path}: {e}")
            return ""

    def get_file_info(self, file_path: Path) -> dict[str, Any]:
        """Get comprehensive file information"""
        if not file_path.exists():
            return {"exists": False}

        try:
            stat = file_path.stat()
            file_hash = self.compute_content_hash(file_path)

            return {
                "exists": True,
                "path": str(file_path),
                "name": file_path.name,
                "size": stat.st_size,
                "size_human": self._format_file_size(stat.st_size),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "extension": file_path.suffix.lower(),
                "mime_type": self._get_mime_type(file_path),
                "content_hash": file_hash,
                "is_image": self._is_image(file_path),
                "is_video": self._is_video(file_path)
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {"exists": False, "error": str(e)}

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type for file"""
        extension = file_path.suffix.lower()

        # Image types
        if extension in {'.jpg', '.jpeg'}:
            return 'image/jpeg'
        elif extension == '.png':
            return 'image/png'
        elif extension == '.gif':
            return 'image/gif'
        elif extension == '.webp':
            return 'image/webp'
        elif extension == '.bmp':
            return 'image/bmp'

        # Video types
        elif extension == '.mp4':
            return 'video/mp4'
        elif extension == '.webm':
            return 'video/webm'
        elif extension == '.avi':
            return 'video/x-msvideo'
        elif extension == '.mov':
            return 'video/quicktime'
        elif extension == '.mkv':
            return 'video/x-matroska'

        # Other common types
        elif extension == '.json':
            return 'application/json'
        elif extension == '.css':
            return 'text/css'
        elif extension == '.js':
            return 'application/javascript'
        elif extension == '.html':
            return 'text/html'

        return 'application/octet-stream'

    def _is_image(self, file_path: Path) -> bool:
        """Check if file is an image"""
        return file_path.suffix.lower() in self.supported_image_formats

    def _is_video(self, file_path: Path) -> bool:
        """Check if file is a video"""
        return file_path.suffix.lower() in self.supported_video_formats

    def validate_content_file(self, file_path: Path) -> dict[str, Any]:
        """Validate content file for security and format compliance"""
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "file_info": {}
        }

        if not file_path.exists():
            validation_result["errors"].append("File does not exist")
            return validation_result

        # Get file info
        file_info = self.get_file_info(file_path)
        validation_result["file_info"] = file_info

        if not file_info.get("exists"):
            validation_result["errors"].append("Unable to read file information")
            return validation_result

        # Check file size
        if file_info["size"] > self.max_file_size:
            validation_result["errors"].append(
                f"File too large: {file_info['size_human']} (max: {self._format_file_size(self.max_file_size)})"
            )

        # Path traversal check
        try:
            resolved_path = file_path.resolve()
            content_root_resolved = self.content_root.resolve()
            if not str(resolved_path).startswith(str(content_root_resolved)):
                validation_result["errors"].append("File path outside allowed directory")
        except Exception as e:
            validation_result["errors"].append(f"Path validation error: {e}")

        # Format validation
        if not (self._is_image(file_path) or self._is_video(file_path)):
            validation_result["warnings"].append("File format not explicitly supported")

        # Set valid if no errors
        validation_result["valid"] = len(validation_result["errors"]) == 0

        return validation_result

    def get_channel_content(self, channel_id: str, subchannel: str | None = None) -> dict[str, Any]:
        """Get content information for channel/subchannel"""
        channel_path = self.content_root / channel_id

        if not channel_path.exists():
            return {"error": "Channel not found", "content": []}

        content_path = channel_path
        if subchannel:
            content_path = channel_path / subchannel
            if not content_path.exists():
                return {"error": "Subchannel not found", "content": []}

        try:
            content_items = []

            for item_path in content_path.iterdir():
                if item_path.is_file() and (self._is_image(item_path) or self._is_video(item_path)):
                    file_info = self.get_file_info(item_path)
                    if file_info.get("exists"):
                        content_items.append({
                            "name": item_path.name,
                            "path": str(item_path.relative_to(self.content_root)),
                            "type": "image" if self._is_image(item_path) else "video",
                            "size": file_info["size"],
                            "size_human": file_info["size_human"],
                            "modified": file_info["modified"],
                            "content_hash": file_info["content_hash"],
                            "mime_type": file_info["mime_type"]
                        })

            # Sort by modification date (newest first)
            content_items.sort(key=lambda x: x["modified"], reverse=True)

            return {
                "channel_id": channel_id,
                "subchannel": subchannel,
                "content": content_items,
                "total_items": len(content_items),
                "path": str(content_path.relative_to(self.content_root))
            }

        except Exception as e:
            logger.error(f"Error getting content for {channel_id}/{subchannel}: {e}")
            return {"error": str(e), "content": []}

    def get_current_content(self, channel_id: str, subchannel: str | None = None,
                          resolution: str | None = None) -> tuple[Path, dict[str, Any]] | None:
        """Get current content file for channel/subchannel with optional resolution"""
        channel_path = self.content_root / channel_id

        if not channel_path.exists():
            return None

        # Build content path
        content_path = channel_path
        if subchannel:
            content_path = channel_path / subchannel

        # Add resolution if specified
        if resolution:
            resolution_path = content_path / resolution
            if resolution_path.exists():
                content_path = resolution_path

        # Look for current content file
        current_file = content_path / "current.jpg"
        if not current_file.exists():
            # Fallback to any image file
            for item_path in content_path.iterdir():
                if item_path.is_file() and self._is_image(item_path):
                    current_file = item_path
                    break

        if current_file.exists():
            file_info = self.get_file_info(current_file)
            return current_file, file_info

        return None

    def generate_content_manifest(self, channel_id: str) -> dict[str, Any]:
        """Generate content manifest for channel"""
        channel_path = self.content_root / channel_id

        if not channel_path.exists():
            return {"error": "Channel not found"}

        try:
            manifest = {
                "channel_id": channel_id,
                "generated_at": datetime.now().isoformat(),
                "subchannels": {},
                "total_content": 0,
                "total_size": 0
            }

            for item in channel_path.iterdir():
                if item.is_dir():
                    # Subchannel directory
                    subchannel_content = self.get_channel_content(channel_id, item.name)
                    if not subchannel_content.get("error"):
                        manifest["subchannels"][item.name] = {
                            "content_count": subchannel_content["total_items"],
                            "content_items": subchannel_content["content"]
                        }
                        manifest["total_content"] += subchannel_content["total_items"]
                        manifest["total_size"] += sum(
                            item["size"] for item in subchannel_content["content"]
                        )

            manifest["total_size_human"] = self._format_file_size(manifest["total_size"])

            return manifest

        except Exception as e:
            logger.error(f"Error generating manifest for {channel_id}: {e}")
            return {"error": str(e)}

    def clean_temp_files(self, max_age_hours: int = 24) -> dict[str, Any]:
        """Clean temporary files older than specified age"""
        cleaned_files = []
        total_size_freed = 0

        try:
            temp_dirs = [
                self.content_root / "temp",
                self.content_root / "cache",
                Path("/tmp") / "mimir"
            ]

            cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

            for temp_dir in temp_dirs:
                if not temp_dir.exists():
                    continue

                for file_path in temp_dir.rglob("*"):
                    if file_path.is_file():
                        try:
                            if file_path.stat().st_mtime < cutoff_time:
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                cleaned_files.append(str(file_path))
                                total_size_freed += file_size
                        except Exception as e:
                            logger.warning(f"Failed to clean temp file {file_path}: {e}")

            return {
                "cleaned_files": len(cleaned_files),
                "size_freed": total_size_freed,
                "size_freed_human": self._format_file_size(total_size_freed),
                "files": cleaned_files
            }

        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
            return {"error": str(e), "cleaned_files": 0}


# Global service instance
content_service = ContentService()
