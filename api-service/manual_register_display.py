#!/usr/bin/env python3

"""
Manually register a display in the database
"""

import sys
import os
sys.path.append('/opt/mimir/mimir-api')

from app.db.base import SessionLocal
from app.db.models import DisplayClient
import datetime

def register_display_manually():
    """Manually register the colorframe05 display"""
    db = SessionLocal()
    
    try:
        # Check if display already exists
        existing = db.query(DisplayClient).filter(
            DisplayClient.hostname == "colorframe05"
        ).first()
        
        if existing:
            print(f"✅ Display already exists with ID: {existing.id}")
            print(f"   Name: {existing.name}")
            print(f"   Location: {existing.location}")
            print(f"   Status: {'Online' if existing.is_online else 'Offline'}")
            return existing.id
        
        # Create new display
        display_id = "discovery-colorframe05-1756316347"  # Use the ID from the display client
        
        new_display = DisplayClient(
            id=display_id,
            name="Inky ePaper Display",
            location="Lab Bench",
            hostname="colorframe05",
            webhook_port=8081,
            width=800,
            height=480,
            orientation="landscape",
            client_version="1.0.0",
            redis_distribution=True,
            content_claiming=True,
            display_type="discovered",
            discovery_method="manual",
            auto_discovered=False,
            is_online=True,
            last_seen=datetime.datetime.now()
        )
        
        db.add(new_display)
        db.commit()
        db.refresh(new_display)
        
        print(f"✅ Successfully registered display:")
        print(f"   ID: {new_display.id}")
        print(f"   Name: {new_display.name}")
        print(f"   Location: {new_display.location}")
        print(f"   Hostname: {new_display.hostname}")
        print(f"   Resolution: {new_display.width}x{new_display.height}")
        print(f"   Webhook: http://192.168.1.41:8081")
        
        return new_display.id
        
    except Exception as e:
        print(f"❌ Failed to register display: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def main():
    print("🔧 Manual Display Registration")
    print("=" * 40)
    
    display_id = register_display_manually()
    
    if display_id:
        print(f"\n🎉 Display registration complete!")
        print(f"You can now see the display at: http://oak:5000/api/displays")
        print(f"Display ID: {display_id}")
    else:
        print(f"\n❌ Registration failed")

if __name__ == "__main__":
    main()
