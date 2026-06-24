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

# app/services/mqtt/types.py
from datetime import datetime
from typing import Any

from pydantic import BaseModel, HttpUrl


class StatusPayload(BaseModel):
    status: str
    timestamp: datetime
    reason: str | None = None
    version: str | None = None

class AssignDelivery(BaseModel):
    type: str = "url"
    url: HttpUrl
    content_type: str = "image/png"
    etag: str = "v1"
    ttl_seconds: int = 3600

class AssignContent(BaseModel):
    delivery: AssignDelivery
    metadata: dict[str, Any] = {}

class AssignCommand(BaseModel):
    type: str = "assign"
    assignment_id: str
    sequence: int = 1
    scene_id: str
    scene_name: str
    content: AssignContent
    timestamp: datetime
    # Update semantics:
    # update_type: "push" for real-time push updates, "scheduled" for polling/scheduler-driven.
    # refresh_interval_s: Polling interval in seconds when update_type == "scheduled".
    #   Must be omitted or null when update_type == "push".
    update_type: str | None = None
    refresh_interval_s: int | None = None

    class Config:
        json_schema_extra = {
            "description": (
                "Assign command sent to display clients. New optional fields 'update_type' and "
                "'refresh_interval_s' communicate whether the scene should be updated by push "
                "events or by client polling. Older clients can ignore these fields safely."
            )
        }

class ClearSceneCommand(BaseModel):
    type: str = "clear_scene"
    assignment_id: str
    timestamp: datetime
