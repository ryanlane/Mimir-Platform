"""
Sub-Channel Management for Mimir Platform v2.4+
Handles API endpoints for sub-channel operations
"""

from typing import Dict, List, Any, Optional
from fastapi import HTTPException
from base_channel import BaseChannel
import logging

logger = logging.getLogger(__name__)


class SubChannelManager:
    """
    Manages sub-channel operations across all channels
    """
    
    def __init__(self, channel_registry: Dict[str, BaseChannel]):
        """
        Initialize with channel registry
        
        Args:
            channel_registry: Dictionary mapping channel_id -> channel instance
        """
        self.channel_registry = channel_registry
    
    def _get_channel(self, channel_id: str) -> BaseChannel:
        """Get channel instance, raising HTTPException if not found"""
        if channel_id not in self.channel_registry:
            raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")
        
        return self.channel_registry[channel_id]
    
    def _ensure_subchannels_supported(self, channel: BaseChannel, channel_id: str):
        """Ensure channel supports sub-channels, raising HTTPException if not"""
        if not channel.supports_subchannels():
            raise HTTPException(
                status_code=400, 
                detail=f"Channel '{channel_id}' does not support sub-channels"
            )
    
    # =========================================================================
    # Sub-Channel Configuration
    # =========================================================================
    
    async def get_subchannel_config(self, channel_id: str) -> Dict[str, Any]:
        """
        Get sub-channel configuration for a channel
        
        Args:
            channel_id: ID of channel
            
        Returns:
            Sub-channel configuration dictionary
        """
        try:
            channel = self._get_channel(channel_id)
            
            # Check if channel supports sub-channels by looking for the method
            if not hasattr(channel, 'supports_subchannels') or not channel.supports_subchannels():
                return {
                    "supported": False,
                    "message": f"Channel '{channel_id}' does not support sub-channels",
                    "subChannelTypes": [],
                    "settings": {}
                }
            
            # Check if channel has the get_subchannel_config method
            if not hasattr(channel, 'get_subchannel_config'):
                return {
                    "supported": False,
                    "message": f"Channel '{channel_id}' does not implement sub-channel configuration",
                    "subChannelTypes": [],
                    "settings": {}
                }
            
            config = channel.get_subchannel_config()
            
            logger.info(f"Retrieved sub-channel config for channel '{channel_id}'")
            return config
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting sub-channel config for '{channel_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get sub-channel config: {str(e)}")
    
    # =========================================================================
    # Sub-Channel Management
    # =========================================================================
    
    async def list_subchannels(self, channel_id: str) -> Dict[str, Any]:
        """
        List all sub-channels for a channel
        
        Args:
            channel_id: ID of channel
            
        Returns:
            Dictionary with 'subChannels' list
        """
        try:
            channel = self._get_channel(channel_id)
            
            # Check if channel supports sub-channels by looking for the method
            if not hasattr(channel, 'supports_subchannels') or not channel.supports_subchannels():
                return {"subChannels": []}
            
            # Check if channel has the get_subchannels method
            if not hasattr(channel, 'get_subchannels'):
                return {"subChannels": []}
            
            subchannels = channel.get_subchannels()
            
            logger.info("Listed %d sub-channels for channel '%s'", len(subchannels), channel_id)
            return {"subChannels": subchannels}
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error listing sub-channels for '%s': %s", channel_id, e)
            raise HTTPException(status_code=500, detail=f"Failed to list sub-channels: {str(e)}") from e
    
    async def get_subchannel_details(self, channel_id: str, subchannel_id: str) -> Dict[str, Any]:
        """
        Get details for a specific sub-channel
        
        Args:
            channel_id: ID of channel
            subchannel_id: ID of sub-channel
            
        Returns:
            Sub-channel details dictionary
        """
        try:
            channel = self._get_channel(channel_id)
            self._ensure_subchannels_supported(channel, channel_id)
            
            details = channel.get_subchannel_details(subchannel_id)
            
            logger.info(f"Retrieved details for sub-channel '{subchannel_id}' in channel '{channel_id}'")
            return details
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting sub-channel details for '{channel_id}/{subchannel_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get sub-channel details: {str(e)}")
    
    async def create_subchannel(self, channel_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new sub-channel
        
        Args:
            channel_id: ID of channel
            data: Sub-channel creation data
            
        Returns:
            Created sub-channel dictionary
        """
        try:
            channel = self._get_channel(channel_id)
            self._ensure_subchannels_supported(channel, channel_id)
            
            # Validate required fields
            if not data.get('name'):
                raise HTTPException(status_code=400, detail="Sub-channel name is required")
            
            created_subchannel = channel.create_subchannel(data)
            
            logger.info(f"Created sub-channel '{created_subchannel.get('id')}' in channel '{channel_id}'")
            return created_subchannel
            
        except HTTPException:
            raise
        except NotImplementedError:
            raise HTTPException(
                status_code=501, 
                detail=f"Channel '{channel_id}' does not support sub-channel creation"
            )
        except Exception as e:
            logger.error(f"Error creating sub-channel in '{channel_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create sub-channel: {str(e)}")
    
    async def update_subchannel(
        self, 
        channel_id: str, 
        subchannel_id: str, 
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing sub-channel
        
        Args:
            channel_id: ID of channel
            subchannel_id: ID of sub-channel
            data: Updated sub-channel data
            
        Returns:
            Updated sub-channel dictionary
        """
        try:
            channel = self._get_channel(channel_id)
            self._ensure_subchannels_supported(channel, channel_id)
            
            updated_subchannel = channel.update_subchannel(subchannel_id, data)
            
            logger.info(f"Updated sub-channel '{subchannel_id}' in channel '{channel_id}'")
            return updated_subchannel
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except HTTPException:
            raise
        except NotImplementedError:
            raise HTTPException(
                status_code=501, 
                detail=f"Channel '{channel_id}' does not support sub-channel updates"
            )
        except Exception as e:
            logger.error(f"Error updating sub-channel '{channel_id}/{subchannel_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update sub-channel: {str(e)}")
    
    async def delete_subchannel(self, channel_id: str, subchannel_id: str) -> Dict[str, Any]:
        """
        Delete a sub-channel
        
        Args:
            channel_id: ID of channel
            subchannel_id: ID of sub-channel
            
        Returns:
            Success confirmation dictionary
        """
        try:
            channel = self._get_channel(channel_id)
            self._ensure_subchannels_supported(channel, channel_id)
            
            success = channel.delete_subchannel(subchannel_id)
            
            if success:
                logger.info(f"Deleted sub-channel '{subchannel_id}' from channel '{channel_id}'")
                return {"success": True, "message": f"Sub-channel '{subchannel_id}' deleted successfully"}
            else:
                raise HTTPException(status_code=500, detail="Failed to delete sub-channel")
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except HTTPException:
            raise
        except NotImplementedError:
            raise HTTPException(
                status_code=501, 
                detail=f"Channel '{channel_id}' does not support sub-channel deletion"
            )
        except Exception as e:
            logger.error(f"Error deleting sub-channel '{channel_id}/{subchannel_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete sub-channel: {str(e)}")
    
    # =========================================================================
    # Content Assignment
    # =========================================================================
    
    async def assign_content_to_subchannel(
        self, 
        channel_id: str, 
        subchannel_id: str, 
        content_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assign content to a sub-channel
        
        Args:
            channel_id: ID of channel
            subchannel_id: ID of sub-channel
            content_data: Content assignment data with 'contentIds' and 'action'
            
        Returns:
            Success confirmation dictionary
        """
        try:
            channel = self._get_channel(channel_id)
            self._ensure_subchannels_supported(channel, channel_id)
            
            # Validate content data
            content_ids = content_data.get('contentIds', [])
            action = content_data.get('action', 'add')
            
            if not content_ids:
                raise HTTPException(status_code=400, detail="contentIds list is required")
            
            if action not in ['add', 'remove', 'set']:
                raise HTTPException(status_code=400, detail="action must be 'add', 'remove', or 'set'")
            
            success = channel.assign_content_to_subchannel(subchannel_id, content_ids, action)
            
            if success:
                logger.info(
                    f"Content assignment '{action}' successful for sub-channel "
                    f"'{subchannel_id}' in channel '{channel_id}': {len(content_ids)} items"
                )
                return {
                    "success": True, 
                    "message": f"Content {action} operation completed successfully",
                    "itemCount": len(content_ids)
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to assign content")
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except HTTPException:
            raise
        except NotImplementedError:
            raise HTTPException(
                status_code=501, 
                detail=f"Channel '{channel_id}' does not support content assignment"
            )
        except Exception as e:
            logger.error(f"Error assigning content to '{channel_id}/{subchannel_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to assign content: {str(e)}")
    
    async def get_subchannel_content(
        self, 
        channel_id: str, 
        subchannel_id: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get content within a sub-channel
        
        Args:
            channel_id: ID of channel
            subchannel_id: ID of sub-channel
            limit: Maximum number of items to return
            offset: Number of items to skip
            
        Returns:
            Dictionary with 'content' list and 'totalCount'
        """
        try:
            channel = self._get_channel(channel_id)
            self._ensure_subchannels_supported(channel, channel_id)
            
            content_data = channel.get_subchannel_content(subchannel_id, limit, offset)
            
            logger.info(
                f"Retrieved content for sub-channel '{subchannel_id}' in channel '{channel_id}': "
                f"{len(content_data.get('content', []))} items"
            )
            return content_data
            
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except HTTPException:
            raise
        except NotImplementedError:
            raise HTTPException(
                status_code=501, 
                detail=f"Channel '{channel_id}' does not support sub-channel content listing"
            )
        except Exception as e:
            logger.error(f"Error getting content for '{channel_id}/{subchannel_id}': {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get sub-channel content: {str(e)}")
