# Image Request Dimension & Orientation Handling

This document explains how display resolution and orientation propagate from the scheduler / scene refresh pipeline into a channel plugin (example: `com.spotify.status`) and why fallback defaults (e.g. 800x480) may appear.

## Overview

Two primary server-side paths invoke `plugin.instance.request_image(request_data)`:

1. Scheduler worker helper: `SchedulerWorker._request_channel_image`
2. Scene refresh service: `SceneRefreshService.refresh_scene`

Both construct a `request_data` dict passed directly to the channel plugin. The channel (e.g. Spotify Status Channel) then decides final width / height and layout.

## Channel Expectations

Channels (like `SpotifyStatusChannel`) look for dimensions in this order:

1. `options.width` / `options.height`
2. `settings.resolution` → two element sequence `[width, height]`
3. Internal fallback defaults (currently `800x480` in the Spotify channel implementation)

A special orientation hint of `"square"` triggers a harmonization: if `width != height`, both are set to the smaller side before rendering.

## Path 1: Scheduler Worker (`_request_channel_image`)

Build logic (simplified):

```python
res = resolution if (resolution and len(resolution) == 2) else [800, 600]
orient = orientation or "landscape"
request_data = {
  "settings": {
    "resolution": res,
    "orientation": orient,
    "distribution": "new",
  },
  "options": {
    "width": res[0],
    "height": res[1],
    "layout": ("auto" if orient != "square" else "auto"),
  },
}
```

Characteristics:
- Supplies *both* `settings.resolution` and `options.width/height` (robust for all channels).
- Fallback if caller does not supply `resolution`: `[800,600]` (note: not the channel's 800x480 default).
- Orientation only influences layout via aspect ratio when `layout="auto"`.

## Path 2: Scene Refresh Service (`refresh_scene`)

Inside the per-(width,height,orientation) group loop:

```python
request_data = {
  "settings": {
    "resolution": [w, h],
    "orientation": orientation,
    "distribution": "new",
  }
}
# (No options.width/height currently added.)
```

Characteristics:
- Only supplies `settings.resolution` (which is sufficient for the Spotify channel).
- Width / height values originate from collected displays (mDNS discovery + DB records). Defaults if missing:
  - mDNS parsing fallback: `(800, 600)`
  - DB fallback: `width or 800`, `height or 600`

## Where 800x480 Comes From

The 800x480 size is **not** emitted by either server-side builder. It is the *channel's own* internal fallback used only when neither `options.width/height` nor a valid `settings.resolution` was present. Therefore, seeing 800x480 indicates the call path that reached the channel omitted both dimension sources (e.g. direct POST without a body or a stripped/invalid payload).

## Layout Resolution in the Channel

Within the channel (Spotify example):
- Layout selection: if `options.layout == "auto"`, aspect ratio drives classification:
  - `ar >= 1.2` → landscape
  - `ar <= 0.83` → portrait
  - otherwise → square
- Square layout (`layout="square"`) produces album-art-only output (no text).
- A provided `orientation="square"` only **forces dimensions to be square**; it does **not** enforce the square layout (layout still depends on `options.layout` / auto logic).

## Common Pitfalls

| Issue | Cause | Result |
|-------|-------|--------|
| Channel returns 800x480 | Missing both `options.width/height` and `settings.resolution` | Channel default applied |
| Unexpected landscape vs portrait | `layout="auto"` and aspect ratio threshold surprised caller | Different text placement |
| Square art without text missing | Used `layout="landscape"` + `orientation="square"` | Still landscape composite, not full-bleed art |
| Text cramped on large display | Not increasing `text_scale` for higher resolutions | Small fonts relative to canvas |

## Recommended Improvements (Optional)

1. Add an `options` block to `SceneRefreshService` requests for parity:
   ```python
   request_data["options"] = {"width": w, "height": h, "layout": "auto"}
   ```
2. Add diagnostic logging in the channel when applying its fallback default dimensions.
3. Introduce environment-driven default resolution (e.g. `SPOTIFY_STATUS_DEFAULT_WIDTH/HEIGHT`) to override 800x480 for direct/manual calls.
4. Add an integration test asserting that a scene with a 1920x1080 display triggers a 1920x1080 image generation.

## Quick Debug Checklist

- Confirm the JSON payload reaching the channel (add a `logger.debug` before `request_image`).
- Verify `settings.resolution` presence in the log.
- If 800x480 appears, capture raw request to the channel endpoint (could be a different caller).

## Example Explicit Request

```json
{
  "settings": {"resolution": [1920, 1080], "orientation": "landscape"},
  "options": {"width": 1920, "height": 1080, "layout": "landscape", "text_scale": 1.0}
}
```

## Summary

- Scheduler helper: supplies both settings and options (safer).
- Scene refresh service: supplies only settings but still adequate.
- 800x480 implies a dimension-less request path hit the channel.
- Adding consistency (options everywhere) plus logging eliminates ambiguity.

Use this document as a reference when adding new channels or debugging display size mismatches.
