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

"""Request/response models specific to the displays domain."""
from pydantic import BaseModel, Field


class AssignSceneBody(BaseModel):
    scene_id: str
    subchannel_id: str | None = None
    public_host_hint: str | None = None
    content_variant: str | None = None


class MdnsIngestEvent(BaseModel):
    event: str  # discovered|updated|lost
    service_name: str
    properties: dict[str, str] | None = None
    addresses: list[str] | None = None
    webhook_port: int | None = None
    seen_at: str | None = None  # ISO8601; optional


class MdnsIngestBody(BaseModel):
    events: list[MdnsIngestEvent]


class MqttConfigResponse(BaseModel):
    enabled: bool
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    platform_url: str | None = None


class MqttBootstrapRequest(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    platform_url: str | None = None
    display_name: str | None = None
    display_location: str | None = None
    public_host_hint: str | None = None


class ProvisionRegisterRequest(BaseModel):
    reg_token: str
    device_id: str
    hostname: str
    capabilities: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class SetupProvisionRequest(BaseModel):
    setup_url: str
    display_name: str | None = None
    display_location: str | None = None
    public_host_hint: str | None = None
