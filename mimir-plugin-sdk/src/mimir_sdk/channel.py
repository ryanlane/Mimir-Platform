"""Core channel protocol and base class for Mimir plugins.

Plugins can either:
  1. Implement ``ChannelProtocol`` directly (structural typing / duck typing)
  2. Subclass ``BaseChannel`` for default implementations and lifecycle hooks
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable

from fastapi import APIRouter

logger = logging.getLogger(__name__)


@runtime_checkable
class ChannelProtocol(Protocol):
    """Structural interface every Mimir channel must satisfy.

    The host validates loaded plugins against this protocol at startup.
    Required methods will raise a clear error if missing; optional methods
    are probed with ``hasattr`` and have sensible fallbacks in the host.
    """

    # --- Required ---------------------------------------------------------

    def get_router(self) -> APIRouter:
        """Return a FastAPI router with all channel-specific endpoints."""
        ...

    def get_manifest(self) -> Dict[str, Any]:
        """Return channel capabilities, UI info, and current status."""
        ...

    async def request_image(self, request_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Generate an image for display.

        Returns a dict with at minimum:
          - ``success``: bool
          - ``bytes``: raw image bytes  (preferred transport)
          - ``content_type``: MIME type (e.g. ``image/jpeg``)
        """
        ...

    # --- Optional (checked via hasattr at runtime) ------------------------
    # These are NOT enforced by the protocol check but are documented here
    # so plugin authors know they exist.
    #
    #   def get_status(self) -> Dict[str, Any]: ...
    #   def on_startup(self) -> None: ...
    #   async def on_shutdown(self) -> None: ...
    #   def register_listener(self, callback: Callable) -> None: ...
    #   def unregister_listener(self, callback: Callable) -> None: ...
    #   def stop(self) -> None: ...
    #   supports_push: bool


class BaseChannel:
    """Optional convenience base class for Mimir channel plugins.

    Provides:
      - Lifecycle hooks (``on_startup`` / ``on_shutdown``) with no-op defaults
      - Sub-channel stub methods
      - Common directory setup
    """

    def __init__(self, channel_dir: str | Path):
        self.channel_dir = Path(channel_dir)
        self.data_dir = self.channel_dir / "data"
        self.data_dir.mkdir(exist_ok=True)

    # --- Lifecycle --------------------------------------------------------

    def on_startup(self) -> None:
        """Called by the host after the router is mounted.

        Override to perform post-mount initialization (e.g. start background
        tasks, warm caches).
        """

    async def on_shutdown(self) -> None:
        """Called by the host during application shutdown.

        Override to clean up resources (stop background threads, close
        connections, persist state).
        """

    # --- Sub-channel stubs ------------------------------------------------

    def supports_subchannels(self) -> bool:
        return False

    def get_subchannels(self) -> List[Dict[str, Any]]:
        return []

    def create_subchannel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Channel does not support sub-channels")

    def update_subchannel(self, subchannel_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Channel does not support sub-channels")

    def delete_subchannel(self, subchannel_id: str) -> bool:
        raise NotImplementedError("Channel does not support sub-channels")

    def assign_content_to_subchannel(
        self, subchannel_id: str, content_ids: List[str], action: str = "add"
    ) -> bool:
        raise NotImplementedError("Channel does not support sub-channels")
