"""
Base Channel Interface for Mimir Platform v2.4+
Provides sub-channel support and standardized channel interface
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
from datetime import datetime, timezone


class BaseChannel(ABC):
    """
    Abstract base class for Mimir Platform channels with sub-channel support.
    
    This provides a standardized interface for channel implementations and
    enables sub-channel functionality for content organization.
    """
    
    def __init__(self, channel_dir: str):
        """
        Initialize channel with directory path
        
        Args:
            channel_dir: Path to channel directory
        """
        self.channel_dir = Path(channel_dir)
        self.config_path = self.channel_dir / "config.json"
        self._config = self._load_config()
        
        # State tracking
        self.last_update = None
        self.last_error = None
        self.current_image_id = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load channel configuration from config.json"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            raise Exception(f"Failed to load channel config: {e}")
    
    @property
    def id(self) -> str:
        """Channel identifier"""
        return self._config.get("id", "unknown")
    
    @property
    def config(self) -> Dict[str, Any]:
        """Channel configuration"""
        return self._config
    
    # =========================================================================
    # Core Channel Interface (must be implemented by channels)
    # =========================================================================
    
    @abstractmethod
    async def render_image(
        self, 
        resolution: Tuple[int, int], 
        orientation: str = "landscape", 
        settings: Dict[str, Any] = None,
        subchannel_id: Optional[str] = None
    ) -> str:
        """
        Generate/select image for display
        
        Args:
            resolution: (width, height) in pixels
            orientation: "landscape" or "portrait"  
            settings: User configuration settings
            subchannel_id: Optional sub-channel to target
            
        Returns:
            Path to generated image file
        """
        pass
    
    @abstractmethod
    async def validate_settings(self, settings: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate channel settings
        
        Args:
            settings: Settings dictionary to validate
            
        Returns:
            Dictionary of field_name -> error_message for any validation errors
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get current channel status
        
        Returns:
            Status dictionary with health, statistics, etc.
        """
        pass
    
    # =========================================================================
    # Sub-Channel Interface (optional - override to enable sub-channels)
    # =========================================================================
    
    def supports_subchannels(self) -> bool:
        """
        Return whether this channel supports sub-channels
        
        Returns:
            True if channel supports sub-channels, False otherwise
        """
        return False
    
    def get_subchannel_config(self) -> Dict[str, Any]:
        """
        Return sub-channel configuration for this channel
        
        Returns:
            Sub-channel configuration dictionary
        """
        return {
            "enabled": False,
            "label": "Sub-channel",
            "labelPlural": "Sub-channels", 
            "supports_tagging": False,
            "supports_multiple_membership": False,
            "allowCustom": True
        }
    
    def get_subchannels(self) -> List[Dict[str, Any]]:
        """
        Return list of available sub-channels
        
        Returns:
            List of sub-channel dictionaries
        """
        return []
    
    def get_subchannel_details(self, subchannel_id: str) -> Dict[str, Any]:
        """
        Return detailed information about a specific sub-channel
        
        Args:
            subchannel_id: ID of sub-channel to get details for
            
        Returns:
            Sub-channel details dictionary
            
        Raises:
            NotImplementedError: If channel doesn't support sub-channels
            ValueError: If sub-channel not found
        """
        if not self.supports_subchannels():
            raise NotImplementedError("Channel does not support sub-channels")
        
        subchannels = self.get_subchannels()
        subchannel = next((s for s in subchannels if s.get('id') == subchannel_id), None)
        
        if not subchannel:
            raise ValueError(f"Sub-channel '{subchannel_id}' not found")
        
        return subchannel
    
    def create_subchannel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new sub-channel
        
        Args:
            data: Sub-channel data (name, description, etc.)
            
        Returns:
            Created sub-channel dictionary
            
        Raises:
            NotImplementedError: If channel doesn't support sub-channels or creation
        """
        if not self.supports_subchannels():
            raise NotImplementedError("Channel does not support sub-channels")
        
        raise NotImplementedError("Sub-channel creation not implemented for this channel")
    
    def update_subchannel(self, subchannel_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing sub-channel
        
        Args:
            subchannel_id: ID of sub-channel to update
            data: Updated sub-channel data
            
        Returns:
            Updated sub-channel dictionary
            
        Raises:
            NotImplementedError: If channel doesn't support sub-channels or updates
            ValueError: If sub-channel not found
        """
        if not self.supports_subchannels():
            raise NotImplementedError("Channel does not support sub-channels")
        
        raise NotImplementedError("Sub-channel updates not implemented for this channel")
    
    def delete_subchannel(self, subchannel_id: str) -> bool:
        """
        Delete a sub-channel
        
        Args:
            subchannel_id: ID of sub-channel to delete
            
        Returns:
            True if successfully deleted
            
        Raises:
            NotImplementedError: If channel doesn't support sub-channels or deletion
            ValueError: If sub-channel not found
        """
        if not self.supports_subchannels():
            raise NotImplementedError("Channel does not support sub-channels")
        
        raise NotImplementedError("Sub-channel deletion not implemented for this channel")
    
    def assign_content_to_subchannel(
        self, 
        subchannel_id: str, 
        content_ids: List[str], 
        action: str = "add"
    ) -> bool:
        """
        Assign content to a sub-channel
        
        Args:
            subchannel_id: ID of sub-channel
            content_ids: List of content IDs to assign
            action: "add", "remove", or "set"
            
        Returns:
            True if successful
            
        Raises:
            NotImplementedError: If channel doesn't support sub-channels or content assignment
            ValueError: If sub-channel not found or invalid action
        """
        if not self.supports_subchannels():
            raise NotImplementedError("Channel does not support sub-channels")
        
        if action not in ["add", "remove", "set"]:
            raise ValueError("Action must be 'add', 'remove', or 'set'")
        
        raise NotImplementedError("Content assignment not implemented for this channel")
    
    def get_subchannel_content(
        self, 
        subchannel_id: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get content within a sub-channel
        
        Args:
            subchannel_id: ID of sub-channel
            limit: Maximum number of items to return
            offset: Number of items to skip
            
        Returns:
            Dictionary with 'content' list and 'totalCount'
            
        Raises:
            NotImplementedError: If channel doesn't support sub-channels
            ValueError: If sub-channel not found
        """
        if not self.supports_subchannels():
            raise NotImplementedError("Channel does not support sub-channels")
        
        raise NotImplementedError("Sub-channel content listing not implemented for this channel")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _get_subchannel_metadata_path(self) -> Path:
        """Get path to sub-channel metadata file"""
        return self.channel_dir / "subchannels.json"
    
    def _load_subchannel_metadata(self) -> Dict[str, Any]:
        """Load sub-channel metadata from file"""
        metadata_path = self._get_subchannel_metadata_path()
        
        if not metadata_path.exists():
            return {
                "version": "1.0",
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
                "subchannels": []
            }
        
        try:
            with open(metadata_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load sub-channel metadata: {e}")
            return {
                "version": "1.0", 
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
                "subchannels": []
            }
    
    def _save_subchannel_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Save sub-channel metadata to file"""
        metadata_path = self._get_subchannel_metadata_path()
        
        try:
            # Update timestamp
            metadata["lastUpdated"] = datetime.now(timezone.utc).isoformat()
            
            # Atomic write
            temp_path = metadata_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            temp_path.replace(metadata_path)
            return True
            
        except Exception as e:
            print(f"Error: Failed to save sub-channel metadata: {e}")
            return False
    
    def _generate_subchannel_id(self, name: str) -> str:
        """Generate a unique sub-channel ID from name"""
        import re
        import uuid
        
        # Create slug from name
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower()).strip('_')
        
        # Ensure uniqueness
        existing_ids = [s.get('id') for s in self.get_subchannels()]
        
        if slug not in existing_ids:
            return slug
        
        # Add suffix if needed
        counter = 1
        while f"{slug}_{counter}" in existing_ids:
            counter += 1
        
        return f"{slug}_{counter}"
