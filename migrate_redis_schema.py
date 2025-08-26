#!/usr/bin/env python3
"""
Database Migration Script for Redis Integration

Adds the new columns needed for Redis distribution to the existing database:
- scenes.distribution_mode
- scenes.content_hash 
- scenes.content_epoch

Also creates the new tables:
- distribution_queues
- content_leases
"""

import sqlite3
import sys
from pathlib import Path


def migrate_database(db_path: str):
    """Apply Redis integration migrations to the database"""
    
    print(f"Migrating database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if migrations are needed
        cursor.execute("PRAGMA table_info(scenes)")
        columns = [col[1] for col in cursor.fetchall()]
        
        needs_migration = 'distribution_mode' not in columns
        
        if not needs_migration:
            print("✅ Database already has Redis integration columns")
            return True
        
        print("🔄 Adding Redis integration columns to scenes table...")
        
        # Add new columns to scenes table
        migrations = [
            "ALTER TABLE scenes ADD COLUMN distribution_mode VARCHAR(20) DEFAULT 'MIRROR'",
            "ALTER TABLE scenes ADD COLUMN content_hash VARCHAR(64)",
            "ALTER TABLE scenes ADD COLUMN content_epoch VARCHAR(32)"
        ]
        
        for migration in migrations:
            try:
                cursor.execute(migration)
                print(f"   ✅ {migration}")
            except sqlite3.Error as e:
                if "duplicate column name" in str(e):
                    print(f"   ⚠️  Column already exists: {migration}")
                else:
                    raise e
        
        # Create distribution_queues table
        print("🔄 Creating distribution_queues table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS distribution_queues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scene_id VARCHAR(36) NOT NULL,
                display_id VARCHAR(100) NOT NULL,
                content_id VARCHAR(100) NOT NULL,
                distribution_mode VARCHAR(20) NOT NULL,
                claimed_at DATETIME NOT NULL,
                completed_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for distribution_queues
        indexes_dq = [
            "CREATE INDEX IF NOT EXISTS idx_dq_scene_id ON distribution_queues(scene_id)",
            "CREATE INDEX IF NOT EXISTS idx_dq_display_id ON distribution_queues(display_id)",
            "CREATE INDEX IF NOT EXISTS idx_dq_claimed_at ON distribution_queues(claimed_at)",
            "CREATE INDEX IF NOT EXISTS idx_dq_completed_at ON distribution_queues(completed_at)"
        ]
        
        for index_sql in indexes_dq:
            cursor.execute(index_sql)
        
        print("   ✅ distribution_queues table created")
        
        # Create content_leases table
        print("🔄 Creating content_leases table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_leases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scene_id VARCHAR(36) NOT NULL,
                display_id VARCHAR(100) NOT NULL,
                content_id VARCHAR(100) NOT NULL,
                lease_start DATETIME NOT NULL,
                lease_end DATETIME NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for content_leases
        indexes_cl = [
            "CREATE INDEX IF NOT EXISTS idx_cl_scene_id ON content_leases(scene_id)",
            "CREATE INDEX IF NOT EXISTS idx_cl_display_id ON content_leases(display_id)", 
            "CREATE INDEX IF NOT EXISTS idx_cl_lease_end ON content_leases(lease_end)",
            "CREATE INDEX IF NOT EXISTS idx_cl_status ON content_leases(status)"
        ]
        
        for index_sql in indexes_cl:
            cursor.execute(index_sql)
            
        print("   ✅ content_leases table created")
        
        # Commit changes
        conn.commit()
        
        print("✅ Database migration completed successfully!")
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(scenes)")
        columns = [col[1] for col in cursor.fetchall()]
        
        required_columns = ['distribution_mode', 'content_hash', 'content_epoch']
        missing = [col for col in required_columns if col not in columns]
        
        if missing:
            print(f"❌ Migration verification failed. Missing columns: {missing}")
            return False
        
        print("✅ Migration verification passed!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def find_database():
    """Find the database file"""
    
    # Common locations for Mimir database
    possible_paths = [
        "mimir.db",
        "api-service/mimir.db", 
        "api/mimir.db",
        "/app/mimir.db",
        "/var/lib/mimir/mimir.db"
    ]
    
    for path in possible_paths:
        if Path(path).exists():
            return str(Path(path).absolute())
    
    return None


def main():
    """Main migration function"""
    
    print("Redis Integration Database Migration")
    print("=" * 40)
    
    # Allow specifying database path as argument
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = find_database()
    
    if not db_path:
        print("❌ Could not find database file.")
        print("\nUsage:")
        print("  python migrate_redis_schema.py [database_path]")
        print("\nOr run from a directory containing mimir.db")
        return False
    
    if not Path(db_path).exists():
        print(f"❌ Database file not found: {db_path}")
        return False
    
    # Backup recommendation
    print(f"📁 Database found: {db_path}")
    print("⚠️  Recommendation: Backup your database before proceeding!")
    print(f"   cp {db_path} {db_path}.backup")
    
    # Run migration
    success = migrate_database(db_path)
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("Your Mimir API now supports Redis integration features:")
        print("- Multi-display distribution modes")
        print("- Content set management")
        print("- Distribution queue tracking")
    else:
        print("\n❌ Migration failed!")
        print("Check the error messages above and try again.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
