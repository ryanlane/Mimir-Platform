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


def main() -> None:
    api_base = os.getenv("MIMIR_API_BASE", "http://127.0.0.1:5000")
    token = os.getenv("MIMIR_DISCOVERY_TOKEN")
    service_type = os.getenv("MIMIR_MDNS_SERVICE_TYPE", DEFAULT_SERVICE_TYPE)
    batch_seconds = float(os.getenv("MIMIR_BATCH_SECONDS", "1.0"))

    q: "queue.Queue[MdnsEvent]" = queue.Queue(maxsize=2048)

    zc = Zeroconf()
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
            zc.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
