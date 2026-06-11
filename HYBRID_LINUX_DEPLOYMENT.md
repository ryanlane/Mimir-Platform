# Hybrid Linux Deployment

This is the recommended deployment model for onboarding physical displays on a LAN.

Use containers for the application services:

- API
- Web UI
- Postgres
- Redis
- Mosquitto

Use the Ubuntu host for network-facing discovery:

- mDNS advertisement
- mDNS browsing
- any bootstrap behavior that must expose the machine's real LAN identity

This avoids the main Docker networking failure modes for display onboarding:

- advertising `localhost`
- advertising internal container hostnames
- unreliable multicast on bridged or virtualized networks

## Why this model

Physical displays need to reach the real machine on the LAN.

That means they need one of these to be true:

- the API advertises a real LAN IP or hostname
- the host advertises a real `mimir.local` name via mDNS

Docker bridge networking is good for app isolation, but it is not a good source of truth for host identity.

## Server setup

### 1. Configure the service stack

From the service root:

```bash
cp .env.hybrid.example .env
```

Edit `.env` and set at least:

```env
PUBLIC_HOST=192.168.1.50
MQTT_PUBLIC_HOST=192.168.1.50
REACT_APP_API_URL=http://192.168.1.50:5000
```

If you also want a friendly local hostname and your Ubuntu host advertises it correctly:

```env
PUBLIC_MDNS_HOST=mimir.local
```

### 2. Start the main services in Docker

```bash
docker compose up -d --build
```

### 3. Run discovery natively on the host

Do not rely on bridged Docker networking for discovery.

From `mimir-discovery/python`:

```bash
MIMIR_API_BASE=http://127.0.0.1:5000 ./run_local.sh
```

For a persistent service, install the example unit:

```bash
sudo cp mimir-discovery/python/mimir-discovery.service.example /etc/systemd/system/mimir-discovery.service
sudo systemctl daemon-reload
sudo systemctl enable --now mimir-discovery
sudo systemctl status mimir-discovery
```

If you use a token, set the same `MIMIR_DISCOVERY_TOKEN` value in both the API environment and the systemd unit.

## Display onboarding

On first boot, leave these blank on the display:

```env
PLATFORM_URL=
MQTT_BROKER_HOST=
```

The expected flow is:

1. display finds `_mimir._tcp.local.` via mDNS
2. display fetches `/api/displays/mqtt/config`
3. display receives real API/MQTT coordinates
4. display registers and shows pairing code
5. user claims the code from the web UI

Manual setup remains a fallback, not the primary path.

## Development workflow

Use your laptop for editing and small UI/API iteration.

Use the Ubuntu server as the truth for hardware validation.

Recommended loop:

1. edit code locally
2. push or sync to the Ubuntu server
3. rebuild/restart only the changed service on the server
4. validate against real displays on the LAN

For example:

```bash
git push origin main
ssh ubuntu-server 'cd /opt/mimir/service && git pull && docker compose up -d --build web api'
```

If you are changing discovery logic, restart the host-native service too:

```bash
ssh ubuntu-server 'sudo systemctl restart mimir-discovery'
```

## Validation checklist

Verify the API advertises a real LAN identity:

```bash
curl http://127.0.0.1:5000/api/displays/mqtt/config
```

The response should contain the server's LAN IP or real hostname, not:

- `localhost`
- `127.0.0.1`
- Docker container names
- container-hash `.local` names

Verify discovery is running:

```bash
sudo journalctl -u mimir-discovery -f
```

Verify the display client bootstrap:

```bash
sudo journalctl -u mimir-display -f
```

The display should wait for bootstrap and must not attempt MQTT with an empty host.