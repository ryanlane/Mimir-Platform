#!/usr/bin/env python3
"""
Generate missing thumbnails for existing images in photo frame channel
"""

import sys
from pathlib import Path
from PIL import Image

def generate_thumbnails(uploads_dir_path):
    """Generate thumbnails for all images that don't have them"""
    uploads_dir = Path(uploads_dir_path)
    
    if not uploads_dir.exists():
        print(f"❌ Uploads directory not found: {uploads_dir}")
        return
    
    print(f"🔍 Scanning for images in: {uploads_dir}")
    
    generated_count = 0
    error_count = 0
    
    # Find all image files
    for image_file in uploads_dir.glob('image_*.png'):
        # Generate thumbnail filename: image_abc123.png -> image_abc123.thumb.jpg
        base_name = image_file.stem
        thumb_filename = f'{base_name}.thumb.jpg'
        thumb_path = uploads_dir / thumb_filename
        
        if thumb_path.exists():
            print(f"⏭️  Thumbnail already exists: {thumb_filename}")
            continue
            
        try:
            print(f"🖼️  Generating thumbnail for: {image_file.name}")
            
            with Image.open(image_file) as img:
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img
                
                # Create thumbnail (600x600 max, maintaining aspect ratio)
                img.thumbnail((600, 600), Image.Resampling.LANCZOS)
                img.save(thumb_path, 'JPEG', quality=85, optimize=True)
                
                print(f"✅ Generated thumbnail: {thumb_filename}")
                generated_count += 1
                
        except Exception as e:
            print(f"❌ Failed to generate thumbnail for {image_file.name}: {e}")
            error_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Generated: {generated_count} thumbnails")
    print(f"   Errors: {error_count}")
    
    if generated_count > 0:
        print(f"✅ Thumbnail generation complete!")
    else:
        print(f"ℹ️  No new thumbnails needed.")

if __name__ == "__main__":
    uploads_path = "/var/opt/mimir/mimir-api/channels/photo_frame/assets/uploads"
    if len(sys.argv) > 1:
        uploads_path = sys.argv[1]
    
    generate_thumbnails(uploads_path)
