#!/usr/bin/env python3
"""
Database Migration: Add Display Type Fields
===========================================

This script adds the new display type and discovery fields to support
both manually registered and auto-discovered displays:

- display_type: "registered" or "discovered"
- discovery_method: "manual", "mdns", "webhook"
- auto_discovered: boolean flag

Usage:
    python migrate_display_types.py

Before running this script, consider backing up your database:
    cp app.db app.db.backup
"""

import sqlite3
import os
import sys
from datetime import datetime

# Database configuration  
DB_PATH = "./app.db"

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in the given table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_display_type_fields():
    """Add the new display type and discovery fields"""
    
    print("🔧 Adding Display Type and Discovery Fields")
    print("=" * 60)
    print(f"📅 Migration Date: {datetime.now().isoformat()}")
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
        
        print("📋 Checking existing schema...")
        cursor.execute("PRAGMA table_info(display_clients)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Current columns: {len(existing_columns)} fields")
        print()
        
        print("🔧 Adding new display type columns...")
        
        # Add display_type column
        if not column_exists(cursor, 'display_clients', 'display_type'):
            cursor.execute("""
                ALTER TABLE display_clients 
                ADD COLUMN display_type TEXT DEFAULT 'registered'
            """)
            print("✅ Added column: display_type")
        else:
            print("⏭️  Column already exists: display_clients.display_type")
        
        # Add discovery_method column
        if not column_exists(cursor, 'display_clients', 'discovery_method'):
            cursor.execute("""
                ALTER TABLE display_clients 
                ADD COLUMN discovery_method TEXT DEFAULT 'manual'
            """)
            print("✅ Added column: discovery_method")
        else:
            print("⏭️  Column already exists: display_clients.discovery_method")
        
        # Add auto_discovered column
        if not column_exists(cursor, 'display_clients', 'auto_discovered'):
            cursor.execute("""
                ALTER TABLE display_clients 
                ADD COLUMN auto_discovered BOOLEAN DEFAULT 0
            """)
            print("✅ Added column: auto_discovered")
        else:
            print("⏭️  Column already exists: display_clients.auto_discovered")
        
        # Update existing records to have proper defaults
        print()
        print("🔄 Updating existing records with default values...")
        
        cursor.execute("""
            UPDATE display_clients 
            SET display_type = 'registered',
                discovery_method = 'manual',
                auto_discovered = 0
            WHERE display_type IS NULL 
               OR discovery_method IS NULL 
               OR auto_discovered IS NULL
        """)
        
        updated_rows = cursor.rowcount
        print(f"📝 Updated {updated_rows} existing records with defaults")
        
        # Commit changes
        conn.commit()
        
        print()
        print("📋 Updated schema:")
        cursor.execute("PRAGMA table_info(display_clients)")
        final_columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Total columns: {len(final_columns)} fields")
        
        new_columns = [col for col in final_columns if col not in existing_columns]
        if new_columns:
            print(f"➕ New columns added: {', '.join(new_columns)}")
        
        print()
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print()
        print("🎯 Display Types Supported:")
        print("   • registered: Manually registered displays")
        print("   • discovered: Auto-discovered via mDNS")
        print()
        print("🔍 Discovery Methods:")
        print("   • manual: Manually registered by user")
        print("   • mdns: Auto-discovered via mDNS/Bonjour") 
        print("   • webhook: Discovered via webhook registration")
        print()
        print("🔄 Next steps:")
        print("1. Restart your API server")
        print("2. Test mDNS discovery: GET /api/displays/discover")
        print("3. Check display list shows display types")
        
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

def verify_migration():
    """Verify the migration was successful"""
    
    print()
    print("🔍 Verifying migration...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Test inserting a record with new fields
        test_id = "test-display-type-migration"
        cursor.execute("""
            INSERT OR REPLACE INTO display_clients (
                id, name, display_type, discovery_method, auto_discovered, 
                orientation, is_online, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_id, "Test Display Type", "discovered", "mdns", True,
            "landscape", False, datetime.now().isoformat()
        ))
        
        # Read it back
        cursor.execute("""
            SELECT display_type, discovery_method, auto_discovered 
            FROM display_clients WHERE id = ?
        """, (test_id,))
        
        result = cursor.fetchone()
        if result and result[0] == "discovered" and result[1] == "mdns" and result[2] == 1:
            print("✅ Schema validation successful - can insert/read new fields")
            
            # Clean up test record
            cursor.execute("DELETE FROM display_clients WHERE id = ?", (test_id,))
            conn.commit()
            
            return True
        else:
            print("❌ Schema validation failed")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("Display Type and Discovery Fields Migration")
    print("==========================================")
    
    # Check if we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ This script should be run from the api-service directory")
        print("   where main.py is located")
        sys.exit(1)
    
    # Run migration
    success = add_display_type_fields()
    
    if success:
        # Verify migration
        verification_success = verify_migration()
        
        if verification_success:
            print("\n🎉 Migration completed and verified successfully!")
        else:
            print("\n⚠️  Migration completed but verification failed")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
