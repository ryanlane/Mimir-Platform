"""In-memory store for transient channel-generated images.

This provides a lightweight mechanism for the `request_image` endpoint to
return a short image URL instead of forcing the frontend to embed or misuse
large base64 payloads inside subsequent GET paths (which was producing URLs
like `/channels/9j/4AAQSk...`).

Design:
  * Images are stored in-process only (ephemeral) – suitable for preview / UI use.
  * Each image gets a UUID `image_id` and is addressable at
    `/api/channels/{channel_id}/images/{image_id}`.
  * A simple TTL-based purge occurs opportunistically on insert / fetch.
  * Thread safety ensured via `RLock`.

Future enhancements (not implemented now):
  * Persistent / shared backing store (Redis / disk) for clustered deployments.
  * Size / count based eviction policy.
  * Optional hashing + de-duplication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock

DEFAULT_TTL_SECONDS = 300  # 5 minutes – sufficient for user to load image
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB safety cap


@dataclass
class StoredChannelImage:
    channel_id: str
    image_id: str
    content: bytes
    content_type: str
    created_at: datetime
    size: int

    def expired(self, now: datetime, ttl: int = DEFAULT_TTL_SECONDS) -> bool:
        return (now - self.created_at).total_seconds() > ttl


class ChannelImageStore:
    """In-memory, TTL-based image cache for channel-generated images."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._images: dict[str, StoredChannelImage] = {}

    def _purge_expired_locked(self) -> None:
        now = datetime.now(timezone.utc)
        expired_keys = [k for k, v in self._images.items() if v.expired(now)]
        for k in expired_keys:
            self._images.pop(k, None)

    def put(self, *, channel_id: str, image_id: str, content: bytes, content_type: str) -> None:
        if len(content) > MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds maximum allowed size")
        rec = StoredChannelImage(
            channel_id=channel_id,
            image_id=image_id,
            content=content,
            content_type=content_type,
            created_at=datetime.now(timezone.utc),
            size=len(content),
        )
        with self._lock:
            self._images[f"{channel_id}:{image_id}"] = rec
            self._purge_expired_locked()

    def get(self, channel_id: str, image_id: str) -> StoredChannelImage | None:
        key = f"{channel_id}:{image_id}"
        with self._lock:
            rec = self._images.get(key)
            if not rec:
                return None
            if rec.expired(datetime.now(timezone.utc)):
                # Expired – remove and report missing
                self._images.pop(key, None)
                return None
            # Opportunistic purge of other expired entries
            self._purge_expired_locked()
            return rec

    def stats(self) -> dict:
        with self._lock:
            total = len(self._images)
            bytes_total = sum(v.size for v in self._images.values())
            return {"entries": total, "bytes": bytes_total}


channel_image_store = ChannelImageStore()
