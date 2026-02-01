# Mimir Service (Docker)

This folder can run the Mimir API backend and Mimir UI frontend via Docker Compose.

## Quick start

From this directory:

- Start everything: `docker compose up -d --build`
- View logs: `docker compose logs -f`
- Stop: `docker compose down`

## Dev mode (hot reload)

This runs:

- FastAPI with `uvicorn --reload`
- React dev server (`react-scripts start`) with live file watching

From this directory:

- Start dev: `docker compose -f docker-compose.dev.yml up --build`
- Stop dev: `docker compose -f docker-compose.dev.yml down`

Optional Postgres admin UI (pgAdmin):

- Start dev + pgAdmin: `docker compose -f docker-compose.dev.yml --profile tools up --build`
- pgAdmin: http://localhost:5050 (login: `admin@mimirframe.com` / `admin`)

Dev URLs:

- UI (dev server): http://localhost:3000
- API: http://localhost:5000

## Ports

- UI: http://localhost:8080
- API: http://localhost:5000
- API health: http://localhost:5000/api/health
- Redis: localhost:6379

## Configuration

- API env defaults for Docker are in mimir-api/api-service/mimir-api.docker.env.
- For local overrides, you can create a separate env file and change `env_file` in docker-compose.yml.

## Database (Postgres)

The Docker setup uses Postgres by default (better concurrency and durability than SQLite).

- Postgres runs as `db` and is exposed on `localhost:5432`
- Default credentials (change these for anything beyond local dev):
  - DB: `mimir`
  - User: `mimir`
  - Password: `mimir`

The API automatically runs `alembic upgrade head` on startup.

### Migrating existing SQLite data

If you were previously running SQLite in Docker, you have two options:

1) **Clean start (no data migration)**
	- Bring the stack down and delete the old DB volume(s), then start up again.

2) **Migrate data with pgloader (recommended)**
	- Export the SQLite DB file from your old volume and import into Postgres using `pgloader`.
	- If you want, tell me where your SQLite DB currently lives (volume name / path) and I’ll write an exact copy-paste command sequence for your machine.

## Notes

- MQTT is disabled by default in Docker to avoid requiring a broker.
- mDNS is multicast and can be flaky/impossible from bridge networking (especially Docker Desktop/WSL2).
	For Linux, you can enable the optional host-network discovery sidecar:
	- `docker compose --profile discovery up -d --build`
	- Details: see MDNS_EDGE_DISCOVERY.md
	For Windows dev without a Linux server, run discovery on the Windows host (outside WSL):
	- Preferred: `service/mimir-discovery-node` (Node + `bonjour-service`)
	- If discovery stays at 0 devices on Windows, set `MIMIR_MDNS_INTERFACE` to your Windows LAN IP (common fix when multiple adapters exist).
	- Windows Firewall help: see WINDOWS_MDNS_FIREWALL.md
	- More background: see MDNS_EDGE_DISCOVERY.md
- Channel plugins are bind-mounted read-only from the repo into the API container.
- Dev channel linking (Developer Mode): when the API runs in Docker, the path you enter must exist inside the API container.
	In `docker-compose.dev.yml`, the repo `plugins/` folder is mounted at `/plugins`, so dev channels typically look like:
	- `/plugins/<plugin-repo>/channels/<channel_id>`
	Note: the dev compose mounts the channels directory writable so the API can persist dev-link state (`dev_channels.json`).
	Auto-reload: linked dev channels are watched for file changes and reloaded automatically. In Docker dev we default to a polling watcher
	(`DEV_WATCHER_MODE=polling`, `DEV_WATCHER_POLLING_INTERVAL=1.0`) for reliability on bind mounts.
- The web UI includes optional PWA/service-worker support, but it is disabled by default for local Docker because a stale SW can cause refreshes to show the offline page.
	To enable it intentionally, build the UI with `REACT_APP_ENABLE_PWA=true`.
