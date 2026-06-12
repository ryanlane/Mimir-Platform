"""In-memory tracking of the last image command sent to each display.

Lightweight, process-local store used for diagnostics endpoints.
Can be replaced later with persistent storage if needed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass
class DisplayImageRecord:
    device_id: str
    assignment_id: str
    image_url: str
    sent_at: datetime
    image_width: int | None = None
    image_height: int | None = None
    image_format: str | None = None
    scene_id: str | None = None
    subchannel_id: str | None = None
    image_path: str | None = None  # local filesystem path if swap stored

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sent_at"] = self.sent_at.isoformat()
        return d


class DisplayLastImageStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._records: dict[str, DisplayImageRecord] = {}

    def update(self, *, device_id: str, assignment_id: str, image_url: str,
               image_width: int | None, image_height: int | None, image_format: str | None,
               scene_id: str | None, subchannel_id: str | None, image_path: str | None = None) -> None:
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
                image_path=image_path,
            )

    def get(self, device_id: str) -> DisplayImageRecord | None:
        with self._lock:
            return self._records.get(device_id)

    def delete(self, device_id: str) -> bool:
        with self._lock:
            return self._records.pop(device_id, None) is not None

    def all(self) -> dict[str, DisplayImageRecord]:
        with self._lock:
            return dict(self._records)


display_last_image_store = DisplayLastImageStore()
