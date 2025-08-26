#!/usr/bin/env python3
"""
Cleanup Duplicate Display Clients
=================================

This script removes duplicate display clients from the database.
It keeps the most recently created entry for each unique combination of name+location.

Usage:
    python cleanup_duplicate_displays.py
"""

import sqlite3
import os
import sys
from datetime import datetime

# Database configuration  
DB_PATH = "./app.db"

def cleanup_duplicates():
    """Remove duplicate display clients"""
    
    print("🧹 Cleaning up duplicate display clients")
    print("=" * 50)
    print(f"📅 Cleanup Date: {datetime.now().isoformat()}")
    print(f"🗄️  Database: {DB_PATH}")
    print()
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file not found: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if display_clients table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='display_clients'")
        if not cursor.fetchone():
            print("❌ display_clients table not found!")
            return False
        
        print("📋 Finding duplicates...")
        
        # Find duplicates based on name + location combination
        cursor.execute("""
            SELECT name, location, COUNT(*) as count
            FROM display_clients 
            GROUP BY name, location
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            print("✅ No duplicates found!")
            return True
        
        print(f"🔍 Found {len(duplicates)} sets of duplicates:")
        for name, location, count in duplicates:
            print(f"   • '{name}' at '{location}': {count} entries")
        
        print()
        
        # For each duplicate set, keep the most recent one
        removed_count = 0
        for name, location in [(d[0], d[1]) for d in duplicates]:
            print(f"🔧 Processing duplicates for '{name}' at '{location}'...")
            
            # Get all entries for this name+location, ordered by creation date
            cursor.execute("""
                SELECT id, created_at 
                FROM display_clients 
                WHERE name = ? AND location = ?
                ORDER BY created_at DESC NULLS LAST, id DESC
            """, (name, location))
            
            entries = cursor.fetchall()
            
            if len(entries) > 1:
                # Keep the first one (most recent), remove the rest
                keep_id = entries[0][0]
                remove_ids = [entry[0] for entry in entries[1:]]
                
                print(f"   ✅ Keeping: {keep_id} (created: {entries[0][1]})")
                
                for remove_id in remove_ids:
                    print(f"   🗑️  Removing: {remove_id}")
                    cursor.execute("DELETE FROM display_clients WHERE id = ?", (remove_id,))
                    removed_count += 1
        
        # Commit changes
        conn.commit()
        
        print()
        print("=" * 50)
        print(f"✅ Cleanup completed!")
        print(f"📝 Removed {removed_count} duplicate entries")
        
        # Show final count
        cursor.execute("SELECT COUNT(*) FROM display_clients")
        final_count = cursor.fetchone()[0]
        print(f"📊 Remaining display clients: {final_count}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("Duplicate Display Client Cleanup")
    print("================================")
    
    # Check if we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ This script should be run from the api-service directory")
        print("   where main.py is located")
        sys.exit(1)
    
    # Run cleanup
    success = cleanup_duplicates()
    
    if success:
        print("\n🎉 Cleanup completed successfully!")
        print("\n🔄 Next steps:")
        print("1. Restart your API server")
        print("2. Check /api/displays to verify duplicates are gone")
        print("3. Consider updating display client registration logic")
    else:
        print("\n❌ Cleanup failed!")
        sys.exit(1)
