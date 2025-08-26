#!/usr/bin/env python3
"""
Database Rollback: Remove Enhanced Display Client Fields
======================================================

This script removes the enhanced display client fields if needed:
- hostname
- webhook_port  
- redis_distribution
- content_claiming

⚠️  WARNING: This will remove data from these columns permanently!

Usage:
    python rollback_display_enhancements.py

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

def backup_database():
    """Create a backup of the database before rollback"""
    backup_path = f"app.db.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return None

def rollback_migration():
    """Remove the enhanced display client columns"""
    
    print("🔄 Starting Enhanced Display Client Rollback")
    print("=" * 60)
    print(f"📅 Rollback Date: {datetime.now().isoformat()}")
    print(f"🗄️  Database: {DB_PATH}")
    print()
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file not found: {DB_PATH}")
        return False
    
    # Confirm rollback
    print("⚠️  WARNING: This will permanently remove enhanced display client data!")
    print("   Columns to be removed: hostname, webhook_port, redis_distribution, content_claiming")
    print()
    
    confirm = input("Are you sure you want to proceed? (type 'yes' to confirm): ").strip().lower()
    if confirm != 'yes':
        print("❌ Rollback cancelled")
        return False
    
    # Create backup
    backup_path = backup_database()
    if not backup_path:
        proceed = input("Backup failed. Continue anyway? (type 'yes' to proceed): ").strip().lower()
        if proceed != 'yes':
            print("❌ Rollback cancelled")
            return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if display_clients table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='display_clients'")
        if not cursor.fetchone():
            print("❌ display_clients table not found!")
            return False
        
        print("📋 Current schema:")
        cursor.execute("PRAGMA table_info(display_clients)")
        current_columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Columns: {', '.join(current_columns)}")
        print()
        
        # SQLite doesn't support DROP COLUMN directly
        # We need to recreate the table without the new columns
        
        print("🔧 Recreating table without enhanced columns...")
        
        # Get the original table structure (without our new columns)
        original_columns = [col for col in current_columns 
                          if col not in ['hostname', 'webhook_port', 'redis_distribution', 'content_claiming']]
        
        if len(original_columns) == len(current_columns):
            print("✅ No enhanced columns found - nothing to rollback")
            return True
        
        # Create new table without enhanced columns
        cursor.execute(f"""
            CREATE TABLE display_clients_backup AS 
            SELECT {', '.join(original_columns)} 
            FROM display_clients
        """)
        
        # Drop original table
        cursor.execute("DROP TABLE display_clients")
        
        # Rename backup to original
        cursor.execute("ALTER TABLE display_clients_backup RENAME TO display_clients")
        
        # Commit changes
        conn.commit()
        
        print("📋 Updated schema:")
        cursor.execute("PRAGMA table_info(display_clients)")
        final_columns = [row[1] for row in cursor.fetchall()]
        print(f"📊 Remaining columns: {', '.join(final_columns)}")
        
        removed_columns = [col for col in current_columns if col not in final_columns]
        
        print()
        print("=" * 60)
        print(f"✅ Rollback completed successfully!")
        print(f"📝 Removed columns: {', '.join(removed_columns)}")
        
        if backup_path:
            print(f"💾 Backup available at: {backup_path}")
        
        print()
        print("🔄 Next steps:")
        print("1. Restart your API server")
        print("2. Update your code to remove references to removed fields")
        print("3. Test that basic display functionality still works")
        
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
    print("Enhanced Display Client Database Rollback")
    print("=========================================")
    
    # Check if we're in the right directory
    if not os.path.exists("main.py"):
        print("❌ This script should be run from the api-service directory")
        print("   where main.py is located")
        sys.exit(1)
    
    # Run rollback
    success = rollback_migration()
    
    if success:
        print("\n🎉 Rollback completed successfully!")
    else:
        print("\n❌ Rollback failed!")
        sys.exit(1)
