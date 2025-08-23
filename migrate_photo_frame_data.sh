#!/bin/bash
"""
Photo Frame Data Migration Script

Backs up user data before deployment and restores it after.
"""

CHANNEL_DIR="${1:-/path/to/photo/frame/channel}"
BACKUP_DIR="/tmp/photo_frame_backup_$(date +%Y%m%d_%H%M%S)"

backup_user_data() {
    echo "📦 Backing up photo frame user data..."
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    if [ -f "$CHANNEL_DIR/data/photo_frame.db" ]; then
        cp "$CHANNEL_DIR/data/photo_frame.db" "$BACKUP_DIR/"
        echo "✅ Database backed up"
    fi
    
    # Backup galleries
    if [ -f "$CHANNEL_DIR/data/galleries.json" ]; then
        cp "$CHANNEL_DIR/data/galleries.json" "$BACKUP_DIR/"
        echo "✅ Galleries backed up"
    fi
    
    # Backup thumbnails
    if [ -d "$CHANNEL_DIR/data/thumbs" ]; then
        cp -r "$CHANNEL_DIR/data/thumbs" "$BACKUP_DIR/"
        echo "✅ Thumbnails backed up"
    fi
    
    # Backup uploads
    if [ -d "$CHANNEL_DIR/assets/uploads" ]; then
        cp -r "$CHANNEL_DIR/assets/uploads" "$BACKUP_DIR/"
        echo "✅ Uploads backed up"
    fi
    
    # Backup current images
    if [ -d "$CHANNEL_DIR/current" ]; then
        cp -r "$CHANNEL_DIR/current" "$BACKUP_DIR/"
        echo "✅ Current images backed up"
    fi
    
    echo "📁 Backup saved to: $BACKUP_DIR"
}

restore_user_data() {
    echo "🔄 Restoring photo frame user data..."
    
    # Create necessary directories
    mkdir -p "$CHANNEL_DIR/data"
    mkdir -p "$CHANNEL_DIR/assets"
    mkdir -p "$CHANNEL_DIR/current"
    
    # Restore database
    if [ -f "$BACKUP_DIR/photo_frame.db" ]; then
        cp "$BACKUP_DIR/photo_frame.db" "$CHANNEL_DIR/data/"
        echo "✅ Database restored"
    fi
    
    # Restore galleries
    if [ -f "$BACKUP_DIR/galleries.json" ]; then
        cp "$BACKUP_DIR/galleries.json" "$CHANNEL_DIR/data/"
        echo "✅ Galleries restored"
    fi
    
    # Restore thumbnails
    if [ -d "$BACKUP_DIR/thumbs" ]; then
        cp -r "$BACKUP_DIR/thumbs" "$CHANNEL_DIR/data/"
        echo "✅ Thumbnails restored"
    fi
    
    # Restore uploads
    if [ -d "$BACKUP_DIR/uploads" ]; then
        cp -r "$BACKUP_DIR/uploads" "$CHANNEL_DIR/assets/"
        echo "✅ Uploads restored"
    fi
    
    # Restore current images
    if [ -d "$BACKUP_DIR/current" ]; then
        cp -r "$BACKUP_DIR/current" "$CHANNEL_DIR/"
        echo "✅ Current images restored"
    fi
    
    echo "🎉 User data restoration complete!"
}

case "$2" in
    "backup")
        backup_user_data
        ;;
    "restore")
        restore_user_data
        ;;
    *)
        echo "Usage: $0 <channel_dir> <backup|restore>"
        echo "Example: $0 /path/to/photo/frame backup"
        exit 1
        ;;
esac
