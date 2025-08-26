#!/usr/bin/env python3
"""
Database Migration: Add Enhanced Display Client Fields
==================================================

This script adds the new fields required for enhanced display client capabilities:
- hostname: System hostname (e.g., "colorframe05")
- webhook_port: Port for webhook server (e.g., 8080) 
- redis_distribution: Boolean flag for Redis distribution support
- content_claiming: Boolean flag for content claiming support

Usage:
    python migrate_display_enhancements.py

The script will:
1. Check if the new columns already exist
2. Add missing columns safely
3. Provide detailed output of changes made
"""

import sqlite3
import os
import sys
from datetime import datetime

# Database configuration
DATABASE_URL = "sqlite:///./app.db"
DB_PATH = "./app.db"

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in the given table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_column_if_not_exists(cursor, table_name, column_name, column_definition):
    """Add a column if it doesn't already exist"""
    if not check_column_exists(cursor, table_name, column_name):
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        cursor.execute(sql)
        print(f"✅ Added column: {table_name}.{column_name}")
        return True
    else:
        print(f"⏭️  Column already exists: {table_name}.{column_name}")
        return False

def run_migration():
    """Execute the database migration"""
    
    print("🚀 Starting Enhanced Display Client Migration")
    print("=" * 60)
    print(f"📅 Migration Date: {datetime.now().isoformat()}")
    print(f"🗄️  Database: {DB_PATH}")
    print()
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file not found: {DB_PATH}")
        print("   Make sure you're running this from the correct directory")
        print("   and that the API server has been started at least once.")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if display_clients table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='display_clients'")
        if not cursor.fetchone():
            print("❌ display_clients table not found!")
            print("   Make sure the API server has been started to create initial tables.")
            return False
        
        print("📋 Checking existing schema...")
        
        # Show current columns
        cursor.execute("PRAGMA table_info(display_clients)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Existing columns: {', '.join(existing_columns)}")
        print()
        
        # Track changes
        changes_made = 0
        
        print("🔧 Adding new columns...")
        
        # Add hostname column
        if add_column_if_not_exists(cursor, "display_clients", "hostname", "VARCHAR(255)"):
            changes_made += 1
            
        # Add webhook_port column  
        if add_column_if_not_exists(cursor, "display_clients", "webhook_port", "INTEGER"):
            changes_made += 1
            
        # Add redis_distribution column
        if add_column_if_not_exists(cursor, "display_clients", "redis_distribution", "BOOLEAN DEFAULT 0"):
            changes_made += 1
            
        # Add content_claiming column
        if add_column_if_not_exists(cursor, "display_clients", "content_claiming", "BOOLEAN DEFAULT 0"):
            changes_made += 1
        
        # Commit changes
        conn.commit()
        
        print()
        print("📋 Updated schema:")
        cursor.execute("PRAGMA table_info(display_clients)")
        updated_columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 New columns: {', '.join(updated_columns)}")
        
        print()
        print("=" * 60)
        if changes_made > 0:
            print(f"✅ Migration completed successfully!")
            print(f"📝 {changes_made} column(s) added to display_clients table")
        else:
            print("✅ Migration completed - no changes needed")
            print("📝 All columns already exist")
            
        print()
        print("🔄 Next steps:")
        print("1. Restart your API server to load the updated schema")
        print("2. Test display registration with new fields")
        print("3. Verify webhook and mDNS functionality")
        
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
    print("\n🔍 Verifying migration...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check all required columns exist
        required_columns = ['hostname', 'webhook_port', 'redis_distribution', 'content_claiming']
        cursor.execute("PRAGMA table_info(display_clients)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        missing_columns = [col for col in required_columns if col not in existing_columns]
        
        if not missing_columns:
            print("✅ All required columns are present")
            
            # Test inserting a sample record to verify schema
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO display_clients 
                    (id, name, hostname, webhook_port, redis_distribution, content_claiming) 
                    VALUES ('test-migration', 'Test Display', 'testframe01', 8080, 1, 1)
                """)
                
                # Clean up test record
                cursor.execute("DELETE FROM display_clients WHERE id = 'test-migration'")
                conn.commit()
                
                print("✅ Schema validation successful - can insert records with new fields")
                return True
                
            except sqlite3.Error as e:
                print(f"❌ Schema validation failed: {e}")
                return False
        else:
            print(f"❌ Missing columns: {', '.join(missing_columns)}")
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("Enhanced Display Client Database Migration")
    print("==========================================")
    
    # Check if we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ This script should be run from the api-service directory")
        print("   where main.py is located")
        sys.exit(1)
    
    # Run migration
    success = run_migration()
    
    if success:
        # Verify migration
        verify_success = verify_migration()
        
        if verify_success:
            print("\n🎉 Migration completed successfully!")
            print("   Your database is ready for enhanced display client features.")
        else:
            print("\n⚠️  Migration completed but verification failed")
            print("   Please check the database manually")
    else:
        print("\n❌ Migration failed!")
        print("   Please check the error messages above")
        sys.exit(1)
