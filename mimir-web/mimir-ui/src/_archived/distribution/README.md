# Archived Distribution Dashboard

This folder contains the deprecated Distribution page (`Distribution.js`) that previously exposed
real-time and aggregate metrics for the Redis-backed content distribution / leasing system.

## Why Archived
- The main dashboard now surfaces a minimal subset of distribution metrics (queues, leases, system & Redis status).
- The full page was not linked in navigation and had overlapping responsibilities with the Scenes & Displays pages.
- WebSocket performance events are either low-value for day‑to‑day ops or can be reintroduced later in a leaner form.

## What Was Removed / Simplified
- Per‑scene action buttons (refresh content, reset distribution) – consider implementing targeted admin actions elsewhere if still required.
- Full display & scene lists (replaced by existing Dashboard / Displays / Scenes pages).
- Verbose logging and secondary status panels.

## How to Restore
If you need deeper distribution insights again:
1. Start from the last revision of `Distribution.js` prior to archival.
2. Decide which metrics are still actionable.
3. Rebuild as a feature‑flagged panel or integrate into an admin/debug drawer.

## Minimal Metrics Now on Dashboard
The Dashboard loads `getDistributionOverview()` (if available) every 60s and displays:
- Total Queue Items
- Active Leases
- Distribution System status
- Redis status

If the endpoint is absent, the dashboard silently omits the panel.

---
_Last updated: 2025-10-02_
