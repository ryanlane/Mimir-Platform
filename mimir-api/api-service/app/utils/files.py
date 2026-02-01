"""
File handling utilities for Mimir API
Provides file operations, validation, and management functions
"""
import os
import shutil
import mimetypes
from pathlib import Path
from typing import Optional, List, Tuple
from app.core.logging import get_logger
from app.core.security import validate_file_path, sanitize_filename

logger = get_logger("app.utils.files")


def ensure_directory(directory: Path) -> bool:
    """
    Ensure a directory exists, create if necessary
    
    Args:
        directory: Path to directory
        
    Returns:
        True if directory exists or was created successfully
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return True
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False


def safe_file_path(base_path: Path, relative_path: str) -> Optional[Path]:
    """
    Safely resolve a file path within a base directory
    Prevents path traversal attacks
    
    Args:
        base_path: Base directory path
        relative_path: Relative path to file
        
    Returns:
        Resolved path if safe, None if unsafe
    """
    if not validate_file_path(relative_path, str(base_path)):
        logger.warning(f"Unsafe file path rejected: {relative_path}")
        return None
    
    return base_path / relative_path


def get_file_info(file_path: Path) -> dict:
    """
    Get comprehensive file information
    
    Args:
        file_path: Path to file
        
    Returns:
        Dictionary with file metadata
    """
    if not file_path.exists():
        return {"exists": False}
    
    try:
        stat = file_path.stat()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        return {
            "exists": True,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": file_path.is_file(),
            "is_dir": file_path.is_dir(),
            "mime_type": mime_type,
            "extension": file_path.suffix.lower(),
            "name": file_path.name,
            "stem": file_path.stem
        }
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to get file info for {file_path}: {e}")
        return {"exists": True, "error": str(e)}


def list_files(directory: Path, pattern: str = "*", recursive: bool = False) -> List[Path]:
    """
    List files in a directory with optional pattern matching
    
    Args:
        directory: Directory to search
        pattern: Glob pattern for file matching
        recursive: Whether to search recursively
        
    Returns:
        List of matching file paths
    """
    if not directory.exists() or not directory.is_dir():
        return []
    
    try:
        if recursive:
            return list(directory.rglob(pattern))
        else:
            return list(directory.glob(pattern))
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to list files in {directory}: {e}")
        return []


def copy_file(source: Path, destination: Path, overwrite: bool = False) -> bool:
    """
    Safely copy a file
    
    Args:
        source: Source file path
        destination: Destination file path
        overwrite: Whether to overwrite existing files
        
    Returns:
        True if successful, False otherwise
    """
    if not source.exists():
        logger.error(f"Source file does not exist: {source}")
        return False
    
    if destination.exists() and not overwrite:
        logger.warning(f"Destination file exists and overwrite=False: {destination}")
        return False
    
    try:
        # Ensure destination directory exists
        ensure_directory(destination.parent)
        
        # Copy file
        shutil.copy2(source, destination)
        logger.info(f"File copied successfully: {source} -> {destination}")
        return True
        
    except (OSError, PermissionError, shutil.Error) as e:
        logger.error(f"Failed to copy file {source} -> {destination}: {e}")
        return False


def move_file(source: Path, destination: Path, overwrite: bool = False) -> bool:
    """
    Safely move a file
    
    Args:
        source: Source file path
        destination: Destination file path
        overwrite: Whether to overwrite existing files
        
    Returns:
        True if successful, False otherwise
    """
    if not source.exists():
        logger.error(f"Source file does not exist: {source}")
        return False
    
    if destination.exists() and not overwrite:
        logger.warning(f"Destination file exists and overwrite=False: {destination}")
        return False
    
    try:
        # Ensure destination directory exists
        ensure_directory(destination.parent)
        
        # Move file
        shutil.move(str(source), str(destination))
        logger.info(f"File moved successfully: {source} -> {destination}")
        return True
        
    except (OSError, PermissionError, shutil.Error) as e:
        logger.error(f"Failed to move file {source} -> {destination}: {e}")
        return False


def delete_file(file_path: Path) -> bool:
    """
    Safely delete a file
    
    Args:
        file_path: Path to file to delete
        
    Returns:
        True if successful, False otherwise
    """
    if not file_path.exists():
        return True  # Already deleted
    
    try:
        file_path.unlink()
        logger.info(f"File deleted successfully: {file_path}")
        return True
    except (OSError, PermissionError) as e:
        logger.error(f"Failed to delete file {file_path}: {e}")
        return False


def get_image_dimensions(image_path: Path) -> Optional[Tuple[int, int]]:
    """
    Get image dimensions without loading the full image
    
    Args:
        image_path: Path to image file
        
    Returns:
        Tuple of (width, height) or None if not an image/error
    """
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size
    except ImportError:
        logger.warning("PIL not available, cannot get image dimensions")
        return None
    except Exception as e:
        logger.error(f"Failed to get image dimensions for {image_path}: {e}")
        return None


def is_image_file(file_path: Path) -> bool:
    """
    Check if a file is an image based on extension and MIME type
    
    Args:
        file_path: Path to file
        
    Returns:
        True if file appears to be an image
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
    
    if file_path.suffix.lower() not in image_extensions:
        return False
    
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type is not None and mime_type.startswith('image/')


def clean_filename(filename: str) -> str:
    """
    Clean and sanitize a filename
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem use
    """
    return sanitize_filename(filename)
