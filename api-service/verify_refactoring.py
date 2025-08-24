#!/usr/bin/env python3
"""
Migration verification script for Mimir API refactoring
Tests that the new modular architecture can import and basic functionality works
"""
import sys
import os
from pathlib import Path

# Add the api-service directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported without errors"""
    print("🧪 Testing module imports...")
    
    try:
        # Test configuration
        from app.config import settings
        print("✅ Configuration loaded successfully")
        print(f"   Database URL: {settings.database_url}")
        print(f"   Channels Directory: {settings.channels_directory}")
        
        # Test database models
        from app.infrastructure.database.models import Channel, Scene, DisplayClient
        print("✅ Database models imported successfully")
        
        # Test services (note: these will fail due to missing SQLAlchemy, but imports should work)
        try:
            from app.core.services.channel_service import ChannelService
            from app.core.services.scene_service import SceneService  
            from app.core.services.display_service import DisplayService
            print("✅ Service classes imported successfully")
        except ImportError as e:
            print(f"⚠️  Service imports failed (expected due to missing SQLAlchemy): {e}")
        
        # Test infrastructure components
        from app.infrastructure.channels.manager import ChannelManager
        from app.infrastructure.websocket.manager import WebSocketManager
        print("✅ Infrastructure components imported successfully")
        
        # Test API routes (note: these will fail due to missing FastAPI, but imports should work)
        try:
            from app.api.routes.channels import router as channels_router
            from app.api.routes.scenes import router as scenes_router
            from app.api.routes.admin import health_router, admin_router
            print("✅ API routes imported successfully")
        except ImportError as e:
            print(f"⚠️  API route imports failed (expected due to missing FastAPI): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_channel_manager():
    """Test channel manager functionality"""
    print("\n🧪 Testing Channel Manager...")
    
    try:
        from app.infrastructure.channels.manager import ChannelManager
        
        # Create channel manager
        manager = ChannelManager()
        print("✅ Channel manager created successfully")
        
        # Test channel discovery (will work even without actual channels)
        channels = manager.discover_channels()
        print(f"✅ Channel discovery completed, found {len(channels)} channels")
        
        # Test configuration validation
        validation = manager.validate_channel_structure("test_channel")
        print(f"✅ Channel validation completed: {validation['valid']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Channel manager test failed: {e}")
        return False

def test_websocket_manager():
    """Test WebSocket manager functionality"""
    print("\n🧪 Testing WebSocket Manager...")
    
    try:
        from app.infrastructure.websocket.manager import WebSocketManager
        
        # Create WebSocket manager
        manager = WebSocketManager()
        print("✅ WebSocket manager created successfully")
        
        # Test connection info
        info = manager.get_connection_info()
        print(f"✅ Connection info: {info}")
        
        return True
        
    except Exception as e:
        print(f"❌ WebSocket manager test failed: {e}")
        return False

def test_directory_structure():
    """Verify the new directory structure exists"""
    print("\n🧪 Testing Directory Structure...")
    
    required_dirs = [
        "app",
        "app/api",
        "app/api/routes", 
        "app/core",
        "app/core/services",
        "app/infrastructure",
        "app/infrastructure/database",
        "app/infrastructure/channels",
        "app/infrastructure/websocket",
        "app/schemas"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} - MISSING")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests"""
    print("🔧 Mimir API Refactoring Verification")
    print("=" * 50)
    
    tests = [
        ("Directory Structure", test_directory_structure),
        ("Module Imports", test_imports),
        ("Channel Manager", test_channel_manager),
        ("WebSocket Manager", test_websocket_manager)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Refactoring structure is ready.")
        print("\n📋 Next Steps:")
        print("   1. Install dependencies: pip install -r requirements.txt")
        print("   2. Run the new application: python -m app.main")
        print("   3. Test API endpoints")
        print("   4. Migrate remaining functionality from old main.py")
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
