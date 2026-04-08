# Mimir Service

This folder contains the Mimir service stack.

There are two supported compose paths:

- `docker-compose.yml`: native Ubuntu server deployment with host-networked API/MQTT for real LAN hardware
- `docker-compose.wsl.yml`: WSL-friendly local stack with normal bridge networking and localhost port publishing

For physical displays on a real LAN, the default recommended deployment is:

- run API, web, Postgres, Redis, and Mosquitto in Docker on a native Ubuntu server
- run discovery natively on the Ubuntu host
- set `PUBLIC_HOST` and `MQTT_PUBLIC_HOST` to the server's real LAN address

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- [Task](https://taskfile.dev/installation/) — the task runner used for all dev and deployment commands

```bash
# Install Task (Linux / WSL)
sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin
```

Run `task` from this directory to see all available commands.

## First-time setup

```bash
cp .env.example .env        # create your local environment file
# edit .env — set PUBLIC_HOST to your server's LAN IP
task setup                  # install API + UI dependencies
```

## Ubuntu Server Quick Start

This is the default path for hardware onboarding and deployment.

1. Copy and edit the environment file:

```bash
cp .env.example .env
# Set PUBLIC_HOST=192.168.1.50 and MQTT_PUBLIC_HOST=192.168.1.50
```

2. Start the production stack:

```bash
task up:build
```

3. Run migrations (first boot only — the API also runs them automatically):

```bash
task db:migrate:prod
```

4. Run discovery natively on the host so displays can find the server via mDNS:

```bash
cd mimir-discovery/python
MIMIR_API_BASE=http://127.0.0.1:5000 ./run_local.sh
```

For the full server workflow, see [HYBRID_LINUX_DEPLOYMENT.md](HYBRID_LINUX_DEPLOYMENT.md).

## WSL Quick Start

Use this when developing from WSL/Windows and you want the stack reachable from your browser at `localhost`.

1. Copy and edit the environment file:

```bash
cp .env.example .env
# Optional for browser-only local use: leave PUBLIC_HOST and MQTT_PUBLIC_HOST blank.
```

2. Start the WSL-friendly stack:

```bash
task wsl:up:build
```

3. Check local health:

```bash
task health:wsl
```

WSL URLs:

- UI: http://localhost:8080
- API: http://localhost:5000
- API health: http://localhost:5000/api/health
- pgAdmin: http://localhost:5050

Use this stack for browser/API work. Do not treat it as the reference environment for mDNS or real-device onboarding.

## Dev mode (hot reload)

Runs FastAPI with `uvicorn --reload` and the React dev server with live file watching.

```bash
task dev            # start full dev stack
task dev:down       # stop it
task dev:reset      # wipe all volumes and start fresh (prompts for confirmation)
task dev:logs:api   # follow API logs only

# WSL local stack
task wsl:up:build   # build + start the WSL-friendly compose
task wsl:down       # stop it
task health:wsl     # curl localhost:5000 directly
```

Optional extras:

```bash
task dev:discovery  # also start the mDNS discovery sidecar (Linux/WSL only)
docker compose -f docker-compose.dev.yml --profile tools up --build  # + pgAdmin at :5050
```

Dev URLs:

- UI (dev server): http://localhost:3000
- API: http://localhost:5000

## Ports

- UI: http://localhost:8080
- API: http://localhost:5000
- API health: http://localhost:5000/api/health
- Redis: localhost:6379

## Configuration

- API env defaults for Docker are in mimir-api/mimir-api.docker.env.
- For local overrides, you can create a separate env file and change `env_file` in docker-compose.yml.
- For the recommended Ubuntu-server deployment, copy `.env.hybrid.example` to `.env` and set the server's real LAN address.
- For WSL/Windows local use, copy `.env.example` to `.env` and leave `PUBLIC_HOST` blank unless you specifically need to advertise a LAN-reachable address.

## Common tasks

```bash
# Database
task db:migrate               # run migrations in the dev API container
task db:revision -- 'add x'   # generate a new Alembic migration
task db:psql                  # open a psql shell on the dev DB

# Code quality
task api:lint
task api:format
task api:test

# Physical displays
task display:deploy -- pi@colorframe05.local   # rsync + restart
task display:logs   -- pi@colorframe05.local   # stream journald logs
task display:restart -- pi@colorframe05.local

# MQTT debugging
task mqtt:sub                 # subscribe to all mimir/# topics

# Health check
task health                   # curl the local API
task health:prod              # curl the server at PUBLIC_HOST
```

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
- `docker-compose.wsl.yml` is the intended browser-friendly local stack for WSL; it is not a substitute for native-Linux host networking.
- A dedicated Ubuntu server is the preferred deployment and validation target for external display onboarding because host-network mDNS works there.
- The recommended workflow is: develop locally, but validate all real-device onboarding on the Ubuntu server.
- For Linux, you can enable the optional host-network discovery sidecar with `docker compose --profile discovery up -d --build`, but the preferred Ubuntu path is host-native discovery. See [HYBRID_LINUX_DEPLOYMENT.md](HYBRID_LINUX_DEPLOYMENT.md).
- For Windows dev without a Linux server, run discovery on the Windows host (outside WSL).
- Preferred Windows discovery path: `service/mimir-discovery-node` (Node + `bonjour-service`).
- If discovery stays at 0 devices on Windows, set `MIMIR_MDNS_INTERFACE` to your Windows LAN IP.
- Windows Firewall help: see [WINDOWS_MDNS_FIREWALL.md](WINDOWS_MDNS_FIREWALL.md).
- More background: see [MDNS_EDGE_DISCOVERY.md](MDNS_EDGE_DISCOVERY.md).
- Channel plugins are bind-mounted read-only from the repo into the API container.
- Dev channel linking (Developer Mode): when the API runs in Docker, the path you enter must exist inside the API container.
	In `docker-compose.dev.yml`, the repo `plugins/` folder is mounted at `/plugins`, so dev channels typically look like:
	- `/plugins/<plugin-repo>/channels/<channel_id>`
	Note: the dev compose mounts the channels directory writable so the API can persist dev-link state (`dev_channels.json`).
	Auto-reload: linked dev channels are watched for file changes and reloaded automatically. In Docker dev we default to a polling watcher
	(`DEV_WATCHER_MODE=polling`, `DEV_WATCHER_POLLING_INTERVAL=1.0`) for reliability on bind mounts.
- The web UI includes optional PWA/service-worker support, but it is disabled by default for local Docker because a stale SW can cause refreshes to show the offline page.
	To enable it intentionally, build the UI with `REACT_APP_ENABLE_PWA=true`.
