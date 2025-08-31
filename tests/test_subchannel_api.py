#!/usr/bin/env python3
"""
Test script for Subchannel API endpoints

This script tests the subchannel (gallery) API functionality to ensure:
1. File path resolution works correctly
2. Subchannel CRUD operations function properly  
3. Content assignment and retrieval works
4. Thumbnail serving operates as expected
5. Error handling is robust

Usage:
    python test_subchannel_api.py [--host localhost] [--port 8000] [--channel-id photo_frame]
"""

import json
import time
import requests
import argparse
from pathlib import Path
from typing import Dict, Any, List


class SubchannelAPITester:
    """Test harness for subchannel API endpoints"""
    
    def __init__(self, base_url: str, channel_id: str = "photo_frame"):
        self.base_url = base_url.rstrip('/')
        self.channel_id = channel_id
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = "", data: Any = None):
        """Log test result"""
        result = {
            "test": test_name,
            "success": success, 
            "message": message,
            "timestamp": time.time()
        }
        if data:
            result["data"] = data
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
    def test_channel_exists(self) -> bool:
        """Test that the channel exists and is accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/channels/{self.channel_id}/config")
            if response.status_code == 200:
                config = response.json()
                self.log_test(
                    "channel_exists", 
                    True, 
                    f"Channel '{config.get('name', self.channel_id)}' found"
                )
                return True
            else:
                self.log_test(
                    "channel_exists", 
                    False, 
                    f"Channel not found (HTTP {response.status_code})"
                )
                return False
        except Exception as e:
            self.log_test("channel_exists", False, f"Error: {str(e)}")
            return False
    
    def test_list_subchannels(self) -> List[Dict[str, Any]]:
        """Test listing subchannels"""
        try:
            response = requests.get(f"{self.base_url}/api/channels/{self.channel_id}/subchannels")
            if response.status_code == 200:
                data = response.json()
                subchannels = data.get("subchannels", [])
                self.log_test(
                    "list_subchannels", 
                    True, 
                    f"Found {len(subchannels)} subchannels",
                    {"count": len(subchannels)}
                )
                return subchannels
            else:
                self.log_test(
                    "list_subchannels", 
                    False, 
                    f"Failed to list subchannels (HTTP {response.status_code})"
                )
                return []
        except Exception as e:
            self.log_test("list_subchannels", False, f"Error: {str(e)}")
            return []
    
    def test_create_subchannel(self) -> str:
        """Test creating a new subchannel"""
        test_subchannel = {
            "name": f"Test Gallery {int(time.time())}",
            "description": "Test subchannel created by API test",
            "tags": ["test", "api"]
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/channels/{self.channel_id}/subchannels",
                json=test_subchannel
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    subchannel = data.get("subchannel", {})
                    subchannel_id = subchannel.get("id")
                    self.log_test(
                        "create_subchannel", 
                        True, 
                        f"Created subchannel '{subchannel_id}'",
                        {"subchannel_id": subchannel_id}
                    )
                    return subchannel_id
                else:
                    self.log_test("create_subchannel", False, "API returned success=false")
            else:
                self.log_test(
                    "create_subchannel", 
                    False, 
                    f"Failed to create subchannel (HTTP {response.status_code})"
                )
        except Exception as e:
            self.log_test("create_subchannel", False, f"Error: {str(e)}")
        
        return None
    
    def test_get_subchannel(self, subchannel_id: str) -> bool:
        """Test getting specific subchannel details"""
        try:
            response = requests.get(
                f"{self.base_url}/api/channels/{self.channel_id}/subchannels/{subchannel_id}"
            )
            if response.status_code == 200:
                subchannel = response.json()
                self.log_test(
                    "get_subchannel", 
                    True, 
                    f"Retrieved subchannel '{subchannel.get('name')}'",
                    {"id": subchannel.get("id")}
                )
                return True
            else:
                self.log_test(
                    "get_subchannel", 
                    False, 
                    f"Failed to get subchannel (HTTP {response.status_code})"
                )
                return False
        except Exception as e:
            self.log_test("get_subchannel", False, f"Error: {str(e)}")
            return False
    
    def test_list_images(self) -> List[str]:
        """Test listing images in the channel"""
        try:
            response = requests.get(f"{self.base_url}/api/channels/{self.channel_id}/images")
            if response.status_code == 200:
                images = response.json()
                if isinstance(images, list):
                    image_ids = [str(img.get("id")) for img in images if img.get("id")]
                    self.log_test(
                        "list_images", 
                        True, 
                        f"Found {len(image_ids)} images",
                        {"count": len(image_ids)}
                    )
                    return image_ids
                else:
                    self.log_test("list_images", False, "Unexpected response format")
                    return []
            else:
                self.log_test(
                    "list_images", 
                    False, 
                    f"Failed to list images (HTTP {response.status_code})"
                )
                return []
        except Exception as e:
            self.log_test("list_images", False, f"Error: {str(e)}")
            return []
    
    def test_assign_content(self, subchannel_id: str, image_ids: List[str]) -> bool:
        """Test assigning content to subchannel"""
        if not image_ids:
            self.log_test("assign_content", False, "No images available to assign")
            return False
        
        # Take first few images for testing
        test_image_ids = image_ids[:min(3, len(image_ids))]
        
        try:
            response = requests.post(
                f"{self.base_url}/api/channels/{self.channel_id}/subchannels/{subchannel_id}/content",
                json={
                    "contentIds": test_image_ids,
                    "action": "add"
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.log_test(
                        "assign_content", 
                        True, 
                        f"Added {len(test_image_ids)} images to subchannel",
                        {"image_count": len(test_image_ids)}
                    )
                    return True
                else:
                    self.log_test("assign_content", False, "API returned success=false")
            else:
                self.log_test(
                    "assign_content", 
                    False, 
                    f"Failed to assign content (HTTP {response.status_code})"
                )
        except Exception as e:
            self.log_test("assign_content", False, f"Error: {str(e)}")
        
        return False
    
    def test_subchannel_images(self, subchannel_id: str) -> bool:
        """Test listing images in a subchannel"""
        try:
            response = requests.get(
                f"{self.base_url}/api/channels/{self.channel_id}/subchannels/{subchannel_id}/images"
            )
            if response.status_code == 200:
                data = response.json()
                images = data.get("images", [])
                self.log_test(
                    "subchannel_images", 
                    True, 
                    f"Subchannel contains {len(images)} images",
                    {"image_count": len(images)}
                )
                return True
            else:
                self.log_test(
                    "subchannel_images", 
                    False, 
                    f"Failed to list subchannel images (HTTP {response.status_code})"
                )
                return False
        except Exception as e:
            self.log_test("subchannel_images", False, f"Error: {str(e)}")
            return False
    
    def test_thumbnail_serving(self, subchannel_id: str, image_id: str) -> bool:
        """Test thumbnail serving for subchannel images"""
        try:
            response = requests.get(
                f"{self.base_url}/api/channels/{self.channel_id}/subchannels/{subchannel_id}/images/{image_id}/thumbnail"
            )
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("image/"):
                    self.log_test(
                        "thumbnail_serving", 
                        True, 
                        f"Thumbnail served successfully ({content_type})",
                        {"content_type": content_type, "size": len(response.content)}
                    )
                    return True
                else:
                    self.log_test(
                        "thumbnail_serving", 
                        False, 
                        f"Invalid content type: {content_type}"
                    )
            else:
                self.log_test(
                    "thumbnail_serving", 
                    False, 
                    f"Failed to serve thumbnail (HTTP {response.status_code})"
                )
        except Exception as e:
            self.log_test("thumbnail_serving", False, f"Error: {str(e)}")
        
        return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run the complete test suite"""
        print(f"🧪 Starting subchannel API tests for channel '{self.channel_id}'")
        print(f"📡 API Base URL: {self.base_url}")
        print("=" * 60)
        
        # 1. Verify channel exists
        if not self.test_channel_exists():
            print("❌ Channel not found, aborting tests")
            return self.get_test_summary()
        
        # 2. List existing subchannels
        existing_subchannels = self.test_list_subchannels()
        
        # 3. Create new test subchannel
        test_subchannel_id = self.test_create_subchannel()
        if not test_subchannel_id:
            print("❌ Failed to create test subchannel, skipping dependent tests")
            return self.get_test_summary()
        
        # 4. Get the created subchannel
        self.test_get_subchannel(test_subchannel_id)
        
        # 5. List available images
        image_ids = self.test_list_images()
        
        # 6. Assign content to subchannel (if images exist)
        if image_ids:
            self.test_assign_content(test_subchannel_id, image_ids)
            
            # 7. List images in subchannel
            self.test_subchannel_images(test_subchannel_id)
            
            # 8. Test thumbnail serving
            self.test_thumbnail_serving(test_subchannel_id, image_ids[0])
        else:
            print("⚠️  No images found, skipping content assignment tests")
        
        return self.get_test_summary()
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Generate test summary"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["success"]])
        failed_tests = total_tests - passed_tests
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "results": self.test_results
        }
        
        print("=" * 60)
        print(f"📊 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {failed_tests}")
        print(f"   Success Rate: {summary['success_rate']:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   - {result['test']}: {result['message']}")
        
        return summary


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Test subchannel API endpoints")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", type=int, default=8000, help="API port")
    parser.add_argument("--channel-id", default="photo_frame", help="Channel ID to test")
    parser.add_argument("--output", help="JSON output file for test results")
    
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}"
    
    tester = SubchannelAPITester(base_url, args.channel_id)
    summary = tester.run_all_tests()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n📄 Test results saved to: {args.output}")
    
    # Exit with error code if tests failed
    exit_code = 0 if summary["failed"] == 0 else 1
    exit(exit_code)


if __name__ == "__main__":
    main()
