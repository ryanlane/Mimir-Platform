# Continuous mDNS Discovery Service

The Mimir API now includes a continuous background mDNS discovery service that automatically monitors the network for Mimir displays without requiring manual discovery calls.

## Features

### 🔄 **Continuous Monitoring**
- Automatically discovers new displays as they come online
- Detects when displays go offline
- Updates display status in real-time
- No timeouts or manual discovery needed

### 🤖 **Auto-Registration**
- Automatically registers discovered displays in the database
- Updates existing display records when they're rediscovered
- Maintains online/offline status

### 🔧 **Configurable**
- Enable/disable via environment variables
- Configurable update intervals and timeouts
- Optional auto-registration

## Configuration

Add these environment variables to configure the mDNS discovery service:

```bash
# Enable/disable mDNS discovery (default: true)
MDNS_DISCOVERY_ENABLED=true

# Auto-register discovered displays (default: true)
MDNS_AUTO_REGISTER=true

# Update interval in seconds (default: 30)
MDNS_UPDATE_INTERVAL=30

# Offline timeout in seconds (default: 120)
MDNS_OFFLINE_TIMEOUT=120
```

## API Endpoints

### Legacy Discovery (Manual)
```http
GET /api/displays/discover?timeout=10&auto_register=true
```
- Now uses background service results if available
- Falls back to manual discovery if service not running
- Returns immediate results from cached discoveries

### New Discovery Endpoints

#### Get Discovery Service Status
```http
GET /api/displays/discovery/status
```
Returns current service status and all discovered displays.

#### Get Live Discovered Displays
```http
GET /api/displays/discovery/live
```
Returns currently discovered displays from the background service.

#### Start Discovery Service
```http
POST /api/displays/discovery/start
```
Manually start the mDNS discovery service.

#### Stop Discovery Service
```http
POST /api/displays/discovery/stop
```
Stop the mDNS discovery service.

## Service Architecture

### Background Service
- Runs continuously in the background
- Uses Zeroconf/mDNS to monitor `_mimir-display._tcp.local.` services
- Maintains internal cache of discovered displays
- Automatically updates database records

### Event-Driven Updates
- Real-time discovery events (discovered, updated, lost)
- Callback system for external integrations
- Automatic database synchronization

### Health Monitoring
- Tracks display last-seen timestamps
- Automatically marks displays offline after timeout
- Updates database status accordingly

## Benefits

### For Users
- **Immediate discovery**: No waiting for timeouts
- **Real-time updates**: See displays appear/disappear instantly
- **Better reliability**: Always up-to-date display status

### For Developers
- **Event callbacks**: Register for discovery events
- **Consistent API**: Same endpoints work with background service
- **Performance**: No repeated mDNS scans

### For Administrators
- **Lower network traffic**: Single background scan vs multiple manual scans
- **Better monitoring**: Continuous health tracking
- **Configurable behavior**: Tune intervals and timeouts

## Implementation Details

### Service Lifecycle
1. **Startup**: Service starts automatically with the API
2. **Discovery**: Continuously scans for mDNS services
3. **Processing**: Parses display information and properties
4. **Registration**: Auto-registers displays in database
5. **Monitoring**: Tracks display health and status
6. **Shutdown**: Cleanly stops with the API

### Display Information Extracted
- Display ID, name, and location
- Hostname and IP addresses
- Resolution and capabilities
- Webhook port for communication
- Client version and feature flags
- Last seen timestamps

### Fault Tolerance
- Graceful handling of mDNS library availability
- Fallback to manual discovery if service fails
- Automatic restart on errors
- Configuration validation

## Usage Examples

### Check Service Status
```bash
curl http://localhost:5000/api/displays/discovery/status
```

### Get Live Displays
```bash
curl http://localhost:5000/api/displays/discovery/live
```

### Use Traditional Discovery (now enhanced)
```bash
curl "http://localhost:5000/api/displays/discover?timeout=0"
# Returns immediate results from background service
```

## Migration from Manual Discovery

The existing `/api/displays/discover` endpoint continues to work but now:

1. **If background service is running**: Returns immediate results from cache
2. **If background service is stopped**: Falls back to manual discovery
3. **Same response format**: No breaking changes
4. **Enhanced data**: Additional fields like `continuous_discovery: true`

## Troubleshooting

### Service Not Starting
- Check if `zeroconf` library is installed: `pip install zeroconf`
- Verify `MDNS_DISCOVERY_ENABLED=true` in environment
- Check logs for initialization errors

### No Displays Found
- Ensure displays are advertising `_mimir-display._tcp.local.` service
- Check network connectivity
- Verify displays are on same network segment
- Check firewall settings for mDNS (port 5353)

### Performance Issues
- Increase `MDNS_UPDATE_INTERVAL` for less frequent updates
- Increase `MDNS_OFFLINE_TIMEOUT` to reduce false offline states
- Disable auto-registration if not needed: `MDNS_AUTO_REGISTER=false`

## Dependencies

- `zeroconf>=0.56.0` (already in requirements.txt)
- Python 3.8+ with asyncio support
- Network access to multicast DNS (port 5353)
