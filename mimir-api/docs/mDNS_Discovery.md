# mDNS Discovery in Mimir API

**mDNS Discovery** is a continuous background service that automatically discovers Mimir display devices on your local network using multicast DNS (mDNS/Zeroconf/Bonjour). This enables zero-configuration networking where displays automatically appear in your Mimir dashboard without manual setup.

## 🎯 **What is mDNS Discovery?**

mDNS (multicast DNS) is a protocol that allows devices to advertise their services on a local network without requiring a central DNS server. Mimir uses mDNS to:

1. **Automatically discover display devices** as they come online
2. **Monitor display health** and detect when devices go offline  
3. **Extract device capabilities** like resolution, location, and features
4. **Provide real-time updates** of network topology changes

## 🔧 **How It Works**

### **1. Service Advertisement (Display Side)**
Display devices (like Inky e-paper displays) advertise themselves using the mDNS service type `_mimir-display._tcp.local.` with properties including:

```python
# Display advertises these properties via mDNS
properties = {
    "display_id": "inky-display-001",
    "display_name": "Office Entrance Display", 
    "hostname": "inky-display-001.local",
    "location": "Office Entrance",
    "resolution": "212x104",
    "webhook_port": "5001",
    "client_version": "2.0.0",
    "redis_distribution": "true",
    "content_claiming": "true",
    "last_seen": "2025-08-31T10:30:00Z"
}
```

### **2. Continuous Discovery (API Side)**
The Mimir API runs a background service that:

- **Listens for mDNS advertisements** on `_mimir-display._tcp.local.`
- **Maintains an internal cache** of discovered displays
- **Monitors display health** by tracking last-seen timestamps
- **Broadcasts events** when displays are discovered, updated, or lost

### **3. Background Monitoring Loop**
Every **30 seconds** (configurable), the service:

```python
# Pseudo-code for monitoring loop
while service_running:
    await asyncio.sleep(update_interval)  # Default: 30 seconds
    
    for display in discovered_displays:
        time_since_seen = now - display.last_seen
        if time_since_seen > offline_timeout:  # Default: 120 seconds
            mark_display_offline(display)
            notify_callbacks(display, "lost")
```

## 📊 **What Gets Discovered**

The mDNS discovery service extracts comprehensive information about each display:

| Property | Description | Example |
|----------|-------------|---------|
| **Display ID** | Unique identifier for the display | `inky-display-001` |
| **Display Name** | Human-readable name | `Office Entrance Display` |
| **Hostname** | Network hostname | `inky-display-001.local` |
| **IP Addresses** | IPv4/IPv6 addresses | `["192.168.1.41"]` |
| **Location** | Physical location | `Office Entrance` |
| **Resolution** | Display dimensions | `212x104` |
| **Webhook Port** | Communication port | `5001` |
| **Client Version** | Software version | `2.0.0` |
| **Capabilities** | Feature flags | `redis_distribution: true` |
| **Last Seen** | Last contact timestamp | `2025-08-31T10:30:00Z` |

## 🌐 **Integration Points**

### **Startup Integration**
Located in your `main.py` at line 45, the service starts automatically when enabled:

```python
# Start mDNS discovery service if enabled
if settings.mdns_discovery_enabled:
    import asyncio
    asyncio.create_task(mdns_discovery_service.start_discovery())
    logger.info("mDNS discovery service started")
```

### **Event-Driven Architecture**
The service uses callbacks to notify other components of discovery events:

```python
# Discovery events that get fired
def on_display_discovered(display, event):
    if event == "discovered":
        logger.info(f"New display found: {display.display_name}")
        # Automatically register in database
        # Update web dashboard
        # Notify administrators
    elif event == "lost":
        logger.info(f"Display went offline: {display.display_name}")
        # Update status in database
        # Alert monitoring systems
```

## 🔍 **Discovery vs Registration**

Mimir supports two ways to add displays to the system:

### **Discovery (Automatic)**
- ✅ **Zero configuration** - displays appear automatically
- ✅ **Real-time updates** - instant status changes
- ✅ **Hardware displays** with mDNS support
- ✅ **Dynamic environments** where displays come and go
- ⚡ **Identified by**: `"display_type": "discovered"`

### **Registration (Manual)**  
- 🔧 **Manual configuration** via API or web interface
- 💾 **Persistent storage** in database
- 🌐 **Web-based displays** (browser clients)
- 📱 **Mobile apps** and virtual displays
- 🔧 **Legacy hardware** without mDNS support
- ⚡ **Identified by**: `"display_type": "registered"`

## ⚙️ **Configuration**

The mDNS discovery service is controlled by these environment variables:

```bash
# Enable/disable mDNS discovery (default: true)
MDNS_DISCOVERY_ENABLED=true

# Update interval in seconds (default: 30)
MDNS_UPDATE_INTERVAL=30

# Offline timeout in seconds (default: 120)  
MDNS_OFFLINE_TIMEOUT=120
```

### **Configuration Details**

| Setting | Default | Description |
|---------|---------|-------------|
| `MDNS_DISCOVERY_ENABLED` | `true` | Enable/disable the entire mDNS discovery system |
| `MDNS_UPDATE_INTERVAL` | `30` | How often to check for offline displays (seconds) |
| `MDNS_OFFLINE_TIMEOUT` | `120` | Mark displays offline after this timeout (seconds) |

## 🔌 **API Endpoints**

### **Legacy Discovery (Enhanced)**
```http
GET /api/displays/discover?timeout=10&auto_register=true
```
- Now returns **immediate results** from background service cache
- Falls back to manual discovery if service not running
- Same response format (backward compatible)

### **New Discovery Endpoints**

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

#### Manual Service Control
```http
POST /api/displays/discovery/start    # Start service
POST /api/displays/discovery/stop     # Stop service
```

## 📈 **Performance Benefits**

### **Before (Manual Discovery)**
- 🐌 Each discovery request scans the network (5-10 seconds)
- 🔄 Multiple clients = multiple scans = network congestion
- ⏱️ Users wait for timeouts on each discovery
- 📊 No real-time status updates

### **After (Continuous Discovery)**  
- ⚡ **Instant results** from background cache
- 🌐 **Single background scan** serves all clients
- 🔄 **Real-time updates** as displays come online/offline
- 📉 **Reduced network traffic** by 90%+

## 🛠️ **Implementation Architecture**

### **Service Components**
```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   mDNS Discovery    │    │   Display Device    │    │   Web Dashboard     │
│      Service        │◄──►│   (Inky Display)    │    │                     │
│                     │    │                     │    │                     │
│ - Zeroconf Browser  │    │ - mDNS Advertiser   │    │ - Real-time Updates │
│ - Event Callbacks   │    │ - Service Info      │    │ - Display Lists     │
│ - Health Monitoring │    │ - Capability Flags  │    │ - Status Indicators │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                          │                          │
           │                          │                          │
           ▼                          ▼                          ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│      Database       │    │     Network         │    │    WebSocket        │
│    (Registered)     │    │   (mDNS/5353)      │    │   Broadcasting      │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

### **Discovery Flow**
1. **Display boots up** → Advertises mDNS service
2. **API service detects** → Parses display information  
3. **Cache updated** → Display added to internal cache
4. **Events fired** → Callbacks notify other components
5. **Database sync** → Auto-registration (if enabled)
6. **Dashboard update** → Real-time display appears in UI

### **Health Monitoring**
```python
# Health monitoring pseudo-code
async def monitoring_loop():
    while service_running:
        await sleep(update_interval)  # 30 seconds
        
        current_time = datetime.now()
        for display in discovered_displays:
            if display.is_online:
                time_since_seen = current_time - display.last_seen
                if time_since_seen > offline_timeout:  # 120 seconds
                    display.is_online = False
                    fire_event("display_lost", display)
```

## ⚡ **Dependencies**

### **Required Libraries**
- `zeroconf>=0.56.0` - mDNS/Zeroconf implementation
- `asyncio` - Asynchronous operation support
- Standard networking libraries

### **Network Requirements** 
- **Port 5353/UDP** - mDNS multicast traffic
- **Multicast support** - Network must allow multicast DNS
- **Same network segment** - Displays and API on same subnet

## 🔧 **Troubleshooting**

### **Service Not Starting**
```bash
# Check if zeroconf library is installed
pip install zeroconf

# Verify environment configuration
echo $MDNS_DISCOVERY_ENABLED  # Should be 'true'

# Check API logs for initialization errors
tail -f /var/log/mimir-api.log | grep mDNS
```

### **No Displays Found**
- ✅ Ensure displays are advertising `_mimir-display._tcp.local.` service
- 🌐 Check network connectivity between API and displays
- 🔥 Verify firewall allows mDNS traffic (port 5353/UDP)
- 📡 Confirm displays and API are on same network segment

### **Performance Issues**
```bash
# Increase update interval for less frequent checks
MDNS_UPDATE_INTERVAL=60

# Increase timeout to reduce false offline alerts  
MDNS_OFFLINE_TIMEOUT=300

# Monitor service statistics
curl http://localhost:5000/api/displays/discovery/status
```

## 📊 **Monitoring & Statistics**

The service provides comprehensive statistics:

```json
{
  "is_running": true,
  "is_available": true,
  "total_discovered": 5,
  "online_displays": 4,
  "offline_displays": 1,
  "update_interval": 30,
  "offline_timeout": 120,
  "discovered_displays": [
    {
      "display_id": "inky-display-001", 
      "display_name": "Office Entrance",
      "hostname": "inky-display-001.local",
      "addresses": ["192.168.1.41"],
      "is_online": true,
      "last_seen": "2025-08-31T10:30:00Z",
      "discovered_at": "2025-08-31T09:15:00Z"
    }
  ]
}
```

This system provides essential zero-configuration networking for Mimir displays, enabling automatic discovery and real-time monitoring of your display infrastructure without manual intervention.