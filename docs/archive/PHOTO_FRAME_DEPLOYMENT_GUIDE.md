# Safe Photo Frame Deployment Guide

## Current Issue
- Rsync preserves `assets/uploads/` but overwrites database
- Result: Image files exist but no database records reference them

## Quick Fix (If Already Happened)
```bash
# Navigate to your API server
cd /path/to/mimir-api

# Run the recovery script
python recover_photo_frame_db.py /path/to/channels/photo_frame

# This will:
# ✅ Rebuild database from existing files
# ✅ Regenerate thumbnails
# ✅ Reset galleries (you'll need to recreate them)
```

## Future Deployment Strategy

### Option 1: Exclude User Data (Recommended)
```bash
# Modify your rsync to exclude user data directories
rsync -av \
  --exclude 'channels/photo_frame/assets/uploads/' \
  --exclude 'channels/photo_frame/data/' \
  --exclude 'channels/photo_frame/current/' \
  SOURCE/ DEST/
```

### Option 2: Backup and Restore
```bash
# Before deployment
./migrate_photo_frame_data.sh /path/to/photo_frame backup

# Run your rsync deployment
rsync -av SOURCE/ DEST/

# After deployment
./migrate_photo_frame_data.sh /path/to/photo_frame restore
```

### Option 3: Smart Deployment Script
```bash
#!/bin/bash
PHOTO_FRAME_DIR="/path/to/channels/photo_frame"

echo "🚀 Starting smart photo frame deployment..."

# Backup user data
./migrate_photo_frame_data.sh "$PHOTO_FRAME_DIR" backup

# Deploy code (including user data exclusions)
rsync -av \
  --exclude 'channels/photo_frame/assets/uploads/' \
  --exclude 'channels/photo_frame/data/' \
  --exclude 'channels/photo_frame/current/' \
  SOURCE/ DEST/

# Restore user data
./migrate_photo_frame_data.sh "$PHOTO_FRAME_DIR" restore

echo "✅ Deployment complete with user data preserved!"
```

## File Structure Understanding
```
channels/photo_frame/
├── channel.py              # Code (safe to overwrite)
├── config.json            # Configuration (safe to overwrite)
├── utils/                  # Code (safe to overwrite)
├── data/                   # ⚠️  USER DATA - PRESERVE
│   ├── photo_frame.db      # Image metadata and references
│   ├── galleries.json      # Gallery/sub-channel definitions
│   └── thumbs/            # Generated thumbnails
├── assets/                 # ⚠️  USER DATA - PRESERVE
│   └── uploads/           # Original uploaded images
└── current/               # ⚠️  USER DATA - PRESERVE
    └── */                 # Resolution-specific rendered images
```

## Recovery After Data Loss
If you've already lost the database:
1. Run `recover_photo_frame_db.py` to rebuild from files
2. Recreate galleries through the web interface
3. Reassign images to galleries as needed

## Prevention
- Always exclude user data directories from deployment rsync
- Consider using Docker volumes for persistent data
- Regular backups of the `data/` directory
