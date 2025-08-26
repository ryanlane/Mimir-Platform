#!/usr/bin/env python3
"""
Database Cleanup Script

Removes the problematic tables and re-runs the migration cleanly.
"""

import sqlite3
import sys
from pathlib import Path


def cleanup_database(db_path: str):
    """Clean up partially created tables"""
    
    print(f"Cleaning up database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Drop tables if they exist (in reverse dependency order)
        tables_to_drop = [
            "content_leases",
            "distribution_queues"
        ]
        
        for table in tables_to_drop:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"   ✅ Dropped table {table}")
            except sqlite3.Error as e:
                print(f"   ⚠️  Could not drop {table}: {e}")
        
        # Drop any indexes that might be hanging around
        indexes_to_drop = [
            "idx_dq_scene_id",
            "idx_dq_display_id", 
            "idx_dq_claimed_at",
            "idx_dq_completed_at",
            "idx_cl_scene_id",
            "idx_cl_display_id",
            "idx_cl_lease_end",
            "idx_cl_status"
        ]
        
        for index in indexes_to_drop:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {index}")
                print(f"   ✅ Dropped index {index}")
            except sqlite3.Error as e:
                print(f"   ⚠️  Could not drop index {index}: {e}")
        
        conn.commit()
        print("✅ Database cleanup completed!")
        return True
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    """Main cleanup function"""
    
    print("Database Cleanup for Redis Integration")
    print("=" * 40)
    
    # Allow specifying database path as argument
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "app.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database file not found: {db_path}")
        return False
    
    print(f"📁 Database found: {db_path}")
    
    # Run cleanup
    success = cleanup_database(db_path)
    
    if success:
        print("\n🎉 Cleanup completed successfully!")
        print("Now run the migration script again:")
        print(f"   python3 migrate_redis_schema.py {db_path}")
    else:
        print("\n❌ Cleanup failed!")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
