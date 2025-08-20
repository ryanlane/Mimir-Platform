import argparse
import requests
import sys

def test_health(base_url):
    r = requests.get(f"{base_url}/api/health")
    print("Health:", r.status_code, r.json())

def test_register_display(base_url):
    payload = {
        "name": "Test Display",
        "description": "Automated test display",
        "location": "Test Lab",
        "capabilities": {
            "resolution": [1920, 1080],
            "supported_formats": ["jpg", "png"],
            "orientation": "landscape",
            "refresh_rate_hz": 60
        },
        "tags": ["test"],
        "client_version": "1.0.0"
    }
    r = requests.post(f"{base_url}/api/displays/register", json=payload)
    print("Register Display:", r.status_code, r.json())
    return r.json().get("id")

def test_list_displays(base_url):
    r = requests.get(f"{base_url}/api/displays")
    print("List Displays:", r.status_code, r.json())

def test_delete_display(base_url, display_id):
    r = requests.delete(f"{base_url}/api/displays/{display_id}")
    print("Delete Display:", r.status_code, r.json())

def test_list_channels(base_url):
    r = requests.get(f"{base_url}/api/channels")
    print("List Channels:", r.status_code, r.json())
    channels = r.json().get("channels", [])
    return channels

def test_create_scene(base_url):
    payload = {
        "name": "Test Scene",
        "channels": ["example_channel"],
        "overlay": {
            "overlays": ["date"],
            "position": ["top", "right"],
            "background": True,
            "backgroundColor": {"red": 0, "green": 0, "blue": 0, "alpha": 10}
        }
    }
    r = requests.post(f"{base_url}/api/scenes", json=payload)
    print("Create Scene:", r.status_code, r.json())
    return r.json().get("id")

def test_list_scenes(base_url):
    r = requests.get(f"{base_url}/api/scenes")
    print("List Scenes:", r.status_code, r.json())
    scenes = r.json().get("scenes", [])
    return scenes

def test_delete_scene(base_url, scene_id):
    r = requests.delete(f"{base_url}/api/scenes/{scene_id}")
    print("Delete Scene:", r.status_code, r.json())

def main():
    parser = argparse.ArgumentParser(description="Mimir API Test Script")
    parser.add_argument("--server", required=True, help="Base API server address (e.g. http://localhost:5000)")
    args = parser.parse_args()
    base_url = args.server.rstrip("/")

    test_health(base_url)
    display_id = test_register_display(base_url)
    test_list_displays(base_url)
    if display_id:
        test_delete_display(base_url, display_id)

    test_list_channels(base_url)
    scene_id = test_create_scene(base_url)
    test_list_scenes(base_url)
    if scene_id:
        test_delete_scene(base_url, scene_id)

if __name__ == "__main__":
    main()
