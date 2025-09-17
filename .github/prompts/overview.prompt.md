---
mode: ask
---

# Mimir System Overview

This document describes the end-to-end flow of how **Channels**, **Scenes**, **Displays**, and the **API Service** interact in the Mimir ecosystem.

---

## Key Concepts

* **Channels (plugins):** Responsible for generating images. Each channel implements its own logic and can produce images either as URLs or as raw bytes.
* **Scenes:** Define *when* images are requested from a channel. Each scene is tied to a specific channel and an interval (days/hours/minutes).
* **Displays:** Remote clients that present images (custom hardware frames, browsers, TVs, etc.).
* **API Service:** Orchestrates discovery, registration, scene scheduling, image requests, and delivery to displays.
* **MQTT Broker:** Lightweight messaging backbone for discovery, control, and image delivery signals.

---

## End-to-End Lifecycle

### 1. Display Discovery & Registration

1. Displays advertise via **mDNS** (`_mimir-display._tcp.local`).
2. API detects and sends an MQTT **probe**:

   ```json
   Topic: mimir/displays/<clientId>/probe
   { "requestId": "uuid-1" }
   ```
3. Display replies with description:

   ```json
   Topic: mimir/api/registrations
   {
     "requestId": "uuid-1",
     "displayId": "disp-42",
     "name": "Kitchen Frame",
     "resolution": {"width": 800, "height": 480},
     "orientation": "landscape",
     "colorModes": ["mono", "gbw"],
     "capabilities": {"acceptsUrl": true, "acceptsBinary": false},
     "firmware": "1.3.0"
   }
   ```
4. API registers the display and begins health checks (pings/pongs).

---

### 2. Scene Assignment

1. Create a scene with channel + interval:

   ```json
   {
     "sceneId": "scene-7",
     "channel": "photo_frame",
     "interval": {"unit": "minutes", "value": 15},
     "channelConfig": { "album": "coastal-sunsets", "shuffle": true }
   }
   ```
2. Assign the scene to a display:

   ```json
   { "displayId": "disp-42", "sceneId": "scene-7" }
   ```
3. API stores the assignment and schedules image requests.

---

### 3. Image Production Workflow

1. Scheduler fires based on scene interval.
2. API requests image from channel:

   ```python
   channel.render_image(channelConfig, displayContext)
   ```

   Returns:

   ```json
   {
     "contentType": "image/png",
     "delivery": {"type": "url", "url": "https://.../scene-7/disp-42.png"},
     "metadata": {"caption": "Sunset #12"}
   }
   ```
3. API notifies display:

   * **Preferred (URL pull):**

     ```json
     Topic: mimir/displays/disp-42/set-image
     {
       "sceneId": "scene-7",
       "image": {
         "type": "url",
         "url": "https://.../scene-7/disp-42.png",
         "contentType": "image/png",
         "etag": "abc123"
       }
     }
     ```
   * **Fallback (binary push):** Bytes over MQTT.
4. Display fetches or accepts image, renders it, and acknowledges:

   ```json
   Topic: mimir/api/acks
   {"displayId": "disp-42", "sceneId": "scene-7", "status": "rendered", "etag": "abc123"}
   ```

---

### 4. Ongoing Operations

* **Heartbeats:** `ping` / `pong` over MQTT.
* **Status updates:** Displays send telemetry (battery, uptime, etc.).
* **Assignment changes:** API re-schedules intervals.
* **Resolution/orientation updates:** Display sends update → API adjusts context.

---

## Interfaces

### Channel Plugin

```python
class ChannelPlugin(Protocol):
    name: str
    def render_image(self, channel_config: dict, display_context: dict) -> dict: ...
```

### Scene Model

```json
{
  "sceneId": "scene-7",
  "channel": "photo_frame",
  "interval": {"unit":"minutes","value":15},
  "channelConfig": {"album":"coastal-sunsets","shuffle":true}
}
```

### Display Model

```json
{
  "displayId": "disp-42",
  "name": "Kitchen Frame",
  "resolution": {"width":800,"height":480},
  "orientation": "landscape",
  "colorModes": ["mono","gbw"],
  "capabilities": {"acceptsUrl":true,"acceptsBinary":false},
  "status": {"online":true, "lastSeen":"2025-09-03T16:10:00Z"}
}
```

---

## MQTT Topics

* `mimir/displays/<displayId>/probe`
* `mimir/<device_id>/cmd`
* `mimir/displays/<displayId>/set-image`
* `mimir/displays/<displayId>/set-image-bytes`
* `mimir/api/acks`
* `mimir/displays/<displayId>/ping` / `pong`

example scene assignment command message:

```json
mimir/<device_id>/cmd

{
  "type": "set_scene",
  "assignment_id": "test-cli-1234",
  "timestamp": "2025-09-05T20:00:00Z"
}


```

clear scene assignment command message:

```json
mimir/<device_id>/cmd

{
  "type": "clear_scene",
  "assignment_id": "test-cli-1234",
  "timestamp": "2025-09-05T20:00:00Z"
}

```

---

## Reliability & Security

* Use **QoS 1** for control messages, **QoS 0** for heartbeats.
* **Retained messages** for last image command.
* **Signed URLs** for HTTP fetches.
* **Backoff + retry** on failures.
* Track **ACKs** to ensure delivery.

---

## Sequence Diagram (simplified)

```
Display --(mDNS)--> API
API --(MQTT probe)--> Display
Display --(MQTT registration)--> API
API --(assign scene)--> DB
Scheduler --(tick)--> API
API --(render request)--> Channel
Channel --(image url/bytes)--> API
API --(set-image msg)--> Display
Display --(fetch/render)--> Display
Display --(ack)--> API
```
