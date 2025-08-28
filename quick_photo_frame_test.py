#!/usr/bin/env python3
"""
Quick Photo Frame Channel Test Runner

This script quickly tests the photo frame channel API endpoints
to validate the fixes we've implemented.
"""

import sys
import os

# Add the current directory to the path so we can import our test module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_all_channel_endpoints import ChannelAPITester

def quick_photo_frame_test():
    """Run a quick test of the photo frame channel"""
    print("🚀 Quick Photo Frame Channel Test")
    print("=" * 40)
    
    # Test against localhost:8000 by default
    base_url = "http://localhost:8000"
    
    tester = ChannelAPITester(base_url)
    
    try:
        # Run photo frame specific tests
        print("Testing photo frame channel...")
        results = tester.test_photo_frame_specific()
        
        # Quick summary
        total_tests = len(tester.test_results)
        passed = len([r for r in tester.test_results if r["success"]])
        
        print(f"\n📊 Quick Summary:")
        print(f"   Tests: {passed}/{total_tests} passed")
        print(f"   Success Rate: {(passed/total_tests*100):.1f}%")
        
        if passed == total_tests:
            print("🎉 All photo frame tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed. Run the full test suite for details:")
            print("   python test_all_channel_endpoints.py --photo-frame-only")
            return 1
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("\nMake sure the mimir-api server is running on localhost:8000")
        return 1

if __name__ == "__main__":
    sys.exit(quick_photo_frame_test())
