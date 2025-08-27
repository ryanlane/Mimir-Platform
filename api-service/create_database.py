#!/usr/bin/env python3
"""
Database Creation Script
Creates all tables from SQLAlchemy models for the refactored Mimir API
"""
import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.db.base import engine, Base
from app.db.models import Channel, DisplayClient, Scene, Overlay  # Import all models
from app.config import settings

def create_database():
    """Create all database tables from models"""
    print(f"🗄️  Creating database schema...")
    print(f"📊 Database URL: {settings.database_url}")
    
    # Drop all existing tables (fresh start)
    print("🧹 Dropping existing tables...")
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables from models
    print("🔨 Creating new tables from models...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Database schema created successfully!")
    print("\nCreated tables:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")

if __name__ == "__main__":
    create_database()
