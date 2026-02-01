# Mimir API Permission Fix Commands
# Run these commands on the oak server to fix the permission issues

# === IMMEDIATE FIX (run these on oak server) ===

# 1. Fix file permissions for photo frame channel
sudo find /var/opt/mimir/mimir-api/channels/photo_frame -type f -exec chmod 644 {} \;
sudo find /var/opt/mimir/mimir-api/channels/photo_frame -type d -exec chmod 755 {} \;

# 2. Set correct ownership
sudo chown -R mimir:mimir /var/opt/mimir/mimir-api/channels/photo_frame

# 3. Restart the API service
sudo systemctl restart mimir-api

# === VERIFICATION ===

# Check if files are now readable
ls -la /var/opt/mimir/mimir-api/channels/photo_frame/assets/uploads/ | head -5

# Check service status
systemctl status mimir-api

# Test API endpoint
curl -I http://localhost:5000/api/channels/photo_frame/current.jpg

# === COMPREHENSIVE TESTING ===

# From your development machine, run:
# python3 test_all_channel_endpoints.py --host oak --port 5000 --photo-frame-only

# === WHAT THESE COMMANDS DO ===

# chmod 644: Sets file permissions to rw-r--r-- (owner read/write, group/others read)
# chmod 755: Sets directory permissions to rwxr-xr-x (owner full access, group/others read/execute)
# chown mimir:mimir: Sets ownership to mimir user and mimir group
# systemctl restart: Restarts the API service to pick up permission changes

# === TROUBLESHOOTING ===

# If you get "Permission denied" errors:
# - Make sure you're running with sudo
# - Check that the mimir user exists: getent passwd mimir
# - Check that the mimir group exists: getent group mimir

# If the API service won't start:
# - Check logs: journalctl -u mimir-api -f
# - Check config files have correct permissions
# - Verify the API service is configured to run as the mimir user
