---
mode: ask
---
Define the task to achieve, including specific requirements, constraints, and success criteria.

# Core functionality of the entire project. 
Display image based content on remote displays. Displays may be custom hardware or standard screens.

## Project primary items
- **Channels:** plugins that manage creating image based content and are highly flexible and custom
- **Scenes:** handles when an image is needed to be requested from a channel.
- **Displays:** manages the presentation of images on remote screens, whether they are custom hardware or standard displays.

## API goals
- manage channels that are added to the channels/ folder by users
- manage scenes that are created by users
- manage displays that are discovered via mDNS or other service discovery protocols

## API technical requirements
- RESTful API design principles
- JSON payloads for requests and responses
- Authentication and authorization mechanisms
- WebSocket support for real-time updates
- MQTT support for lightweight messaging to displays
- Redis support for caching and message brokering

Got it—here’s a clean, end-to-end picture of how it all fits together, plus minimal payloads so you can wire it up fast.

# High-level roles

* **Channels (plugins):** Produce images on demand (fully custom logic).
* **Scenes:** Decide *when* to request a new image from a specific Channel (interval policy) and *where* it goes (assigned display).
* **Displays:** Remote clients that show images (e-ink frames, browsers, TVs, etc.).
* **API Service:** The conductor—discovers displays, registers them, schedules scene ticks, asks channels for images, delivers images to displays.
* **MQTT Broker:** Lightweight, near-real-time messaging fabric (discovery handshake, control, and delivery signals).

# Lifecycle (end-to-end)

## 1 - Display discovery & registration

1. **Display advertises via mDNS** (e.g., `_mimir-display._tcp.local` with a reachable control host/port or MQTT client ID).
2. **API detects mDNS service** and publishes a *who-are-you?* probe over MQTT:

   * Topic: `mimir/displays/<clientId>/probe`
   * Msg: `{ "requestId": "uuid-1" }`
3. **Display replies** describing itself:

   * Topic: `mimir/api/registrations`
   * Msg:

     ```json
     {
       "requestId": "uuid-1",
       "displayId": "disp-42",
       "name": "Kitchen Frame",
       "resolution": {"width": 800, "height": 480},
       "orientation": "landscape",      // "portrait" | "landscape" | "square"
       "colorModes": ["mono", "gbw"],   // optional, e.g., ["rgb"], ["mono"]
       "capabilities": {"acceptsUrl": true, "acceptsBinary": false},
       "firmware": "1.3.0"
     }
     ```
4. **API registers/updates** the Display in its DB and starts heartbeats/health tracking (e.g., `mimir/displays/<id>/ping` → `.../pong`).

## 2 - Scene assignment

1. **Create a Scene** (must reference a Channel and interval):

   ```json
   {
     "sceneId": "scene-7",
     "channel": "photo_frame",            // plugin name
     "interval": {"unit": "minutes", "value": 15},  // days | hours | minutes
     "channelConfig": { /* plugin-specific */ }
   }
   ```
2. **Assign Scene → Display**:

   ```json
   { "displayId": "disp-42", "sceneId": "scene-7" }
   ```
3. **API persists assignment** and arms a scheduler for that display/scene.

## 3 - Image production workflow (each interval tick)

1. **Scheduler fires** for `disp-42` / `scene-7`.

2. **API requests image from Channel** (Channels are local plugins exposed through a stable interface):

   * Call: `channels/<channel>/renderImage(channelConfig, displayContext)`
   * The Channel returns either:

     * **URL** to a freshly rendered image (recommended), or
     * **Binary** image bytes + MIME (fallback for fully offline displays).
   * Suggested return:

     ```json
     {
       "contentType": "image/png",
       "delivery": {
         "type": "url",
         "url": "https://api.example/mimir/media/scene-7/disp-42/1693812345.png",
         "ttlSeconds": 3600
       },
       "metadata": {"caption": "Sunset #12"}
     }
     ```
   * API stores the image in its media store (filesystem/S3-compatible), signs the URL if needed.

3. **API tells display a new image is ready**:

   * **Preferred (URL pull):**

     * Topic: `mimir/displays/disp-42/set-image`
     * Msg:

       ```json
       {
         "sceneId": "scene-7",
         "image": {
           "type": "url",
           "url": "https://api.example/mimir/media/scene-7/disp-42/1693812345.png",
           "contentType": "image/png",
           "etag": "abc123"
         }
       }
       ```
     * **Display fetches** the URL over HTTP(S), validates `content-type/etag`, caches if desired, and renders.
   * **Alternate (MQTT binary push) for constrained networks:**

     * Topic: `mimir/displays/disp-42/set-image-bytes`
     * Payload: binary frame (MQTT) with headers in a small JSON preface

       ```json
       {"sceneId":"scene-7","contentType":"image/png","etag":"abc123","chunked":false}
       ```

       (followed by bytes or chunk protocol)

4. **Display acknowledges** (optional but recommended for reliability/metrics):

   * Topic: `mimir/api/acks`
   * Msg:

     ```json
     {"displayId":"disp-42","sceneId":"scene-7","status":"rendered","etag":"abc123"}
     ```

## 4 - Ongoing operations

* **Heartbeats:** API pings; display pongs with uptime/battery/temp.
* **Health & retries:** If no ACK or heartbeat, API backs off, re-sends, or marks display degraded.
* **On assignment change:** API cancels previous timer, schedules new interval, triggers an immediate render if desired (“prime on assign”).
* **On orientation/resolution change:** display publishes an update; API re-registers and passes updated `displayContext` to Channels next tick.

# Minimal interfaces (API & Channel)

## Channel plugin interface (Python idea)

```python
class ChannelPlugin(Protocol):
    name: str  # "photo_frame"

    def render_image(
        self,
        channel_config: dict,
        display_context: dict,   # {resolution, orientation, colorModes, displayId}
    ) -> dict:
        """
        Returns {
          "contentType": "image/png" | "image/jpeg" | "image/webp",
          "delivery": {"type":"url","url": "..."} | {"type":"bytes","data": b"..."},
          "metadata": {...}
        }
        """
        ...
```

## Scene model

```json
{
  "sceneId": "scene-7",
  "channel": "photo_frame",
  "interval": {"unit":"minutes","value":15},
  "channelConfig": {
    "album": "coastal-sunsets",
    "shuffle": true
  }
}
```

## Display model

```json
{
  "displayId": "disp-42",
  "name": "Kitchen Frame",
  "resolution": {"width":800,"height":480},
  "orientation": "landscape",
  "colorModes": ["mono","gbw"],
  "capabilities": {"acceptsUrl": true, "acceptsBinary": false},
  "status": {"online": true, "lastSeen": "2025-09-03T16:10:00Z"}
}
```

# Recommended transport choices

* **Primary delivery:** URL fetch (HTTP(S)). It’s simpler, scalable, cacheable, and keeps MQTT payloads small.
* **Fallback:** MQTT binary for isolated or fully offline segments.
* **Control plane:** MQTT topics per display and shared system topics.

# Suggested MQTT topic map

* Probing: `mimir/displays/<displayId>/probe`
* Registration replies: `mimir/api/registrations`
* Heartbeat: `mimir/displays/<displayId>/ping` / `mimir/displays/<displayId>/pong`
* Image set (URL): `mimir/displays/<displayId>/set-image`
* Image set (bytes): `mimir/displays/<displayId>/set-image-bytes`
* Acks/telemetry: `mimir/api/acks`, `mimir/api/telemetry`

# Reliability & security quick hits

* **Retain** the latest `set-image` command with an ETag so late-joining displays can recover.
* **QoS 1** for control messages; **QoS 0** fine for heartbeats.
* **Signed URLs** or **mTLS** for direct fetch; keep URLs short-lived.
* **Backoff + jitter** on network errors.
* **Versioned channel outputs** (include `etag` or content hash).



