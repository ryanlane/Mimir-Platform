"""Provisioning and bootstrap endpoints."""
import base64
import json
import logging
import secrets as _secrets
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DisplayClient
from app.schemas.displays import DisplayClientResponse
from app.services.mdns_discovery import mdns_discovery_service

from ._helpers import (
    _build_client_config,
    _build_registered_display_response,
    _mqtt_host_for_clients,
    _normalize_public_host_hint,
    _normalize_setup_url,
    _pick_webhook_address,
    _platform_url_for_clients,
    _provision_url_from_setup_url,
    _request_host_if_reachable,
    build_http_url,
    get_db,
)
from ._schemas import (
    MqttBootstrapRequest,
    ProvisionRegisterRequest,
    SetupProvisionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Provision token store (in-process, ephemeral)
# ---------------------------------------------------------------------------

_PROVISION_TOKEN_TTL = 600
_PROVISION_TOKENS: dict[str, float] = {}


def _issue_provision_token() -> str:
    reg_token = _secrets.token_hex(24)
    _PROVISION_TOKENS[reg_token] = time.monotonic() + _PROVISION_TOKEN_TTL
    return reg_token


def _consume_provision_token(reg_token: str) -> bool:
    expires_at = _PROVISION_TOKENS.pop(reg_token, None)
    return isinstance(expires_at, float) and expires_at > time.monotonic()


# ---------------------------------------------------------------------------
# Provision bundle helpers
# ---------------------------------------------------------------------------

def _build_provision_bundle_payload(request: Request | None) -> dict[str, object]:
    payload = {
        "v": 1,
        "platform_url": _platform_url_for_clients(request) or "",
        "mqtt_host": _mqtt_host_for_clients(request) or "",
        "mqtt_port": settings.mqtt_public_port or settings.mqtt_broker_port,
        "reg_token": _issue_provision_token(),
    }
    if settings.mqtt_expose_credentials:
        payload["mqtt_username"] = settings.mqtt_username
        payload["mqtt_password"] = settings.mqtt_password
    return payload


def _encode_provision_bundle(payload: dict[str, object]) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/provision-bundle")
async def get_provision_bundle(request: Request):
    """Generate a one-time provision bundle for QR/manual onboarding."""
    payload = _build_provision_bundle_payload(request)
    return {
        "bundle": _encode_provision_bundle(payload),
        "payload": payload,
    }


@router.post("/provision-from-setup")
async def provision_from_setup_url(body: SetupProvisionRequest, request: Request):
    """Send a one-time provision bundle to a display setup endpoint."""
    setup_url = _normalize_setup_url(body.setup_url)
    provision_url = _provision_url_from_setup_url(setup_url)
    payload = _build_provision_bundle_payload(request)
    public_host_hint = _normalize_public_host_hint(body.public_host_hint)
    if public_host_hint:
        payload["platform_url"] = build_http_url(public_host_hint, settings.public_port or settings.api_port)
        payload["mqtt_host"] = public_host_hint
    if body.display_name:
        payload["display_name"] = body.display_name
    if body.display_location:
        payload["display_location"] = body.display_location

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.post(
                provision_url,
                json={"bundle": _encode_provision_bundle(payload)},
            )
            if response.status_code >= 300:
                raise HTTPException(
                    status_code=502,
                    detail=f"Display setup service rejected provisioning ({response.status_code})",
                )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach display setup service: {exc}",
        ) from exc

    return {
        "status": "sent",
        "setup_url": setup_url,
        "provision_url": provision_url,
        "payload": payload,
        "message": "Provisioning sent. The display should finish registering within a few seconds.",
    }


@router.post("/bootstrap/{display_id}")
async def bootstrap_display_config(display_id: str, body: MqttBootstrapRequest, request: Request):
    """Push full onboarding config to a discovered display webhook."""
    display = mdns_discovery_service.get_display_by_id(display_id)
    if not display:
        raise HTTPException(status_code=404, detail="Display not found in discovery cache")
    if not display.addresses or not display.webhook_port:
        raise HTTPException(status_code=409, detail="Display has no webhook endpoint")

    addr = _pick_webhook_address(display.addresses)
    if not addr:
        raise HTTPException(status_code=409, detail="Display has no usable address")

    from urllib.parse import urlparse
    public_host_hint = _normalize_public_host_hint(body.public_host_hint)
    host = (
        public_host_hint
        or body.host
        or settings.mqtt_public_host
        or settings.public_mdns_host
        or _request_host_if_reachable(request)
        or urlparse(_platform_url_for_clients(request) or "").hostname
        or settings._discover_primary_ipv4()
        or settings.mqtt_broker_host
    )
    port = body.port or settings.mqtt_public_port or settings.mqtt_broker_port
    platform_url = body.platform_url
    if not platform_url:
        platform_url = (
            build_http_url(public_host_hint, settings.public_port or settings.api_port)
            if public_host_hint
            else _platform_url_for_clients(request)
        )
    reg_token = _issue_provision_token()

    payload: dict[str, object] = {
        "host": host,
        "port": port,
        "platform_url": platform_url,
        "reg_token": reg_token,
        "source": "mdns_bootstrap",
    }
    if body.display_name:
        payload["display_name"] = body.display_name
    if body.display_location:
        payload["display_location"] = body.display_location
    if settings.mqtt_expose_credentials:
        payload["username"] = body.username or settings.mqtt_username
        payload["password"] = body.password or settings.mqtt_password
    elif body.username or body.password:
        payload["username"] = body.username
        payload["password"] = body.password

    url = f"http://{addr}:{display.webhook_port}/config"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code >= 300:
                raise HTTPException(status_code=502, detail=f"Webhook failed: {res.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Webhook error: {e}") from e

    return {"status": "sent", "webhook_url": url, "payload": payload}


@router.post("/provision-register", response_model=DisplayClientResponse, tags=["pairing"])
async def provision_register(body: ProvisionRegisterRequest, db: Session = Depends(get_db)):
    """Register a display after webhook/bootstrap provisioning."""
    from app.services.mqtt.registration import AutoRegistrationService

    if not _consume_provision_token(body.reg_token):
        raise HTTPException(status_code=401, detail="Invalid or expired provision token")

    device_id = body.device_id
    capabilities = body.capabilities or {}
    metadata = body.metadata or {}
    name = metadata.get("name") or body.hostname or device_id
    location = metadata.get("location") or "Unknown"
    hostname = body.hostname or device_id
    resolution = capabilities.get("resolution") or capabilities.get("native_resolution") or [800, 480]
    orientation = capabilities.get("orientation", "landscape")
    client_version = metadata.get("client_version", "unknown")

    existing = db.query(DisplayClient).filter(DisplayClient.hostname == hostname).first()
    if existing:
        existing.name = name
        existing.location = location
        existing.is_online = True
        existing.last_seen = datetime.now(timezone.utc)
        existing.client_version = client_version
        existing.orientation = orientation
        existing.discovery_method = "provision_bundle"
        existing.redis_distribution = bool(capabilities.get("redis_distribution", False))
        existing.content_claiming = bool(capabilities.get("content_claiming", False))
        if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
            existing.width = int(resolution[0])
            existing.height = int(resolution[1])
        db.commit()
        db.refresh(existing)
        display = existing
    else:
        display = DisplayClient(
            id=str(uuid.uuid4()),
            name=name,
            location=location,
            hostname=hostname,
            display_type="registered",
            discovery_method="provision_bundle",
            is_online=True,
            last_seen=datetime.now(timezone.utc),
            client_version=client_version,
            orientation=orientation,
            redis_distribution=bool(capabilities.get("redis_distribution", False)),
            content_claiming=bool(capabilities.get("content_claiming", False)),
        )
        if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
            display.width = int(resolution[0])
            display.height = int(resolution[1])
        db.add(display)
        db.commit()
        db.refresh(display)

    client_config = _build_client_config(
        display_name=display.name,
        display_location=display.location or "",
        display_orientation=display.orientation,
    )

    reg_service = AutoRegistrationService()
    reg_key = _secrets.token_hex(16)
    await reg_service._send_finalize_command(
        device_id=device_id,
        display_id=str(display.id),
        registration_key=reg_key,
        client_config=client_config,
    )

    return DisplayClientResponse.model_validate(_build_registered_display_response(display))
