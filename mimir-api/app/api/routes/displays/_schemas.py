"""Request/response models specific to the displays domain."""
from pydantic import BaseModel, Field


class AssignSceneBody(BaseModel):
    scene_id: str
    subchannel_id: str | None = None
    public_host_hint: str | None = None


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
