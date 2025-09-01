#!/usr/bin/env python3
"""
Simple import test to check for missing dependencies
"""
import sys
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

def test_imports():
    """Test basic imports"""
    print("Testing imports...")
    
    try:
        print("1. Testing APScheduler...")
        from apscheduler.schedulers.background import BackgroundScheduler
        print("   ✅ APScheduler import OK")
    except Exception as e:
        print(f"   ❌ APScheduler import failed: {e}")
        return False
    
    try:
        print("2. Testing Prometheus client...")
        from prometheus_client import Counter, generate_latest
        print("   ✅ Prometheus client import OK")
    except Exception as e:
        print(f"   ❌ Prometheus client import failed: {e}")
        return False
    
    try:
        print("3. Testing app core modules...")
        from app.config import settings
        print("   ✅ App config import OK")
    except Exception as e:
        print(f"   ❌ App config import failed: {e}")
        return False
    
    try:
        print("4. Testing app metrics module...")
        from app.core.metrics import metrics, setup_metrics
        print("   ✅ App metrics import OK")
    except Exception as e:
        print(f"   ❌ App metrics import failed: {e}")
        return False
    
    print("\n✅ All essential imports successful!")
    return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
