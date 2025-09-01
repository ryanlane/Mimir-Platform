# MQTT Presence System Setup Summary

## ✅ Completed Tasks

### 1. Dependencies Updated
- Updated `requirements.txt` to use `aiomqtt>=1.0.0` (renamed from asyncio-mqtt)
- Updated all MQTT service code to use new aiomqtt v1.0 API
- Package installed in api-service environment

### 2. Configuration Updated
- Updated `app/config.py` to point MQTT broker to "oak" machine
- MQTT is enabled by default with proper settings

### 3. MQTT Services Created
- **API Service**: `app/services/mqtt_presence.py` - Server-side MQTT presence detection
- **Display Client**: `mqtt_presence_client.py` - Client script for display devices
- **Admin API**: Added MQTT management endpoints to `routes/admin.py`

### 4. Connectivity Diagnostics
- Created `mqtt_diagnostics.py` - Comprehensive connectivity testing
- Created `test_mqtt_connectivity_v2.py` - MQTT protocol testing

## 🔧 Current Status

### Network Connectivity ✅
- Hostname "oak" resolves to `192.168.1.19` ✅
- DNS resolution working ✅

### MQTT Broker ❌
- **Issue**: Connection refused to port 1883 on oak
- **Cause**: MQTT broker (mosquitto) not running or not accessible

## 🚀 Next Steps

### 1. Start MQTT Broker on Oak
```bash
# On the oak machine:
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
sudo systemctl status mosquitto
```

### 2. Verify MQTT Broker
```bash
# Check if it's listening:
sudo netstat -tlnp | grep :1883

# Test locally on oak:
mosquitto_pub -h localhost -t test -m "hello"
mosquitto_sub -h localhost -t test
```

### 3. Configure Firewall (if needed)
```bash
# Allow MQTT port:
sudo ufw allow 1883

# Or for iptables:
sudo iptables -A INPUT -p tcp --dport 1883 -j ACCEPT
```

### 4. Test Connectivity
```bash
# From mimir-api machine:
cd /mnt/c/Users/futil/projects/github/mimir-api
python mqtt_diagnostics.py
python test_mqtt_connectivity_v2.py
```

### 5. Deploy MQTT Presence System
Once MQTT broker is accessible:
```bash
# Restart mimir-api service to enable MQTT
cd /mnt/c/Users/futil/projects/github/mimir-api/api-service
# Deploy with your usual process

# Install client on display devices
# Copy mqtt_presence_client.py to display devices
# Run: python mqtt_presence_client.py --broker oak
```

## 📊 Expected Benefits

### Instant Presence Detection
- **Before**: 30-120 second polling delays for offline detection
- **After**: Sub-second offline detection via MQTT Last Will & Testament

### Real-time Display Management
- Immediate notification when displays go offline
- Instant online status when displays reconnect
- Real-time display inventory in admin dashboard

### Reduced Network Load
- Event-driven vs polling-based detection
- Heartbeat messages only (no constant status checks)
- More efficient than mDNS scanning

## 🔍 Troubleshooting

If issues persist after starting mosquitto:
1. Check mosquitto logs: `sudo journalctl -u mosquitto -f`
2. Verify configuration: `sudo mosquitto -c /etc/mosquitto/mosquitto.conf -v`
3. Test with mosquitto clients: `mosquitto_pub` and `mosquitto_sub`
4. Check for port conflicts: `sudo lsof -i :1883`

## 📱 Admin Interface

New MQTT admin endpoints available at:
- `GET /admin/mqtt/status` - MQTT service status
- `GET /admin/mqtt/devices` - Connected devices list  
- `POST /admin/mqtt/publish` - Manual device status publishing

Once running, you'll have real-time display presence in your admin dashboard!
