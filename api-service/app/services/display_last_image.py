"""In-memory tracking of the last image command sent to each display.

Lightweight, process-local store used for diagnostics endpoints.
Can be replaced later with persistent storage if needed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from threading import RLock


@dataclass
class DisplayImageRecord:
    device_id: str
    assignment_id: str
    image_url: str
    sent_at: datetime
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    image_format: Optional[str] = None
    scene_id: Optional[str] = None
    subchannel_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["sent_at"] = self.sent_at.isoformat()
        return d


class DisplayLastImageStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: Dict[str, DisplayImageRecord] = {}

    def update(self, *, device_id: str, assignment_id: str, image_url: str,
               image_width: Optional[int], image_height: Optional[int], image_format: Optional[str],
               scene_id: Optional[str], subchannel_id: Optional[str]) -> None:
        with self._lock:
            self._records[device_id] = DisplayImageRecord(
                device_id=device_id,
                assignment_id=assignment_id,
                image_url=image_url,
                sent_at=datetime.now(timezone.utc),
                image_width=image_width,
                image_height=image_height,
                image_format=image_format,
                scene_id=scene_id,
                subchannel_id=subchannel_id,
            )

    def get(self, device_id: str) -> Optional[DisplayImageRecord]:
        with self._lock:
            return self._records.get(device_id)

    def all(self) -> Dict[str, DisplayImageRecord]:
        with self._lock:
            return dict(self._records)


display_last_image_store = DisplayLastImageStore()
