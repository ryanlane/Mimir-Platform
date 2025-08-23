#!/usr/bin/env python3
"""
Photo Frame Database Recovery Script

This script rebuilds the photo frame database from existing image files
when the database has been lost but image files remain.

Usage:
    python recover_photo_frame_db.py /path/to/photo/frame/channel
"""

import sys
import sqlite3
from pathlib import Path
from PIL import Image
import json
from datetime import datetime, timezone

def get_image_dimensions(image_path):
    """Get image dimensions using PIL"""
    try:
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except Exception as e:
        print(f"Warning: Could not read {image_path}: {e}")
        return (800, 600)  # Default dimensions

def recover_database(channel_dir):
    """Recover the photo frame database from existing files"""
    channel_path = Path(channel_dir)
    uploads_dir = channel_path / "assets" / "uploads"
    data_dir = channel_path / "data"
    db_path = data_dir / "photo_frame.db"
    
    if not uploads_dir.exists():
        print(f"❌ Upload directory not found: {uploads_dir}")
        return False
    
    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database to start fresh
    if db_path.exists():
        backup_path = db_path.with_suffix('.db.backup')
        db_path.rename(backup_path)
        print(f"📦 Backed up existing database to {backup_path}")
    
    # Initialize new database
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create tables (same as PhotoFrameDB._init_db)
    c.execute('''CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        original_name TEXT NOT NULL,
        title TEXT DEFAULT '',
        description TEXT DEFAULT '',
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        enabled BOOLEAN DEFAULT TRUE,
        sort_order INTEGER DEFAULT 0,
        times_shown INTEGER DEFAULT 0,
        last_shown_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        crop_x REAL DEFAULT 0.0,
        crop_y REAL DEFAULT 0.0,
        crop_width REAL DEFAULT 100.0,
        crop_height REAL DEFAULT 100.0,
        preserve_aspect_ratio BOOLEAN DEFAULT FALSE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS channel_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(uploads_dir.glob(f'*{ext}'))
        image_files.extend(uploads_dir.glob(f'*{ext.upper()}'))
    
    print(f"📁 Found {len(image_files)} image files in {uploads_dir}")
    
    # Add images to database
    recovered_count = 0
    for i, image_path in enumerate(sorted(image_files)):
        try:
            width, height = get_image_dimensions(image_path)
            
            # Use file modification time as created_at
            mtime = datetime.fromtimestamp(image_path.stat().st_mtime, tz=timezone.utc)
            
            c.execute('''INSERT INTO images 
                (filename, original_name, width, height, enabled, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (image_path.name, image_path.name, width, height, True, i, mtime.isoformat()))
            
            recovered_count += 1
            print(f"✅ Recovered: {image_path.name} ({width}x{height})")
            
        except Exception as e:
            print(f"❌ Failed to recover {image_path.name}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Database recovery complete!")
    print(f"📊 Recovered {recovered_count} images")
    print(f"💾 Database saved to: {db_path}")
    
    # Clear galleries.json to avoid orphaned references
    galleries_file = data_dir / "galleries.json"
    if galleries_file.exists():
        backup_galleries = galleries_file.with_suffix('.json.backup')
        galleries_file.rename(backup_galleries)
        print(f"📦 Backed up galleries to {backup_galleries}")
    
    # Create empty galleries file
    with open(galleries_file, 'w') as f:
        json.dump([], f)
    print(f"🗂️ Reset galleries (you'll need to recreate them)")
    
    return True

def regenerate_thumbnails(channel_dir):
    """Regenerate thumbnails for all images"""
    print("\n🖼️ Regenerating thumbnails...")
    
    channel_path = Path(channel_dir)
    uploads_dir = channel_path / "assets" / "uploads"
    thumbs_dir = channel_path / "data" / "thumbs"
    
    # Clear existing thumbnails
    if thumbs_dir.exists():
        for thumb in thumbs_dir.glob('*'):
            thumb.unlink()
    else:
        thumbs_dir.mkdir(parents=True, exist_ok=True)
    
    # Regenerate thumbnails
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    thumbnail_count = 0
    
    for image_path in uploads_dir.iterdir():
        if image_path.suffix.lower() in image_extensions:
            try:
                with Image.open(image_path) as img:
                    # Create thumbnail (150x150 max, maintain aspect ratio)
                    img.thumbnail((150, 150), Image.Resampling.LANCZOS)
                    
                    # Save as JPEG thumbnail
                    thumb_path = thumbs_dir / f"{image_path.stem}.jpg"
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Convert to RGB for JPEG
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    
                    img.save(thumb_path, 'JPEG', quality=85)
                    thumbnail_count += 1
                    
            except Exception as e:
                print(f"❌ Failed to create thumbnail for {image_path.name}: {e}")
    
    print(f"✅ Generated {thumbnail_count} thumbnails")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python recover_photo_frame_db.py /path/to/photo/frame/channel")
        sys.exit(1)
    
    channel_dir = sys.argv[1]
    
    if not Path(channel_dir).exists():
        print(f"❌ Channel directory not found: {channel_dir}")
        sys.exit(1)
    
    print(f"🔧 Starting photo frame database recovery...")
    print(f"📁 Channel directory: {channel_dir}")
    
    if recover_database(channel_dir):
        regenerate_thumbnails(channel_dir)
        print(f"\n✅ Recovery complete! Your photo frame channel should now work.")
        print(f"ℹ️  Note: You'll need to recreate any galleries through the web interface.")
    else:
        print(f"\n❌ Recovery failed!")
        sys.exit(1)
