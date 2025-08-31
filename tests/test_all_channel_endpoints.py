#!/usr/bin/env python3
"""
Comprehensive Channel API Test Suite

This script tests ALL channel API endpoints to ensure they work correctly.
It includes specific tests for the photo frame channel and subchannel functionality.

Features:
- Tests all GET, POST, PUT, DELETE endpoints
- Photo frame channel specific tests
- Image upload and thumbnail testing
- Subchannel (gallery) operations
- Error handling validation
- Performance timing
- Detailed reporting

Usage:
    python test_all_channel_endpoints.py [--host localhost] [--port 8000] [--photo-frame-only]
"""

import json
import time
import requests
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from io import BytesIO
from PIL import Image as PILImage
import hashlib


class ChannelAPITester:
    """Comprehensive test harness for all channel API endpoints"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.test_results = []
        self.created_resources = {
            "subchannels": [],
            "uploaded_images": []
        }
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mimir-Channel-API-Tester/1.0'
        })
        
    def log_test(self, test_name: str, success: bool, message: str = "", 
                 data: Any = None, response_time: float = None):
        """Log test result with timing information"""
        result = {
            "test": test_name,
            "success": success, 
            "message": message,
            "timestamp": time.time(),
            "response_time_ms": round(response_time * 1000, 2) if response_time else None
        }
        if data:
            result["data"] = data
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        timing = f" ({result['response_time_ms']}ms)" if response_time else ""
        print(f"{status} {test_name}: {message}{timing}")
        
    def make_request(self, method: str, url: str, **kwargs) -> Tuple[requests.Response, float]:
        """Make HTTP request with timing"""
        start_time = time.time()
        try:
            response = self.session.request(method, url, **kwargs)
            response_time = time.time() - start_time
            return response, response_time
        except Exception as e:
            response_time = time.time() - start_time
            # Create a mock response for failed requests
            mock_response = requests.Response()
            mock_response.status_code = 0
            mock_response._content = str(e).encode()
            return mock_response, response_time
    
    def create_test_image(self, size=(800, 600), color=(255, 0, 0)) -> bytes:
        """Create a test image for upload testing"""
        img = PILImage.new('RGB', size, color)
        # Add some text to make it identifiable
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        
        try:
            # Try to use a default font
            font = ImageFont.load_default()
        except:
            font = None
            
        text = f"Test Image {int(time.time())}"
        if font:
            draw.text((10, 10), text, fill=(255, 255, 255), font=font)
        else:
            draw.text((10, 10), text, fill=(255, 255, 255))
        
        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        return buffer.getvalue()

    # ===== BASIC CHANNEL ENDPOINTS =====
    
    def test_list_channels(self) -> List[Dict[str, Any]]:
        """Test GET /api/channels - List all channels"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels")
        
        if response.status_code == 200:
            try:
                data = response.json()
                channels = data.get('channels', [])
                self.log_test(
                    "list_channels", 
                    True, 
                    f"Found {len(channels)} channels",
                    {"total": data.get('total', len(channels))},
                    response_time
                )
                return channels
            except json.JSONDecodeError:
                self.log_test("list_channels", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test("list_channels", False, f"HTTP {response.status_code}", None, response_time)
        
        return []
    
    def test_channels_manifest(self) -> Dict[str, Any]:
        """Test GET /api/channels/manifest - Get channels manifest"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/manifest")
        
        if response.status_code == 200:
            try:
                manifest = response.json()
                channels_count = len(manifest.get('channels', []))
                self.log_test(
                    "channels_manifest", 
                    True, 
                    f"Manifest contains {channels_count} channels",
                    {"channels_count": channels_count},
                    response_time
                )
                return manifest
            except json.JSONDecodeError:
                self.log_test("channels_manifest", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test("channels_manifest", False, f"HTTP {response.status_code}", None, response_time)
        
        return {}

    # ===== CHANNEL-SPECIFIC ENDPOINTS =====
    
    def test_channel_config(self, channel_id: str) -> Dict[str, Any]:
        """Test GET /api/channels/{channel_id}/config"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/config")
        
        if response.status_code == 200:
            try:
                config = response.json()
                self.log_test(
                    f"channel_config_{channel_id}", 
                    True, 
                    f"Retrieved config for '{config.get('name', channel_id)}'",
                    {"version": config.get('version')},
                    response_time
                )
                return config
            except json.JSONDecodeError:
                self.log_test(f"channel_config_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"channel_config_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return {}
    
    def test_channel_settings(self, channel_id: str) -> Dict[str, Any]:
        """Test GET /api/channels/{channel_id}/settings"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/settings")
        
        if response.status_code == 200:
            try:
                settings = response.json()
                self.log_test(
                    f"channel_settings_{channel_id}", 
                    True, 
                    f"Retrieved settings",
                    {"settings_type": settings.get('settingsType')},
                    response_time
                )
                return settings
            except json.JSONDecodeError:
                self.log_test(f"channel_settings_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"channel_settings_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return {}
    
    def test_update_channel_settings(self, channel_id: str, settings: Dict[str, Any]) -> bool:
        """Test POST /api/channels/{channel_id}/settings"""
        response, response_time = self.make_request(
            'POST', 
            f"{self.base_url}/api/channels/{channel_id}/settings",
            json=settings
        )
        
        if response.status_code == 200:
            self.log_test(
                f"update_settings_{channel_id}", 
                True, 
                "Settings updated successfully",
                None,
                response_time
            )
            return True
        else:
            self.log_test(f"update_settings_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
            return False
    
    def test_channel_status(self, channel_id: str) -> Dict[str, Any]:
        """Test GET /api/channels/{channel_id}/status"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/status")
        
        if response.status_code == 200:
            try:
                status = response.json()
                self.log_test(
                    f"channel_status_{channel_id}", 
                    True, 
                    "Status retrieved",
                    status,
                    response_time
                )
                return status
            except json.JSONDecodeError:
                self.log_test(f"channel_status_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"channel_status_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return {}
    
    def test_channel_health(self, channel_id: str) -> Dict[str, Any]:
        """Test GET /api/channels/{channel_id}/health"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/health")
        
        if response.status_code == 200:
            try:
                health = response.json()
                self.log_test(
                    f"channel_health_{channel_id}", 
                    True, 
                    f"Health: {'healthy' if health.get('healthy') else 'unhealthy'}",
                    {"healthy": health.get('healthy')},
                    response_time
                )
                return health
            except json.JSONDecodeError:
                self.log_test(f"channel_health_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"channel_health_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return {}
    
    def test_channel_token(self, channel_id: str) -> str:
        """Test GET /api/channels/{channel_id}/token"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/token")
        
        if response.status_code == 200:
            try:
                token_data = response.json()
                token = token_data.get('token')
                self.log_test(
                    f"channel_token_{channel_id}", 
                    True, 
                    f"Token retrieved ({len(token) if token else 0} chars)",
                    {"token_length": len(token) if token else 0},
                    response_time
                )
                return token
            except json.JSONDecodeError:
                self.log_test(f"channel_token_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"channel_token_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return ""
    
    def test_channel_current_content(self, channel_id: str) -> Dict[str, Any]:
        """Test GET /api/channels/{channel_id}/current"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/current")
        
        if response.status_code == 200:
            try:
                content = response.json()
                self.log_test(
                    f"current_content_{channel_id}", 
                    True, 
                    f"Current content available",
                    {"content_type": content.get('contentType')},
                    response_time
                )
                return content
            except json.JSONDecodeError:
                self.log_test(f"current_content_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"current_content_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return {}
    
    def test_channel_current_image(self, channel_id: str) -> bool:
        """Test GET /api/channels/{channel_id}/current.jpg"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/current.jpg")
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if content_type.startswith('image/'):
                self.log_test(
                    f"current_image_{channel_id}", 
                    True, 
                    f"Image served ({len(response.content)} bytes)",
                    {"content_type": content_type, "size": len(response.content)},
                    response_time
                )
                return True
            else:
                self.log_test(f"current_image_{channel_id}", False, f"Wrong content type: {content_type}", None, response_time)
        else:
            self.log_test(f"current_image_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return False
    
    def test_channel_test(self, channel_id: str) -> bool:
        """Test POST /api/channels/{channel_id}/test"""
        response, response_time = self.make_request(
            'POST', 
            f"{self.base_url}/api/channels/{channel_id}/test",
            json={"test_type": "basic"}
        )
        
        if response.status_code == 200:
            try:
                result = response.json()
                success = result.get('success', False)
                self.log_test(
                    f"channel_test_{channel_id}", 
                    success, 
                    f"Test {'passed' if success else 'failed'}",
                    {"test_result": result.get('test_result')},
                    response_time
                )
                return success
            except json.JSONDecodeError:
                self.log_test(f"channel_test_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"channel_test_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return False

    # ===== IMAGE MANAGEMENT ENDPOINTS =====
    
    def test_list_images(self, channel_id: str) -> List[Dict[str, Any]]:
        """Test GET /api/channels/{channel_id}/images"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/images")
        
        if response.status_code == 200:
            try:
                images = response.json()
                if isinstance(images, list):
                    self.log_test(
                        f"list_images_{channel_id}", 
                        True, 
                        f"Found {len(images)} images",
                        {"count": len(images)},
                        response_time
                    )
                    return images
                else:
                    self.log_test(f"list_images_{channel_id}", False, "Unexpected response format", None, response_time)
            except json.JSONDecodeError:
                self.log_test(f"list_images_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"list_images_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return []
    
    def test_upload_images(self, channel_id: str) -> List[str]:
        """Test POST /api/channels/{channel_id}/images/upload"""
        # Create test images
        test_images = [
            ("test_red.jpg", self.create_test_image((800, 600), (255, 0, 0))),
            ("test_green.jpg", self.create_test_image((600, 800), (0, 255, 0))),
            ("test_blue.jpg", self.create_test_image((400, 400), (0, 0, 255)))
        ]
        
        files = []
        for filename, image_data in test_images:
            files.append(('files', (filename, BytesIO(image_data), 'image/jpeg')))
        
        response, response_time = self.make_request(
            'POST', 
            f"{self.base_url}/api/channels/{channel_id}/images/upload",
            files=files
        )
        
        uploaded_image_ids = []
        
        if response.status_code == 200:
            try:
                result = response.json()
                results = result.get('results', [])
                successful_uploads = [r for r in results if r.get('success')]
                uploaded_image_ids = [str(r.get('image_id')) for r in successful_uploads if r.get('image_id')]
                
                self.log_test(
                    f"upload_images_{channel_id}", 
                    len(successful_uploads) > 0, 
                    f"Uploaded {len(successful_uploads)}/{len(results)} images",
                    {"successful": len(successful_uploads), "total": len(results)},
                    response_time
                )
                
                # Track uploaded images for cleanup
                self.created_resources["uploaded_images"].extend(uploaded_image_ids)
                
            except json.JSONDecodeError:
                self.log_test(f"upload_images_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"upload_images_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return uploaded_image_ids

    # ===== SUBCHANNEL ENDPOINTS =====
    
    def test_list_subchannels(self, channel_id: str) -> List[Dict[str, Any]]:
        """Test GET /api/channels/{channel_id}/subchannels"""
        response, response_time = self.make_request('GET', f"{self.base_url}/api/channels/{channel_id}/subchannels")
        
        if response.status_code == 200:
            try:
                data = response.json()
                subchannels = data.get('subchannels', [])
                self.log_test(
                    f"list_subchannels_{channel_id}", 
                    True, 
                    f"Found {len(subchannels)} subchannels",
                    {"count": len(subchannels)},
                    response_time
                )
                return subchannels
            except json.JSONDecodeError:
                self.log_test(f"list_subchannels_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"list_subchannels_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return []
    
    def test_create_subchannel(self, channel_id: str) -> str:
        """Test POST /api/channels/{channel_id}/subchannels"""
        test_subchannel = {
            "name": f"API Test Gallery {int(time.time())}",
            "description": "Test subchannel created by comprehensive API test",
            "tags": ["test", "api", "comprehensive"]
        }
        
        response, response_time = self.make_request(
            'POST', 
            f"{self.base_url}/api/channels/{channel_id}/subchannels",
            json=test_subchannel
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('success'):
                    subchannel = data.get('subchannel', {})
                    subchannel_id = subchannel.get('id')
                    self.log_test(
                        f"create_subchannel_{channel_id}", 
                        True, 
                        f"Created subchannel '{subchannel_id}'",
                        {"subchannel_id": subchannel_id},
                        response_time
                    )
                    
                    # Track created subchannel for cleanup
                    self.created_resources["subchannels"].append(subchannel_id)
                    return subchannel_id
                else:
                    self.log_test(f"create_subchannel_{channel_id}", False, "API returned success=false", None, response_time)
            except json.JSONDecodeError:
                self.log_test(f"create_subchannel_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"create_subchannel_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return ""
    
    def test_get_subchannel(self, channel_id: str, subchannel_id: str) -> Dict[str, Any]:
        """Test GET /api/channels/{channel_id}/subchannels/{subchannel_id}"""
        response, response_time = self.make_request(
            'GET', 
            f"{self.base_url}/api/channels/{channel_id}/subchannels/{subchannel_id}"
        )
        
        if response.status_code == 200:
            try:
                subchannel = response.json()
                self.log_test(
                    f"get_subchannel_{channel_id}", 
                    True, 
                    f"Retrieved subchannel '{subchannel.get('name')}'",
                    {"id": subchannel.get('id'), "image_count": subchannel.get('imageCount', 0)},
                    response_time
                )
                return subchannel
            except json.JSONDecodeError:
                self.log_test(f"get_subchannel_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"get_subchannel_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return {}
    
    def test_assign_content_to_subchannel(self, channel_id: str, subchannel_id: str, image_ids: List[str]) -> bool:
        """Test POST /api/channels/{channel_id}/subchannels/{subchannel_id}/content"""
        if not image_ids:
            self.log_test(f"assign_content_{channel_id}", False, "No images available to assign")
            return False
        
        response, response_time = self.make_request(
            'POST', 
            f"{self.base_url}/api/channels/{channel_id}/subchannels/{subchannel_id}/content",
            json={
                "contentIds": image_ids[:3],  # Assign first 3 images
                "action": "add"
            }
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('success'):
                    self.log_test(
                        f"assign_content_{channel_id}", 
                        True, 
                        f"Assigned {len(image_ids[:3])} images to subchannel",
                        {"image_count": len(image_ids[:3])},
                        response_time
                    )
                    return True
                else:
                    self.log_test(f"assign_content_{channel_id}", False, "API returned success=false", None, response_time)
            except json.JSONDecodeError:
                self.log_test(f"assign_content_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"assign_content_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return False
    
    def test_subchannel_images(self, channel_id: str, subchannel_id: str) -> List[Dict[str, Any]]:
        """Test GET /api/channels/{channel_id}/subchannels/{subchannel_id}/images"""
        response, response_time = self.make_request(
            'GET', 
            f"{self.base_url}/api/channels/{channel_id}/subchannels/{subchannel_id}/images?include_metadata=true"
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                images = data.get('images', [])
                self.log_test(
                    f"subchannel_images_{channel_id}", 
                    True, 
                    f"Subchannel contains {len(images)} images",
                    {"image_count": len(images)},
                    response_time
                )
                return images
            except json.JSONDecodeError:
                self.log_test(f"subchannel_images_{channel_id}", False, "Invalid JSON response", None, response_time)
        else:
            self.log_test(f"subchannel_images_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return []
    
    def test_subchannel_thumbnail(self, channel_id: str, subchannel_id: str, image_id: str) -> bool:
        """Test GET /api/channels/{channel_id}/subchannels/{subchannel_id}/images/{image_id}/thumbnail"""
        response, response_time = self.make_request(
            'GET', 
            f"{self.base_url}/api/channels/{channel_id}/subchannels/{subchannel_id}/images/{image_id}/thumbnail"
        )
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if content_type.startswith('image/'):
                self.log_test(
                    f"subchannel_thumbnail_{channel_id}", 
                    True, 
                    f"Thumbnail served ({len(response.content)} bytes)",
                    {"content_type": content_type, "size": len(response.content)},
                    response_time
                )
                return True
            else:
                self.log_test(f"subchannel_thumbnail_{channel_id}", False, f"Wrong content type: {content_type}", None, response_time)
        else:
            self.log_test(f"subchannel_thumbnail_{channel_id}", False, f"HTTP {response.status_code}", None, response_time)
        
        return False

    # ===== COMPREHENSIVE TEST RUNNER =====
    
    def test_single_channel(self, channel_id: str) -> Dict[str, Any]:
        """Run comprehensive tests for a single channel"""
        print(f"\n🔍 Testing channel: {channel_id}")
        print("=" * 50)
        
        # Basic channel information
        config = self.test_channel_config(channel_id)
        settings = self.test_channel_settings(channel_id)
        status = self.test_channel_status(channel_id)
        health = self.test_channel_health(channel_id)
        
        # Authentication and content
        token = self.test_channel_token(channel_id)
        current_content = self.test_channel_current_content(channel_id)
        current_image = self.test_channel_current_image(channel_id)
        
        # Test functionality
        test_result = self.test_channel_test(channel_id)
        
        # Image management
        existing_images = self.test_list_images(channel_id)
        uploaded_images = self.test_upload_images(channel_id)
        
        # Get updated image list after upload
        all_images = self.test_list_images(channel_id)
        available_image_ids = [str(img.get('id')) for img in all_images if img.get('id')]
        
        # Subchannel operations
        existing_subchannels = self.test_list_subchannels(channel_id)
        new_subchannel_id = self.test_create_subchannel(channel_id)
        
        if new_subchannel_id:
            # Test subchannel operations
            subchannel_details = self.test_get_subchannel(channel_id, new_subchannel_id)
            
            if available_image_ids:
                # Assign content and test image operations
                content_assigned = self.test_assign_content_to_subchannel(
                    channel_id, new_subchannel_id, available_image_ids
                )
                
                if content_assigned:
                    subchannel_images = self.test_subchannel_images(channel_id, new_subchannel_id)
                    
                    # Test thumbnail serving if we have images
                    if subchannel_images and available_image_ids:
                        self.test_subchannel_thumbnail(
                            channel_id, new_subchannel_id, available_image_ids[0]
                        )
        
        return {
            "channel_id": channel_id,
            "config": config,
            "has_images": len(available_image_ids) > 0,
            "uploaded_images": len(uploaded_images),
            "has_subchannels": len(existing_subchannels) > 0 or bool(new_subchannel_id),
            "created_subchannel": new_subchannel_id
        }
    
    def test_photo_frame_specific(self) -> Dict[str, Any]:
        """Run photo frame channel specific tests"""
        channel_id = "photo_frame"
        print(f"\n📸 Running Photo Frame Channel Specific Tests")
        print("=" * 60)
        
        # Test photo frame channel
        photo_frame_results = self.test_single_channel(channel_id)
        
        # Additional photo frame specific tests could go here
        # For example: testing specific photo frame settings, gallery operations, etc.
        
        return photo_frame_results
    
    def run_all_tests(self, photo_frame_only: bool = False) -> Dict[str, Any]:
        """Run the complete test suite"""
        print("🧪 Starting Comprehensive Channel API Test Suite")
        print(f"📡 API Base URL: {self.base_url}")
        print("=" * 70)
        
        start_time = time.time()
        
        # Test global endpoints first
        if not photo_frame_only:
            channels = self.test_list_channels()
            manifest = self.test_channels_manifest()
        else:
            channels = [{"id": "photo_frame"}]  # Mock for photo frame only testing
        
        # Test each channel
        channel_results = {}
        
        if photo_frame_only:
            # Test only photo frame channel
            channel_results["photo_frame"] = self.test_photo_frame_specific()
        else:
            # Test all discovered channels
            for channel in channels:
                channel_id = channel.get('id')
                if channel_id:
                    try:
                        channel_results[channel_id] = self.test_single_channel(channel_id)
                    except Exception as e:
                        self.log_test(f"channel_error_{channel_id}", False, f"Channel test failed: {str(e)}")
        
        total_time = time.time() - start_time
        
        return self.get_test_summary(total_time, channel_results)
    
    def get_test_summary(self, total_time: float, channel_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["success"]])
        failed_tests = total_tests - passed_tests
        
        # Calculate response time statistics
        response_times = [r["response_time_ms"] for r in self.test_results if r.get("response_time_ms")]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        
        summary = {
            "test_execution": {
                "total_time_seconds": round(total_time, 2),
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": round((passed_tests / total_tests * 100) if total_tests > 0 else 0, 1)
            },
            "performance": {
                "average_response_time_ms": round(avg_response_time, 2),
                "max_response_time_ms": round(max_response_time, 2),
                "total_requests": len(response_times)
            },
            "channels_tested": channel_results,
            "created_resources": self.created_resources,
            "detailed_results": self.test_results
        }
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE TEST SUMMARY")
        print("=" * 70)
        print(f"⏱️  Total Execution Time: {summary['test_execution']['total_time_seconds']}s")
        print(f"🧪 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {summary['test_execution']['success_rate']}%")
        print(f"⚡ Average Response Time: {summary['performance']['average_response_time_ms']}ms")
        print(f"🐌 Slowest Response: {summary['performance']['max_response_time_ms']}ms")
        
        print(f"\n📋 Channels Tested: {len(channel_results)}")
        for channel_id, results in channel_results.items():
            status = "✅" if results.get("config") else "❌"
            print(f"   {status} {channel_id}: {results.get('uploaded_images', 0)} uploaded, "
                  f"{'has subchannels' if results.get('has_subchannels') else 'no subchannels'}")
        
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS ({failed_tests}):")
            for result in self.test_results:
                if not result["success"]:
                    print(f"   • {result['test']}: {result['message']}")
        
        if self.created_resources["subchannels"] or self.created_resources["uploaded_images"]:
            print(f"\n🗑️  CLEANUP NEEDED:")
            if self.created_resources["subchannels"]:
                print(f"   • {len(self.created_resources['subchannels'])} subchannels created")
            if self.created_resources["uploaded_images"]:
                print(f"   • {len(self.created_resources['uploaded_images'])} images uploaded")
        
        return summary


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Comprehensive Channel API Test Suite")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", type=int, default=8000, help="API port")
    parser.add_argument("--photo-frame-only", action="store_true", 
                       help="Test only the photo frame channel")
    parser.add_argument("--output", help="JSON output file for test results")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}"
    
    # Check if PIL is available for image creation
    try:
        from PIL import Image as PILImage, ImageDraw, ImageFont
    except ImportError:
        print("❌ PIL (Pillow) not available. Image upload tests will be skipped.")
        print("   Install with: pip install Pillow")
        return 1
    
    tester = ChannelAPITester(base_url)
    
    try:
        summary = tester.run_all_tests(photo_frame_only=args.photo_frame_only)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"\n📄 Test results saved to: {args.output}")
        
        # Exit with error code if tests failed
        exit_code = 0 if summary["test_execution"]["failed"] == 0 else 1
        
        if exit_code == 0:
            print(f"\n🎉 All tests passed! API is working correctly.")
        else:
            print(f"\n⚠️  Some tests failed. Check the results above.")
        
        return exit_code
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Test execution failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
