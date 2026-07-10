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

"""Web Screens — browser-only displays addressed by a secret URL.

Any device with a browser becomes a display by loading /d/<token>: the page
polls for content, and the poll doubles as heartbeat and live-resolution
report. Designed for old tablets: the page is a single self-contained ES5
document (no fetch, no modules, no framework).
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import DisplayClient
from app.services.display_last_image import display_last_image_store

from ._helpers import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

POLL_SECONDS = 15
# Kick a render at most this often per display when a scene is assigned but
# no content exists yet (fresh screens shouldn't wait for the scheduler).
_KICK_INTERVAL_SECONDS = 60
_last_kick: dict[str, float] = {}


class WebDisplayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: str | None = None
    # Initial size hint only — the page reports its real viewport on load.
    width: int | None = Field(None, ge=64, le=7680)
    height: int | None = Field(None, ge=64, le=4320)


@router.post("/web", tags=["web-displays"])
async def create_web_display(body: WebDisplayCreate, db: Session = Depends(get_db)):
    """Create a Web Screen and return its unique display URL."""
    display_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(24)
    w = body.width or 1280
    h = body.height or 800
    now = datetime.now(timezone.utc)

    display = DisplayClient(
        id=display_id,
        name=body.name,
        location=body.location,
        display_type="registered",
        discovery_method="web",
        auto_discovered=False,
        hostname=f"web-{display_id[:8]}",
        width=w,
        height=h,
        orientation="square" if w == h else ("portrait" if h > w else "landscape"),
        # Until the page feature-detects otherwise: old browsers can't play
        # animated WebP, and the animated→static downgrade handles the rest.
        supports_animation=False,
        web_token=token,
        is_online=False,
        last_seen=None,
        created_at=now,
    )
    db.add(display)
    db.commit()

    return {
        "ok": True,
        "display_id": display_id,
        "name": body.name,
        "web_path": f"/d/{token}",
        "discovery_method": "web",
    }


def _display_by_token(db: Session, token: str) -> DisplayClient:
    display = (
        db.query(DisplayClient)
        .filter(DisplayClient.web_token == token, DisplayClient.discovery_method == "web")
        .first()
    )
    if not display:
        raise HTTPException(status_code=404, detail="Unknown display")
    return display


def _same_origin_path(url: str | None) -> str | None:
    """Reduce our own absolute media URLs to a path so the page fetches
    same-origin — works identically via the API port and the web proxy,
    and sidesteps public-host reachability entirely."""
    if not url:
        return None
    try:
        parts = urlsplit(url)
        if parts.path.startswith("/media/") or parts.path.startswith("/channels/"):
            return parts.path + (f"?{parts.query}" if parts.query else "")
    except ValueError:
        pass
    return url


def _trigger_refresh(scene_id: str, device_id: str, reason: str) -> None:
    async def _refresh() -> None:
        try:
            from app.services.scene_refresh_service import scene_refresh_service
            await scene_refresh_service.refresh_scene(
                scene_id, trigger_reason=reason, force=True, target_devices=[device_id],
            )
        except Exception as e:  # noqa: BLE001 — background kick must not surface
            logger.warning("Web display refresh failed for %s: %s", device_id, e)
    try:
        asyncio.get_running_loop().create_task(_refresh())
    except RuntimeError:  # pragma: no cover
        pass


@router.get("/web/{token}/current", tags=["web-displays"])
async def web_display_current(
    token: str,
    w: int | None = None,
    h: int | None = None,
    anim: int | None = None,
    db: Session = Depends(get_db),
):
    """Content poll — also heartbeat and live-resolution report.

    Returns the current image (as a same-origin path when possible) plus a
    content hash; the page only swaps its <img> when the hash changes.
    """
    display = _display_by_token(db, token)
    device_id = str(display.hostname)

    display.is_online = True
    display.last_seen = datetime.now(timezone.utc)

    res_changed = False
    if w and h and 64 <= w <= 7680 and 64 <= h <= 4320:
        if (display.width, display.height) != (w, h):
            logger.info("Web display %s resolution changed: %sx%s -> %sx%s",
                        device_id, display.width, display.height, w, h)
            display.width, display.height = w, h
            display.orientation = "square" if w == h else ("portrait" if h > w else "landscape")
            res_changed = True
    if anim is not None:
        val = bool(anim)
        if bool(display.supports_animation) != val:
            display.supports_animation = val
    db.commit()

    scene_id = str(display.assigned_scene_id) if display.assigned_scene_id else None
    record = display_last_image_store.get(device_id)

    if scene_id and (res_changed or record is None):
        # Stale-size content or a brand-new screen: kick a targeted render
        # (rate-limited so an empty scene can't cause a refresh storm).
        now = time.monotonic()
        if res_changed or now - _last_kick.get(device_id, 0) > _KICK_INTERVAL_SECONDS:
            _last_kick[device_id] = now
            _trigger_refresh(scene_id, device_id,
                             "resolution_change" if res_changed else "web_display_initial")

    image_url = _same_origin_path(record.image_url) if record else None
    return {
        "image": image_url,
        "version": record.assignment_id if record else None,
        "scene_assigned": scene_id is not None,
        "poll_seconds": POLL_SECONDS,
    }


# ── The display page (served at /d/{token}, outside /api) ───────────────────

page_router = APIRouter()

_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>Mimir Display</title>
<style>
  html, body { margin: 0; padding: 0; width: 100%; height: 100%;
    background: #000; overflow: hidden; }
  .layer { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
  img.content { object-fit: contain; opacity: 0;
    -webkit-transition: opacity 0.4s; transition: opacity 0.4s; }
  img.content.visible { opacity: 1; }
  #status { color: #9aa; font: 16px/1.5 sans-serif; text-align: center;
    position: absolute; left: 0; right: 0; top: 45%; }
  #hint { color: #567; font: 12px/1.5 sans-serif; text-align: center;
    position: absolute; left: 0; right: 0; bottom: 12px; }
</style>
</head>
<body>
<img id="imgA" class="layer content" alt="">
<img id="imgB" class="layer content" alt="">
<div id="status">Connecting&hellip;</div>
<div id="hint">Tap for fullscreen</div>
<script>
(function () {
  'use strict';
  var TOKEN = document.location.pathname.split('/').pop();
  var API = '/api/displays/web/' + TOKEN + '/current';
  var pollSeconds = 15;
  var version = null;
  var front = document.getElementById('imgA');
  var back = document.getElementById('imgB');
  var statusEl = document.getElementById('status');
  var hintEl = document.getElementById('hint');
  var animSupport = 0;
  var timer = null;

  function setStatus(text) {
    statusEl.style.display = text ? 'block' : 'none';
    if (text) statusEl.innerHTML = text;
  }

  // Feature-detect *animated* WebP (old tablets: no). 2-frame probe decodes
  // to natural height 1 only when the ANIM chunk is understood.
  (function detectAnimWebp() {
    var probe = new Image();
    probe.onload = function () { animSupport = (probe.height === 1) ? 1 : 0; };
    probe.onerror = function () { animSupport = 0; };
    probe.src = 'data:image/webp;base64,UklGRlIAAABXRUJQVlA4WAoAAAASAAAAAAAAAAAAQU5JTQYAAAD/////AABBTk1GJgAAAAAAAAAAAAAAAAAAAGQAAABWUDhMDQAAAC8AAAAQBxAREYiI/gcA';
  })();

  function currentSize() {
    var dpr = window.devicePixelRatio || 1;
    return {
      w: Math.max(64, Math.round((window.innerWidth || 640) * dpr)),
      h: Math.max(64, Math.round((window.innerHeight || 480) * dpr))
    };
  }

  function swapTo(url) {
    back.onload = function () {
      back.className = 'layer content visible';
      front.className = 'layer content';
      var t = front; front = back; back = t;
      setStatus('');
    };
    back.onerror = function () {
      setStatus('Could not load content');
    };
    back.src = url;
  }

  function poll() {
    var size = currentSize();
    var xhr = new XMLHttpRequest();
    var url = API + '?w=' + size.w + '&h=' + size.h + '&anim=' + animSupport;
    xhr.open('GET', url, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      if (xhr.status !== 200) {
        setStatus(xhr.status === 404 ? 'This display link is no longer valid'
                                     : 'Reconnecting&hellip;');
        schedule();
        return;
      }
      try {
        var data = JSON.parse(xhr.responseText);
        pollSeconds = data.poll_seconds || 15;
        if (!data.scene_assigned) {
          setStatus('No program assigned to this screen yet');
        } else if (!data.image) {
          setStatus('Preparing content&hellip;');
        } else if (data.version !== version) {
          version = data.version;
          swapTo(data.image);
        }
      } catch (e) {
        setStatus('Reconnecting&hellip;');
      }
      schedule();
    };
    xhr.send();
  }

  function schedule() {
    if (timer) clearTimeout(timer);
    timer = setTimeout(poll, pollSeconds * 1000);
  }

  // Immediate re-poll (and thus size report) when rotated/resized/re-shown.
  var resizeTimer = null;
  function onResize() {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(poll, 800);
  }
  if (window.addEventListener) {
    window.addEventListener('resize', onResize, false);
    window.addEventListener('orientationchange', onResize, false);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) poll();
    }, false);
    document.addEventListener('click', function () {
      hintEl.style.display = 'none';
      var el = document.documentElement;
      var fs = el.requestFullscreen || el.webkitRequestFullscreen || el.mozRequestFullScreen;
      if (fs) { try { fs.call(el); } catch (e) { /* older browsers */ } }
    }, false);
  }

  poll();
})();
</script>
</body>
</html>
"""


@page_router.get("/d/{token}", include_in_schema=False)
async def web_display_page(token: str, db: Session = Depends(get_db)):
    """The display page. Token is validated so a bad URL 404s immediately."""
    from fastapi.responses import HTMLResponse
    _display_by_token(db, token)
    return HTMLResponse(content=_PAGE, headers={"Cache-Control": "no-cache"})
