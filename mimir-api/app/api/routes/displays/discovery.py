"""mDNS discovery and MQTT config endpoints."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.services.mdns_discovery import mdns_discovery_service

from ._helpers import _mqtt_host_for_clients, _platform_url_for_clients
from ._schemas import MdnsIngestBody, MqttConfigResponse

router = APIRouter()


@router.post("/mdns/ingest", response_model=dict)
async def ingest_mdns_events(body: MdnsIngestBody, request: Request):
    """Ingest mDNS discovery events from an external host-network discovery service."""
    if not settings.mdns_external_feed_enabled:
        raise HTTPException(status_code=404, detail="External mDNS ingest disabled")

    expected = settings.mdns_external_feed_token
    if expected:
        provided = request.headers.get("x-mimir-discovery-token")
        if not provided or provided != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")

    if not mdns_discovery_service.is_running:
        await mdns_discovery_service.start_external_feed()

    ingested = 0
    errors: list[str] = []
    for e in body.events:
        try:
            seen_dt = None
            if e.seen_at:
                try:
                    seen_dt = datetime.fromisoformat(e.seen_at.replace('Z', '+00:00'))
                except Exception:
                    seen_dt = None
            mdns_discovery_service.ingest_external_event(
                event=e.event,
                service_name=e.service_name,
                properties=e.properties,
                addresses=e.addresses,
                webhook_port=e.webhook_port,
                seen_at=seen_dt,
            )
            ingested += 1
        except Exception as exc:
            errors.append(f"{e.service_name}: {exc}")

    return {"ingested": ingested, "errors": errors}


@router.get("/mqtt/config", response_model=MqttConfigResponse)
async def get_mqtt_config(request: Request):
    """Return MQTT broker configuration for display clients."""
    host = _mqtt_host_for_clients(request)
    port = settings.mqtt_public_port or settings.mqtt_broker_port
    platform_url = _platform_url_for_clients(request)
    payload: dict[str, object] = {
        "enabled": settings.mqtt_enabled,
        "host": host,
        "port": port,
        "platform_url": platform_url,
    }
    if settings.mqtt_expose_credentials:
        payload["username"] = settings.mqtt_username
        payload["password"] = settings.mqtt_password
    return payload  # type: ignore[return-value]


@router.get("/discovery/status")
async def get_discovery_status():
    """Get current mDNS discovery service status"""
    stats = mdns_discovery_service.get_discovery_stats()
    discovered = mdns_discovery_service.get_discovered_displays()

    return {
        "service_status": stats,
        "ingest": {
            "external_feed_enabled": bool(getattr(settings, "mdns_external_feed_enabled", False)),
            "token_required": bool(getattr(settings, "mdns_external_feed_token", None)),
            "endpoint": "/api/displays/mdns/ingest",
        },
        "discovered_displays": [
            {
                "display_id": d.display_id,
                "display_name": d.display_name,
                "hostname": d.hostname,
                "location": d.location,
                "addresses": d.addresses,
                "is_online": d.is_online,
                "last_seen": d.last_seen.isoformat(),
                "discovered_at": d.discovered_at.isoformat()
            }
            for d in discovered
        ]
    }


@router.get("/discovery/live")
async def get_live_discovered_displays():
    """Get currently discovered displays from the live discovery cache.

    Cache is populated either by native Zeroconf browsing, or by external-feed ingest.
    """
    if not mdns_discovery_service.is_running:
        raise HTTPException(
            status_code=503,
            detail="Discovery service is not running."
        )

    discovered = mdns_discovery_service.get_discovered_displays()

    return {
        "total_discovered": len(discovered),
        "online_count": sum(1 for d in discovered if d.is_online),
        "discovered_displays": [
            {
                "service_name": d.service_name,
                "display_id": d.display_id,
                "display_name": d.display_name,
                "hostname": d.hostname,
                "location": d.location,
                "addresses": d.addresses,
                "webhook_port": d.webhook_port,
                "resolution": d.resolution,
                "client_version": d.client_version,
                "is_online": d.is_online,
                "discovered_at": d.discovered_at.isoformat(),
                "last_seen": d.last_seen.isoformat(),
                "properties": d.properties,
                "webhook_url": f"http://{d.addresses[0]}:{d.webhook_port}" if d.addresses and d.webhook_port else None
            }
            for d in discovered
        ]
    }


@router.post("/discovery/start")
async def start_discovery_service():
    """Start the mDNS discovery service"""
    if mdns_discovery_service.is_running:
        return {"status": "already_running", "message": "mDNS discovery service is already running"}

    if getattr(settings, "mdns_external_feed_enabled", False):
        success = await mdns_discovery_service.start_external_feed()
        if success:
            return {"status": "started", "mode": "external_feed", "message": "Discovery external feed started"}

    if not mdns_discovery_service.is_available:
        raise HTTPException(status_code=501, detail="mDNS discovery not available")

    success = await mdns_discovery_service.start_discovery()
    if success:
        return {"status": "started", "mode": "native", "message": "mDNS discovery service started successfully"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to start mDNS discovery service"
        )


@router.post("/discovery/stop")
async def stop_discovery_service():
    """Stop the mDNS discovery service"""
    await mdns_discovery_service.stop_discovery()
    return {"status": "stopped", "message": "mDNS discovery service stopped"}
