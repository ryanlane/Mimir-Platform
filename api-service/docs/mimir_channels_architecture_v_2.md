# Mimir ChThis d## 1. What's new since v2.0

- **UI‑capable Channels**: A Channel may ship a web UI bundle (Web Component by default; iframe as a stricter sandbox option).
- **Manifest Extension**: `config.json` gains a `ui` section (declarative elements, routes, slots, assets, integrity, and render mode).
- **Host Plugin Runtime**: A small, framework‑agnostic loader in React dynamically fetches manifests and mounts Channel UI.
- **Settings Persistence**: Robust JSON column storage with proper SQLAlchemy change detection and type conversion.
- **Zip Upload Pipeline**: Admins can upload a Channel as a zip from the Console → FastAPI validates, extracts, optionally installs deps, and hot‑registers it.
- **Security Hardening**: CSP, SRI, per‑Channel token scopes, safe extraction, dependency policy, error isolation. updates the v2.0 Channel architecture to enable **optional, self‑contained UI** for Channels ("plugins") while keeping the core guarantee: **a Channel works when its folder is copied into **``** on the API service.** It also introduces **robust settings persistence** and a **secure zip‑upload flow** so Channels can be installed from the React Console without SSH or filesystem access.nnels Architecture v2.4 — Self‑Contained UI + Settings Persistence

**Version:** 2.4\
**Date:** August 20, 2025\
**Status:** Architecture Specification

---

## 0. Purpose

This document updates the v2.0 Channel architecture to enable **optional, self‑contained UI** for Channels (“plugins”) while keeping the core guarantee: **a Channel works when its folder is copied into **``** on the API service.** It also introduces a **secure zip‑upload flow** so Channels can be installed from the React Console without SSH or filesystem access.

> Non‑goal: Third‑party code must not modify or rebuild the React host app. The React app **discovers and loads** Channel UI at runtime via a generic loader.

---

## 1. What’s new since v2.0

- **UI‑capable Channels**: A Channel may ship a web UI bundle (Web Component by default; iframe as a stricter sandbox option).
- **Manifest Extension**: `config.json` gains a `ui` section (declarative elements, routes, slots, assets, integrity, and render mode).
- **Host Plugin Runtime**: A small, framework‑agnostic loader in React dynamically fetches manifests and mounts Channel UI.
- **Zip Upload Pipeline**: Admins can upload a Channel as a zip from the Console → FastAPI validates, extracts, optionally installs deps, and hot‑registers it.
- **Security Hardening**: CSP, SRI, per‑Channel token scopes, safe extraction, dependency policy, error isolation.

Backwards compatibility: Pure server‑side Channels (no UI) continue to work unchanged.

---

## 2. Terms

- **Channel**: A plugin hosted by the FastAPI service under `channels/<channelId>/`.
- **Manifest**: The Channel’s `config.json`, extended to describe UI bundles.
- **Slot**: A named mount point in the host UI (e.g., `dashboard.topRight`).
- **Render Mode**:
  - `element` → Web Component (Custom Element + Shadow DOM)
  - `iframe` → isolated iframe micro‑frontend

---

## 3. Directory Layout (unchanged with optional UI)

```
channels/
└── weather_channel/
    ├── config.json              # Manifest (extended in v2.4)
    ├── channel.py               # Channel implementation (server‑side)
    ├── placeholder.jpg          # Fallback media (optional)
    ├── current.jpg              # Example generated media (optional)
    ├── requirements.txt         # Py deps (optional; see §11)
    ├── ui/                      # Optional: self‑contained UI bundle(s)
    │   ├── index.esm.js         # Web Component entry (ESM)
    │   ├── page.esm.js          # Optional page‑level element (ESM)
    │   ├── styles.css           # Optional scoped styles
    │   └── assets/…             # Images/fonts used by the UI
    └── assets/                  # Server assets (served by API)
```

> **Keep‑it‑simple contract:** Copying this folder into `channels/` is sufficient. If present, `ui/` files are automatically served and discoverable via the manifest.

---

## 4. Manifest (config.json) — v2.4 extension

### 4.1 Base (from v2.0)

Retain existing fields (`name`, `description`, `version`, `update_schedule`, `settings`, etc.).

### 4.2 New fields

```jsonc
{
  "schemaVersion": "2.4",
  "id": "com.example.weather",           // optional if folder name is canonical id
  "permissions": ["read:weather"],      // server-enforced scopes
  "ui": [
    {
      "element": "x-weather-card",      // custom element tag
      "moduleUrl": "/api/channels/com.example.weather/ui/index.esm.js",
      "styleUrl": "/api/channels/com.example.weather/ui/styles.css",
      "slots": ["dashboard.topRight"],
      "propsSchema": { "$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": { "user": {"type":"object"} } },
      "renderMode": "element",           // "element" | "iframe"
      "integrity": {                      // optional SRI hashes
        "module": "sha384-…",
        "style": "sha384-…"
      }
    },
    {
      "route": "/weather",              // optional page route
      "element": "x-weather-page",
      "moduleUrl": "/api/channels/com.example.weather/ui/page.esm.js",
      "nav": { "label": "Weather", "icon": "cloud" },
      "renderMode": "element"
    }
  ],
  "assets": [ { "name": "logo", "url": "/api/channels/com.example.weather/assets/logo.svg" } ],
  "settings": {
    "defaults": {
      "poll_interval": 900,
      "location": "Seattle"
    },
    "schema": {
      "type": "object",
      "properties": {
        "poll_interval": { "type": "integer", "minimum": 300 },
        "location": { "type": "string" }
      }
    }
  }
}
```

**Notes**

- `moduleUrl`/`styleUrl` are served by FastAPI under a **namespaced static mount** (see §6).
- `renderMode:"iframe"` yields an isolated render (see §8.2) using a `src` derived from `moduleUrl` (or a dedicated `iframeUrl`).
- `propsSchema` lets the host validate props sent to elements.

---

## 5. Server Runtime (FastAPI)

### 5.1 Discovery (startup & hot‑reload)

- Scan `channels/` for directories containing `config.json`.
- Load `channel.py` via `importlib` and instantiate a class implementing the Channel protocol.
- Mount static file apps for `ui/` and `assets/` to:
  - `/api/channels/<id>/ui/*`
  - `/api/channels/<id>/assets/*`
- Compute/verify SRI (if configured) and attach to the in‑memory manifest served to clients.

### 5.2 Public endpoints

```
GET  /api/channels                          # list discovered channels (metadata + status)
GET  /api/channels/manifest                 # array of UI-aware manifests for the React loader
GET  /api/channels/{id}/config              # raw manifest/config
GET  /api/channels/{id}/settings            # current settings (per-tenant) with default merging
POST /api/channels/{id}/settings            # validate + persist settings with type conversion
POST /api/channels/{id}/test                # run a safe test action (e.g., generate sample)
POST /api/channels/upload                   # zip upload (see §10)
```

### 5.3 Channel protocol (summary)

```python
class Channel(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def config(self) -> dict: ...
    async def render_image(self, resolution: tuple[int,int], orientation: str, settings: dict) -> str: ...
    async def validate_settings(self, settings: dict) -> dict[str,str]: ...
    def get_status(self) -> dict: ...
    def get_router(self) -> APIRouter | None: ...  # optional, for channel-specific APIs
```

> Optional `get_router()` lets a Channel expose internal APIs under `/api/channels/{id}/…`, consumed by its UI.

---

## 6. Static Serving & Integrity

- For each Channel, mount static dirs:
  - `ui/ → /api/channels/{id}/ui` (ESM, CSS)\*\*
  - `assets/ → /api/channels/{id}/assets`
- Compute SHA‑384 SRI for each JS/CSS file during discovery (or accept `integrity` provided in the manifest). Attach to `/api/channels/manifest` responses. Reject mismatches if `strict_integrity` is enabled.
- Set strong cache headers (immutable) for versioned assets; short cache for `manifest`.

---

## 7. React Host — Plugin Runtime

A thin runtime in the host app loads and mounts Channel UIs without rebuilds.

### 7.1 Loader flow

1. Fetch `/api/channels/manifest` on app start.
2. Filter by compatibility and permissions.
3. For each `ui` entry:
   - If `renderMode:"element"`: inject `<link rel="stylesheet">` (optional), then `await import(/* webpackIgnore: true */ moduleUrl)`.
   - If `renderMode:"iframe"`: no scripts injected; render an iframe later.
4. Register available `slots` and `routes`.

### 7.2 Slot component

```tsx
function PluginSlot({ name, hostProps }: { name: string; hostProps: any }) {
  const entries = useMemo(() => selectUiEntriesForSlot(name), [name]);
  return (
    <>
      {entries.map((u, i) => u.renderMode === 'element'
        ? <u.element key={i} data-hostprops={JSON.stringify(hostProps)} />
        : <iframe key={i} src={deriveIframeUrl(u)} sandbox="allow-scripts allow-same-origin" />)}
    </>
  );
}
```

### 7.3 Route integration

- A single catch‑all `PluginRoute` renders the declared `element` for any `ui[].route`.
- Navigation items come from `ui[].nav`.

### 7.4 Host ↔ UI communication

- **Web Components**: pass JSON props via an attribute (e.g., `data-hostprops`), update through a small host API or property setters, and receive events via `CustomEvent`.
- **Iframe**: communicate via `postMessage` using a minimal RPC (get user, theme, token, navigate).

---

## 8. UI Delivery Modes

### 8.1 Web Components (default)

- Pros: framework‑agnostic, lightweight, Shadow DOM isolation, native in all evergreen browsers.
- Usage: the Channel’s ESM defines and registers custom elements. Example entry (`ui/index.esm.js`):

```js
class WeatherCard extends HTMLElement {
  async connectedCallback(){
    const props = JSON.parse(this.getAttribute('data-hostprops')||'{}');
    const res = await fetch(`/api/channels/com.example.weather/forecast?city=${encodeURIComponent(props.user?.city||'Seattle')}`, {credentials: 'include'});
    const data = await res.json();
    this.attachShadow({mode:'open'});
    this.shadowRoot.innerHTML = `<div>${data.city}: ${data.tempC} °C</div>`;
  }
}
customElements.define('x-weather-card', WeatherCard);
```

### 8.2 Iframe micro‑frontend (optional)

- Pros: strongest isolation; easier CSP; Channel can use any stack.
- Cons: heavier; message‑based API; theming is indirect.
- Manifest may specify `renderMode:"iframe"` and optionally `iframeUrl` if distinct from `moduleUrl`.

**Recommendation**: default to Web Components; require iframe for untrusted vendors or advanced isolation needs.

---

## 9. Auth, Permissions, and Tokens

- Channels declare `permissions` in the manifest.
- The host exchanges the user session for a **Channel‑scoped, short‑lived token** (e.g., at `/api/channels/{id}/token`) that the UI uses when calling Channel endpoints.
- Enforce scopes server‑side on `/api/channels/{id}/…` routes. Apply per‑Channel rate limits.

---

## 10. Zip Upload Flow (React → FastAPI → channels/)

### 10.1 UX

- Admin navigates to **Add Channel** → uploads a `.zip` produced by the Channel author.
- Console shows a **dry‑run validation** (manifest parsed, integrity computed, deps analyzed, conflicts detected).
- If accepted, server installs the Channel and **hot‑registers** it without a host restart (where supported).

### 10.2 Server endpoint

```
POST /api/channels/upload (multipart/form-data)
  file: channel.zip
  options: { install_dependencies?: boolean, strict_integrity?: boolean }
```

### 10.3 Validation & extraction (safe‑by‑default)

1. Check size limits and MIME.
2. Open zip and **reject Zip Slip** paths (`..`, absolute paths, drive letters). Only allow a single top‑level directory.
3. Require `config.json` and `channel.py`; `ui/` optional.
4. Parse manifest; verify `schemaVersion` ∈ supported range.
5. If `integrity` present, compute SRI over declared files and verify.
6. Extract to a temporary dir → optionally install deps (see §11) → atomically move to `channels/<id>/`.
7. Register static mounts and instance; update in‑memory manifest registry.

**Zip‑slip guard (sketch):**

```python
for m in z.infolist():
    dest = (tmp_dir / m.filename).resolve()
    if not str(dest).startswith(str(tmp_dir.resolve())):
        raise HTTPException(400, 'unsafe path in zip')
    z.extract(m, tmp_dir)
```

### 10.4 Rollback

- If any step fails, delete temp dir; if activation fails after move, move the folder to `channels/.quarantine/<id>-<ts>/`.

---

## 11. Dependencies & Isolation (Python)

- **Default**: discourage heavy deps; prefer pure‑Python and the platform SDK.
- **Policy**: allowlist common libraries; block native extensions unless explicitly approved.
- **Per‑Channel venv (optional)**: If `requirements.txt` exists and `install_dependencies=true`, create `venv/channels/<id>/` and install with `pip --no-build-isolation --only-binary :all:` where possible.
- Record a **lockfile** snapshot used for repeatable installs.
- Channels import their deps via their router or background tasks; document how `sys.path` is extended per instance when needed.

---

## 12. Security & Compliance

- **CSP**: Restrictive defaults. For Web Components, `script-src` self + hashes; for iframes, `sandbox` plus tight `allow-*`.
- **SRI**: Verify JS/CSS integrity when provided; optionally enforce `strict_integrity`.
- **Quotas & Rate Limits**: per‑Channel on server endpoints.
- **Error Isolation**: loader catches and reports per‑Channel load errors; UI degrades gracefully.
- **Telemetry**: per‑Channel load times, failures, API error rates; surfaced in Admin Console.

---

## 13. Observability & Health

- `/api/channels` returns status derived from `get_status()` (last update, last error, etc.).
- Add `/api/channels/{id}/health` (optional) for Channel‑specific health checks.
- Emit structured logs with `channelId` and `tenantId` correlation IDs.

---

## 14. Developer Experience (DX)

- **Starter kits**: Python (FastAPI) + UI (Web Component template) + example manifest.
- **Local dev**: dev server that serves a synthetic `/api/channels/manifest` and hot‑reloads `ui/*.esm.js`.
- **Schema validation**: publish JSON Schemas for `config.json` v2.4 and host‑provided props.
- **Testing**: CLI to run compatibility checks (API version, permissions, schema).

---

## 15. Migration from v2.0

- v2.0 Channels continue to function unchanged.
- To adopt UI:
  1. add `ui/` with `index.esm.js` and optional `styles.css`,
  2. extend `config.json` with `ui` array entries (slots/routes),
  3. (optional) add `get_router()` for Channel‑specific APIs.

---

## 16. Appendix A — Minimal examples

### 16.1 `config.json` (UI + page)

```json
{
  "schemaVersion": "2.4",
  "name": "Weather Display",
  "description": "Shows current weather conditions with forecast",
  "version": "1.2.0",
  "update_schedule": { "unit": "minutes", "duration": 15 },
  "permissions": ["read:weather"],
  "ui": [
    {
      "element": "x-weather-card",
      "moduleUrl": "/api/channels/weather_channel/ui/index.esm.js",
      "styleUrl": "/api/channels/weather_channel/ui/styles.css",
      "slots": ["dashboard.topRight"],
      "renderMode": "element"
    },
    {
      "route": "/weather",
      "element": "x-weather-page",
      "moduleUrl": "/api/channels/weather_channel/ui/page.esm.js",
      "nav": {"label":"Weather","icon":"cloud"},
      "renderMode": "element"
    }
  ]
}
```

### 16.2 Channel router (optional)

```python
router = APIRouter()

@router.get('/forecast')
async def forecast(city: str):
    return {"city": city, "tempC": 22}

class WeatherChannel:
    def __init__(self, channel_dir: str): ...
    def get_router(self):
        return router
```

---

## 17. Appendix B — FastAPI notes (mounts & manifest)

- Mount: `app.mount(f"/api/channels/{id}/ui", StaticFiles(directory=ui_path), name=f"{id}-ui")`
- Manifest endpoint composes per‑Channel JSON and returns an array for the React loader.

---

## 18. Risks & Mitigations

- **JS supply chain risk** → SRI + local hosting + allowlist + iframe for untrusted.
- **Python dependency conflicts** → per‑Channel venvs or strict allowlist.
- **Zip poisoning / path traversal** → strict extraction checks.
- **Plugin crashes** → per‑Channel try/catch + telemetry + fallback UI.

---

## 19. Summary

v2.4 preserves the simple installation story (copy a folder into `channels/`) while adding a safe, modern path for **rich, self‑contained Channel UIs**, **robust settings persistence**, and a **zero‑touch zip upload**. The host remains stable; Channels declare what they need, and the platform discovers, validates, and mounts them at runtime.

