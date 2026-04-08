from __future__ import annotations

import os
import queue
import signal
import socket
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf


DEFAULT_SERVICE_TYPE = "_mimir-display._tcp.local."


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_properties(info: ServiceInfo) -> dict[str, str]:
    props: dict[str, str] = {}
    for k, v in (info.properties or {}).items():
        try:
            key = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
        except Exception:
            key = str(k)
        try:
            if isinstance(v, (bytes, bytearray)):
                props[key] = v.decode("utf-8")
            else:
                props[key] = str(v)
        except Exception:
            props[key] = str(v)
    return props


def _parse_addresses(info: ServiceInfo) -> list[str]:
    addrs: list[str] = []
    for addr in info.addresses:
        try:
            if len(addr) == 4:
                addrs.append(socket.inet_ntoa(addr))
            elif len(addr) == 16:
                import ipaddress

                addrs.append(str(ipaddress.ip_address(addr)))
        except Exception:
            continue
    return addrs


@dataclass
class MdnsEvent:
    event: str
    service_name: str
    properties: dict[str, str] | None = None
    addresses: list[str] | None = None
    webhook_port: int | None = None
    seen_at: str | None = None


class _Listener(ServiceListener):
    def __init__(self, zeroconf: Zeroconf, out_q: "queue.Queue[MdnsEvent]", service_type: str):
        self._zc = zeroconf
        self._q = out_q
        self._service_type = service_type

    def add_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._emit_upsert("discovered", service_type, name)

    def update_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        self._emit_upsert("updated", service_type, name)

    def remove_service(self, zeroconf: Zeroconf, service_type: str, name: str) -> None:
        # No ServiceInfo on remove.
        print(f"[discovery] lost service_name={name}")
        self._q.put(MdnsEvent(event="lost", service_name=name, seen_at=_iso_now()))

    def _emit_upsert(self, event: str, service_type: str, name: str) -> None:
        try:
            info = self._zc.get_service_info(service_type, name, timeout=1500)
            if not info:
                return
            props = _parse_properties(info)
            addrs = _parse_addresses(info)
            port = None
            if props.get("webhook_port"):
                try:
                    port = int(props["webhook_port"])
                except Exception:
                    port = None
            display_id = props.get("display_id") or name
            display_name = props.get("display_name") or display_id
            hostname = props.get("hostname") or "unknown"
            addrs_str = ",".join(addrs) if addrs else "-"
            print(
                f"[discovery] {event} display_id={display_id} name={display_name} host={hostname} "
                f"addr={addrs_str} webhook_port={port}"
            )
            self._q.put(
                MdnsEvent(
                    event=event,
                    service_name=name,
                    properties=props,
                    addresses=addrs,
                    webhook_port=port,
                    seen_at=_iso_now(),
                )
            )
        except Exception:
            # best-effort; keep running
            return


class _Poster:
    def __init__(self, *, api_base: str, token: str | None, batch_seconds: float):
        self._api_base = api_base.rstrip("/")
        self._token = token or None
        self._batch_seconds = batch_seconds
        self._stop = threading.Event()

        self._session = requests.Session()

    def stop(self) -> None:
        self._stop.set()

    def run(self, q: "queue.Queue[MdnsEvent]") -> None:
        endpoint = f"{self._api_base}/api/displays/mdns/ingest"
        headers: dict[str, str] = {"content-type": "application/json"}
        if self._token:
            headers["x-mimir-discovery-token"] = self._token

        pending: list[dict[str, Any]] = []
        last_flush = time.monotonic()

        while not self._stop.is_set():
            timeout = max(0.1, self._batch_seconds - (time.monotonic() - last_flush))
            try:
                ev = q.get(timeout=timeout)
                pending.append(
                    {
                        "event": ev.event,
                        "service_name": ev.service_name,
                        "properties": ev.properties,
                        "addresses": ev.addresses,
                        "webhook_port": ev.webhook_port,
                        "seen_at": ev.seen_at,
                    }
                )
            except queue.Empty:
                pass

            if not pending:
                continue

            if (time.monotonic() - last_flush) < self._batch_seconds:
                continue

            body = {"events": pending}
            try:
                resp = self._session.post(endpoint, json=body, headers=headers, timeout=3)
                if resp.status_code >= 400:
                    # keep minimal noise; retry next cycle
                    last_flush = time.monotonic()
                    continue
                pending = []
            except Exception:
                # best-effort; retry next cycle
                pass
            finally:
                last_flush = time.monotonic()


SERVER_SERVICE_TYPE = "_mimir._tcp.local."


def _get_local_ip() -> str:
    """Return the primary outbound LAN IP of this host."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def _parse_api_base(api_base: str) -> tuple[str, int]:
    """Extract (host, port) from a URL like http://127.0.0.1:5000."""
    import urllib.parse
    parsed = urllib.parse.urlparse(api_base)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.hostname or "127.0.0.1", port


def _normalize_mdns_host(raw: str | None) -> str:
    host = (raw or "mimir.local").strip().rstrip(".")
    if not host:
        return "mimir.local"
    if not host.endswith(".local"):
        host = f"{host}.local"
    return host


def _register_server(
    zc: Zeroconf,
    api_port: int,
    api_prefix: str = "/api",
    advertised_host: str | None = None,
) -> ServiceInfo | None:
    """Advertise the Mimir API server on _mimir._tcp.local. using the host's LAN IP."""
    try:
        import ipaddress
        local_ip = _get_local_ip()
        mdns_host = _normalize_mdns_host(advertised_host)
        instance_name = mdns_host[:-6] if mdns_host.endswith(".local") else mdns_host
        info = ServiceInfo(
            type_=SERVER_SERVICE_TYPE,
            name=f"{instance_name}.{SERVER_SERVICE_TYPE}",
            addresses=[ipaddress.IPv4Address(local_ip).packed],
            port=api_port,
            properties={
                b"api_prefix": api_prefix.encode(),
                b"version": b"1",
                b"host": mdns_host.encode(),
            },
            server=f"{mdns_host}.",
        )
        zc.register_service(info)
        print(
            f"[discovery] registered Mimir server at {local_ip}:{api_port} as {SERVER_SERVICE_TYPE} host={mdns_host}"
        )
        return info
    except Exception as exc:
        print(f"[discovery] failed to register server advertisement: {exc}", file=sys.stderr)
        return None


def main() -> None:
    api_base = os.getenv("MIMIR_API_BASE", "http://127.0.0.1:5000")
    token = os.getenv("MIMIR_DISCOVERY_TOKEN")
    service_type = os.getenv("MIMIR_MDNS_SERVICE_TYPE", DEFAULT_SERVICE_TYPE)
    batch_seconds = float(os.getenv("MIMIR_BATCH_SECONDS", "1.0"))
    api_prefix = os.getenv("MIMIR_API_PREFIX", "/api")
    public_mdns_host = os.getenv("MIMIR_PUBLIC_HOSTNAME") or os.getenv("PUBLIC_MDNS_HOST")

    q: "queue.Queue[MdnsEvent]" = queue.Queue(maxsize=2048)

    zc = Zeroconf()

    # Advertise the Mimir server so display clients can discover it without
    # knowing the server's IP in advance (no PLATFORM_URL needed in .env).
    _, api_port = _parse_api_base(api_base)
    server_info = _register_server(zc, api_port, api_prefix, public_mdns_host)

    listener = _Listener(zc, q, service_type)
    browser = ServiceBrowser(zc, service_type, listener)

    poster = _Poster(api_base=api_base, token=token, batch_seconds=batch_seconds)
    t = threading.Thread(target=poster.run, args=(q,), daemon=True)
    t.start()

    stop = threading.Event()

    def _handle(sig: int, _frame: Any) -> None:
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    # Keep running
    try:
        while not stop.is_set():
            time.sleep(0.5)
    finally:
        try:
            poster.stop()
        except Exception:
            pass
        try:
            browser.cancel()
        except Exception:
            pass
        try:
            if server_info:
                zc.unregister_service(server_info)
        except Exception:
            pass
        try:
            zc.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
