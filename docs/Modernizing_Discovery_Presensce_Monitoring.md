# Quick verdict

* Keep: WebSockets to your dashboard, mDNS for zero-config discovery. (Both are fine!)
* Replace/augment: home-rolled metrics loops and “is-offline” timers with standard telemetry + a presence channel.
* Standardize: scheduling and background loops with a real scheduler so replicas don’t spawn duplicate workers.

# Concrete upgrades

### 1) Observability: swap bespoke metrics for OpenTelemetry → Prometheus (+Grafana)

Right now you’re collecting & broadcasting metrics from a 30-second loop and pushing them over WebSocket to the UI . Instead, instrument your API/services with OpenTelemetry metrics (Counters/Histograms) and expose a Prometheus scrape endpoint. Let Grafana render the charts; your dashboard can still subscribe to “events” over WS if you like.

* OTel Python + Collector is the current best-practice path; export to Prometheus or your vendor of choice. ([OpenTelemetry][1])
* Prometheus exporter is pull-based (Prom scrapes your app). ([OpenTelemetry][2])
* Step-by-step OTel metrics in Python guides are plentiful. ([Better Stack][3])

**Why?** You delete custom sampling/aggregation code, get alerts and long-term trends for free, and your backend becomes observable across instances.

---

### 2) Scheduling: replace ad-hoc `asyncio.create_task(...)` loops with APScheduler 4.x

Both documents start background jobs from app startup (e.g., 30-second monitors and discovery loops)  . Use APScheduler’s `AsyncScheduler` with a database job store so jobs are durable and you can coalesce or add jitter. In multi-instance deployments, you also avoid duplicate loops.

* APScheduler is actively maintained, supports asyncio, and scales from single process to multi-node with shared stores. ([PyPI][4], [GitHub][5])
* The 4.x line introduced notable changes/executors (worth adopting if you’re on older versions). ([GitHub][6], [apscheduler.readthedocs.io][7])

**Why?** Clear job lifecycle, easier tuning, and fewer “is this loop running twice?” headaches.

---

### 3) Discovery/presence: keep Zeroconf, add MQTT LWT for “online/offline”

mDNS via `zeroconf` is still the Python standard and it now has asyncio support; keep it for discovery and basic capabilities .

* `python-zeroconf` remains current (0.147.0 as of May 2025) and battle-tested. ([PyPI][8])
* Asyncio support exists in the project (and older notes mention the asyncio layer). ([GitHub][9], [PyPI][10])

For **online/offline**, rather than polling “last\_seen > timeout” every 30–120s, have devices maintain an MQTT connection and set a **Last Will and Testament (LWT)** topic. If a device drops unexpectedly, the broker publishes the offline message instantly—no timers.

* LWT is the canonical way IoT systems detect offline clients. ([HiveMQ][11], [www.emqx.com][12], [ThingsBoard][13])

**Why?** Presence becomes event-driven and immediate; you can remove custom offline timers and much of the monitoring loop, while still using mDNS for initial discovery.

---

### 4) Content distribution/events: use Redis Streams (or MQTT topics) rather than ad-hoc keys

Your system tracks leases, queue sizes, rates, and emits a bunch of WS events (assign/release/queue updates) . Consider modeling these as **Redis Streams** with **consumer groups**—or as MQTT topics if you embrace MQTT.

* Streams + consumer groups give you ordered, durable, at-least-once event processing and easy horizontal scale. ([Redis][14], [InfoWorld][15])
* Plenty of concise Python examples exist for consumer groups. ([GitHub][16])

**Why?** You get replay, back-pressure, and fewer custom coordination primitives. Your WS dashboard can read from a materialized view or subscribe to summarized metrics rather than raw internal structures.

---

### 5) Keep the WebSocket UI, but power charts from Prometheus

Your Distribution Monitor component can stay, but fetch trend data from Prometheus (or via your OTel collector) instead of custom WS payloads. Real-time “events” (e.g., “content\_assigned”) can still be broadcast over WS for UX responsiveness, but time-series charts pull from Prom for accuracy and history.&#x20;

---

# Suggested “modern defaults” stack

* **Discovery:** `zeroconf` (async API) for `_mimir-display._tcp.local.`; auto-register on first sight. ([PyPI][8], [GitHub][9])
* **Presence/health:** MQTT (Mosquitto/EMQX/HiveMQ CE) with LWT for online/offline + periodic heartbeat topics. ([HiveMQ][11], [www.emqx.com][12], [ThingsBoard][13])
* **Scheduling:** APScheduler 4.x `AsyncScheduler` with a SQL job store. ([PyPI][4], [GitHub][5])
* **Events/queues:** Redis Streams (+ consumer groups) for assignments & queue updates (or MQTT if going all-in on brokered messaging). ([Redis][14], [InfoWorld][15])
* **Metrics:** OpenTelemetry SDK → OTel Collector → Prometheus → Grafana. ([OpenTelemetry][1])
* **UI:** Keep WebSockets for live toasts; chart long-term metrics from Prom.

# What you can delete or simplify

* The 30-second “are they offline yet?” loop—replaced by MQTT LWT presence.&#x20;
* Custom metric aggregation/broadcast loops—replaced by OTel + Prometheus scraping.&#x20;
* Ad-hoc Redis structures for events—replaced by Streams with consumer groups.&#x20;

# Modernizing Discovery, Presence & Monitoring (with minimal code)

This doc captures the “modern defaults” we discussed, plus drop-in code for OpenTelemetry metrics (scraped by Prometheus), durable scheduling with APScheduler, and instant presence via MQTT Last-Will (LWT).

## TL;DR

* **Discovery**: keep mDNS/`zeroconf` (async) for zero-config service findability.
* **Presence**: publish `online`/`offline` via **MQTT LWT** instead of polling.
* **Metrics**: instrument with **OpenTelemetry** and expose `/metrics` for **Prometheus**.
* **Jobs**: run background loops with **APScheduler (AsyncIOScheduler)** with a DB job store.

Why these choices? OTel + Prometheus is a common, well-documented pattern; Prometheus can scrape OTel-exposed metrics or receive OTLP directly. ([OpenTelemetry][1], [Prometheus][2])
For scheduling, APScheduler’s AsyncIOScheduler is the standard in-process scheduler for asyncio apps; the 3.x line is stable today (4.0 exists but is still evolving). ([apscheduler.readthedocs.io][3])
For presence, MQTT’s **Last Will and Testament** is the canonical instant “went offline unexpectedly” signal. ([HiveMQ][4])

---

## 1) OpenTelemetry metrics → Prometheus (FastAPI)

This is the smallest workable OTel setup that:

* uses OTel’s **Prometheus Metric Reader** to bridge metrics to Prometheus, and
* mounts a `/metrics` endpoint in your FastAPI app.

> Prometheus can scrape OTel-exposed metrics, or you can point OTel at Prometheus’ OTLP receiver; the exporter/reader options are documented by OTel and Prometheus. ([OpenTelemetry][5], [Prometheus][2])

### Install

```bash
pip install fastapi uvicorn
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-exporter-prometheus prometheus-client
```

### FastAPI + OTel + Prometheus (minimal)

```python
# app.py
from fastapi import FastAPI, Request
from prometheus_client import make_asgi_app
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.metrics import set_meter_provider, get_meter_provider
from opentelemetry.exporter.prometheus import PrometheusMetricReader

# 1) Wire up OTel metrics with a Prometheus reader
reader = PrometheusMetricReader()  # exposes metrics via prometheus_client registry
provider = MeterProvider(metric_readers=[reader])
set_meter_provider(provider)
meter = get_meter_provider().get_meter("mimir")

# Example instruments
http_requests = meter.create_counter(
    name="http_requests_total", unit="1", description="HTTP requests"
)
http_latency = meter.create_histogram(
    name="http_request_duration_seconds", unit="s", description="Request latency"
)

# 2) FastAPI app
app = FastAPI()

# 3) Simple middleware to record per-request metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    import time
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.perf_counter() - start
        http_requests.add(1, {"method": request.method, "path": request.url.path})
        http_latency.record(elapsed, {"method": request.method, "path": request.url.path})

# 4) Mount the Prometheus /metrics endpoint
#    (prometheus_client provides a tiny ASGI app you can mount)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Hello route
@app.get("/hello")
async def hello():
    return {"ok": True}
```

Run it:

```bash
uvicorn app:app --reload
# scrape http://localhost:8000/metrics
```

* Prometheus’ ASGI helper `make_asgi_app()` is the recommended way to expose `/metrics` in FastAPI. ([PyPI][6])
* OTel’s Prometheus reader is the supported “pull” path for Prom scraping (alternative: emit OTLP to Prom’s OTLP receiver). ([OpenTelemetry][5], [Prometheus][2])

### Prometheus scrape config (snippet)

```yaml
scrape_configs:
  - job_name: mimir-api
    scrape_interval: 15s
    static_configs:
      - targets: ["host.docker.internal:8000"]  # or "mimir-api:8000"
```

> If you prefer, enable Prometheus’ **OTLP receiver** and send metrics via OTLP instead of exposing `/metrics`. ([Prometheus][2])

---

## 2) Durable background jobs with APScheduler (AsyncIO)

Use APScheduler’s `AsyncIOScheduler` and a SQL job store so tasks are durable and you avoid duplicate loops across processes.

### Install

```bash
pip install APScheduler sqlalchemy
```

### FastAPI + AsyncIOScheduler + SQLAlchemy job store

```python
# scheduler.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url="sqlite:///jobs.sqlite")},
    timezone="UTC",
)

# Example async job (e.g., device discovery)
async def discover_devices():
    # ... your mDNS/zeroconf discovery here ...
    pass

def setup_jobs():
    scheduler.add_job(
        discover_devices,
        trigger="interval",
        seconds=30,
        id="discovery",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        jitter=5,
        replace_existing=True,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_jobs()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown()  # graceful stop

app = FastAPI(lifespan=lifespan)
```

* `AsyncIOScheduler` is the asyncio-native scheduler; 3.x is stable and widely used in production today. ([apscheduler.readthedocs.io][3])
* APScheduler 4.0 is an ongoing rewrite; consult the migration notes when you decide to move. ([apscheduler.readthedocs.io][7])

---

## 3) Instant online/offline with MQTT LWT

Use MQTT to publish device presence. With **Last Will and Testament**, the **broker** publishes an “offline” message automatically if a device disconnects unexpectedly—no polling required.

### Install

```bash
pip install paho-mqtt
# (optional asyncio flavor) pip install asyncio-mqtt
```

### Minimal Paho client with LWT (threaded loop)

```python
# presence.py
import socket, os, time
import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT   = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", socket.gethostname())
BASE = f"mimir/{DEVICE_ID}"

client = mqtt.Client(client_id=f"{DEVICE_ID}", clean_session=True, protocol=mqtt.MQTTv311)

# 1) Set Last Will BEFORE connecting:
client.will_set(f"{BASE}/status", payload="offline", qos=1, retain=True)  # LWT

def on_connect(c, userdata, flags, rc):
    # Publish ONLINE each (re)connect
    c.publish(f"{BASE}/status", "online", qos=1, retain=True)

client.on_connect = on_connect

client.connect(BROKER, PORT, keepalive=30)
client.loop_start()  # background network thread

# Example heartbeat (optional, if you want a 'last_seen' timestamp)
while True:
    client.publish(f"{BASE}/heartbeat", str(int(time.time())), qos=0, retain=False)
    time.sleep(30)
```

**Notes**

* **Always** call `will_set()` before `connect()`; the broker will emit the Will on ungraceful disconnects. ([steves-internet-guide.com][8], [Stack Overflow][9])
* LWT is the standard way to signal unexpected disconnects in MQTT. ([HiveMQ][4])
* Prefer small `keepalive` (e.g., 30s) if you want quicker failure detection.

### Optional: asyncio style with `asyncio-mqtt`

```python
# presence_async.py
import socket, os, asyncio
from asyncio_mqtt import Client, MqttError

BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT   = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", socket.gethostname())
BASE = f"mimir/{DEVICE_ID}"

async def main():
    async with Client(BROKER, PORT, client_id=DEVICE_ID, will=(f"{BASE}/status","offline",1,True)) as client:
        await client.publish(f"{BASE}/status", "online", qos=1, retain=True)
        while True:
            await client.publish(f"{BASE}/heartbeat", "tick", qos=0)
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
```

* `asyncio-mqtt` wraps Paho with a clean `async` API, including a `will=` parameter for LWT. ([PyPI][10])

---

## 4) Discovery (keep mDNS/zeroconf)

Continue advertising/looking up your service (e.g., `_mimir-display._tcp.local.`) with `zeroconf`—it remains the de-facto Python library and has asyncio support. (You’ll combine this with MQTT presence so the dashboard immediately updates “offline” without polling.) ([Uptrace][11], [Stack Overflow][12])

---

## 5) Putting it together

* **Device boot**:

  1. Start MQTT client (publish retained `online`, set LWT to `offline`).
  2. Start your service and advertise via mDNS.
* **API**:

  1. Start FastAPI with APScheduler via `lifespan`.
  2. Expose `/metrics` for Prometheus.
* **Dashboard**:

  * Subscribe to `mimir/+/status` and `mimir/+/heartbeat` for instant presence and last-seen.
  * Pull charts from Prometheus; keep WebSockets for “live” UX events.

---

## Appendices

### A. Prometheus via OTLP (alternative)

If you’d rather not expose `/metrics`, Prometheus can ingest **OTLP over HTTP** directly; enable `--web.enable-otlp-receiver` and point your OTel SDK to Prom’s OTLP endpoint. ([Prometheus][2])

### B. Why not just `prometheus_client`?

You *can*—it’s the simplest possible FastAPI integration (mount `/metrics` and use counters/histograms directly). But OTel gives you vendor-neutral metrics that can also flow to an OTel Collector, tracing backends, etc. (You can still expose a `/metrics` endpoint using OTel’s Prometheus reader.) ([PyPI][6], [OpenTelemetry][5])

---

## Package quicklist

```
zeroconf
paho-mqtt           # or asyncio-mqtt
fastapi uvicorn
opentelemetry-api opentelemetry-sdk
opentelemetry-exporter-prometheus prometheus-client
APScheduler sqlalchemy
```

If you want, I can tailor these snippets to your exact repo layout (e.g., wire them into your existing `mDNS_Discovery` loop and Distribution Monitor), or convert your current polling logic to pure MQTT presence.

[1]: https://opentelemetry.io/blog/2024/prom-and-otel/?utm_source=chatgpt.com "Prometheus and OpenTelemetry - Better Together"
[2]: https://prometheus.io/docs/guides/opentelemetry/?utm_source=chatgpt.com "Using Prometheus as your OpenTelemetry backend"
[3]: https://apscheduler.readthedocs.io/?utm_source=chatgpt.com "Advanced Python Scheduler — APScheduler 3.11.0.post1 ..."
[4]: https://www.hivemq.com/blog/mqtt-essentials-part-9-last-will-and-testament/?utm_source=chatgpt.com "What is MQTT Last Will and Testament (LWT)?"
[5]: https://opentelemetry.io/docs/languages/python/exporters/?utm_source=chatgpt.com "Exporters"
[6]: https://pypi.org/project/prometheus-client/0.17.1/?utm_source=chatgpt.com "prometheus-client 0.17.1"
[7]: https://apscheduler.readthedocs.io/en/master/versionhistory.html?utm_source=chatgpt.com "Version history — APScheduler documentation - Read the Docs"
[8]: https://www.steves-internet-guide.com/mqtt-last-will-example/?utm_source=chatgpt.com "MQTT Last Will and Testament (LWT) Use and Examples"
[9]: https://stackoverflow.com/questions/28612283/problems-with-mosquitto-and-last-will-testament?utm_source=chatgpt.com "python - Problems with Mosquitto and last will (testament)"
[10]: https://pypi.org/project/asyncio-mqtt/?utm_source=chatgpt.com "asyncio-mqtt"
[11]: https://uptrace.dev/blog/opentelemetry-compatible-platforms?utm_source=chatgpt.com "12 OpenTelemetry-Compatible Platforms You Should ..."
[12]: https://stackoverflow.com/questions/63001954/python-apscheduler-how-does-asyncioscheduler-work?utm_source=chatgpt.com "Python APScheduler - How does AsyncIOScheduler work?"
[13]: https://opentelemetry.io/docs/languages/python/exporters/?utm_source=chatgpt.com "Exporters"
[14]: https://opentelemetry.io/docs/specs/otel/metrics/sdk_exporters/prometheus/?utm_source=chatgpt.com "Metrics Exporter - Prometheus"
[15]: https://betterstack.com/community/guides/observability/otel-metrics-python/?utm_source=chatgpt.com "Implementing OpenTelemetry Metrics in Python Apps"
[16]: https://pypi.org/project/APScheduler/?utm_source=chatgpt.com "APScheduler"
[17]: https://github.com/agronholm/apscheduler?utm_source=chatgpt.com "agronholm/apscheduler: Task scheduling library for Python"
[18]: https://github.com/agronholm/apscheduler/releases?utm_source=chatgpt.com "Releases · agronholm/apscheduler"
[19]: https://apscheduler.readthedocs.io/en/master/versionhistory.html?utm_source=chatgpt.com "Version history — APScheduler documentation - Read the Docs"
[20]: https://pypi.org/project/zeroconf/?utm_source=chatgpt.com "zeroconf"
[21]: https://github.com/python-zeroconf/python-zeroconf?utm_source=chatgpt.com "A pure python implementation of multicast DNS service ..."
[22]: https://pypi.org/project/zeroconf/0.39.1/?utm_source=chatgpt.com "zeroconf"
[23]: https://www.hivemq.com/blog/mqtt-essentials-part-9-last-will-and-testament/?utm_source=chatgpt.com "What is MQTT Last Will and Testament (LWT)?"
[24]: https://www.emqx.com/en/blog/use-of-mqtt-will-message?utm_source=chatgpt.com "MQTT Will Message (Last Will & Testament) Explained and ..."
[25]: https://thingsboard.io/docs/mqtt-broker/user-guide/last-will/?utm_source=chatgpt.com "Last Will and Testament | MQTT Broker"
[26]: https://redis.io/learn/develop/node/nodecrashcourse/advancedstreams?utm_source=chatgpt.com "Parallel Processing Checkins with Consumer Groups"
[27]: https://www.infoworld.com/article/2257824/how-to-use-consumer-groups-in-redis-streams.html?utm_source=chatgpt.com "How to use consumer groups in Redis Streams"
[28]: https://github.com/sureshdsk/redis-stream-python-example/blob/main/consumergroup.py?utm_source=chatgpt.com "redis-stream-python-example/consumergroup.py at main"
