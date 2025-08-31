# Channel API Fixes and Improvements Summary

## Issues Fixed

### 1. ✅ Duplicate Operation ID Warning
**Problem**: FastAPI warning about duplicate operation ID for `get_channel_settings`
```
Duplicate Operation ID get_channel_settings_api_channels__channel_id__settings_get
```

**Solution**: Removed duplicate `get_channel_settings` function at line ~1420 in `channels.py`

**Files Changed**:
- `api-service/app/api/routes/channels.py` - Removed duplicate endpoint

### 2. ✅ Channel ID Documentation Added
**Problem**: Need clear documentation about proper channel ID usage

**Solution**: Added comprehensive documentation at the top of `channels.py`

**Key Rule**: 
```
⚠️ CRITICAL: CHANNEL ID USAGE ⚠️
ALL channel operations MUST use the channel ID from the channel's config.json file,
NEVER the directory name, path, or display name.

✅ Correct: Use config.json "id" field (e.g., "com.epaperframe.photoframe")
❌ Wrong: Use directory name (e.g., "photo_frame") 
❌ Wrong: Use display name (e.g., "Photo Frame")
```

### 3. 🔄 Channel Discovery Improvements
**Problem**: Discovery service trying to process subdirectories as channels
```
No config.json found for channel: photo_frameassets
No config.json found for channel: photo_framedata
```

**Solution**: Enhanced channel discovery with better filtering and logging

**Improvements**:
- Skip hidden directories (starting with '.')
- Skip common subdirectories: `assets`, `data`, `static`, `uploads`, `thumbnails`, `cache`, `temp`, `logs`
- Better debug logging to track discovery process
- More specific warning messages with full paths

**Files Changed**:
- `api-service/app/services/channel_discovery.py` - Enhanced discovery logic

## API Testing Results

### ✅ Working Endpoints (Photo Frame Channel: `com.epaperframe.photoframe`)
- `/api/channels` - Lists all channels ✅
- `/api/channels/{channel_id}/config` - Channel configuration ✅
- `/api/channels/{channel_id}/settings` - Channel settings ✅
- `/api/channels/{channel_id}/status` - Channel status ✅
- `/api/channels/{channel_id}/health` - Health checks ✅
- `/api/channels/{channel_id}/token` - Authentication tokens ✅
- `/api/channels/{channel_id}/current` - Current content info ✅
- `/api/channels/{channel_id}/test` - Channel testing ✅
- `/api/channels/{channel_id}/images` - Image listing ✅
- `/api/channels/{channel_id}/images/upload` - Image upload ✅
- `/api/channels/{channel_id}/subchannels` - Subchannel management ✅
- `/api/channels/{channel_id}/subchannels/{id}` - Individual subchannel access ✅

### 🔄 Remaining Issues
- `/api/channels/{channel_id}/current.jpg` - Returns 404 (likely permission issue)

## Permission Issues

### Problem
API service cannot read image files due to permission issues:
```
Permission denied: '/var/opt/mimir/mimir-api/channels/photo_frame/assets/uploads/image_*.jpg'
```

### Solution Commands (Run on oak server)
```bash
# Fix file permissions
sudo find /var/opt/mimir/mimir-api/channels -type f -exec chmod 644 {} \;
sudo find /var/opt/mimir/mimir-api/channels -type d -exec chmod 755 {} \;

# Set correct ownership
sudo chown -R mimir:mimir /var/opt/mimir/mimir-api/channels

# Restart API service
sudo systemctl restart mimir-api
```

## Channel Discovery Analysis

### Correct Channel Structure
```
/var/opt/mimir/mimir-api/channels/
├── photo_frame/                    # Directory name (not used for API)
│   ├── config.json                 # Contains "id": "com.epaperframe.photoframe"
│   ├── assets/                     # Should be ignored by discovery
│   │   ├── uploads/               # Should be ignored by discovery
│   │   └── thumbnails/            # Should be ignored by discovery
│   └── data/                      # Should be ignored by discovery
│       └── galleries.json
├── example_channel/
│   └── config.json
└── weather_channel/
    └── config.json
```

### Channel ID Mapping
| Directory Name | Config ID | Use in API |
|----------------|-----------|------------|
| `photo_frame` | `com.epaperframe.photoframe` | ✅ `com.epaperframe.photoframe` |
| `example_channel` | `example_channel` | ✅ `example_channel` |
| `weather_channel` | `weather_channel` | ✅ `weather_channel` |

## Diagnostic Scripts Created

### 1. `diagnose_channel_structure.sh`
Run on oak server to check channel directory structure and identify issues

### 2. `quick_fix_oak.sh`  
Quick permission fix script for oak server

### 3. `PERMISSION_FIX_COMMANDS.md`
Step-by-step commands to fix permission issues

### 4. `test_all_channel_endpoints.py`
Comprehensive API test suite for all channel endpoints

## Testing Commands

### Full API Test
```bash
python3 test_all_channel_endpoints.py --host oak --port 5000
```

### Photo Frame Only Test
```bash
python3 test_all_channel_endpoints.py --host oak --port 5000 --photo-frame-only
```

### Test After Permission Fix
```bash
# On oak server - fix permissions first
sudo ./quick_fix_oak.sh

# From development machine - test API
python3 test_all_channel_endpoints.py --host oak --port 5000 --photo-frame-only
```

## Next Steps

1. **Fix Permissions**: Run permission fix commands on oak server
2. **Test Discovery**: Restart API service and check logs for discovery warnings
3. **Validate API**: Run comprehensive tests to ensure all endpoints work
4. **Monitor Logs**: Watch for any remaining permission or discovery issues

## Best Practices Established

### Channel ID Usage
- Always use config.json "id" field in API calls
- Never use directory names or display names
- Validate channel IDs through ChannelDiscoveryService

### Channel Discovery
- Only process directories with config.json files
- Skip common subdirectories automatically
- Log discovery process for debugging

### File Permissions
- Use 644 for files (rw-r--r--)
- Use 755 for directories (rwxr-xr-x)
- Ensure mimir:mimir ownership
- Restart API service after permission changes

### API Testing
- Test all endpoints systematically
- Use proper channel IDs from discovery
- Include error handling validation
- Monitor response times and success rates
