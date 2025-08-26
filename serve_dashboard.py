#!/usr/bin/env python3
"""
Simple HTTP server to serve the Mimir Distribution Dashboard
"""

import http.server
import socketserver
import webbrowser
import os
from pathlib import Path

PORT = 8080
DASHBOARD_FILE = "distribution_dashboard.html"

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers to allow connections to oak:5000
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def main():
    # Check if dashboard file exists
    if not Path(DASHBOARD_FILE).exists():
        print(f"❌ Dashboard file '{DASHBOARD_FILE}' not found!")
        print("Make sure you're running this from the directory containing the dashboard file.")
        return
    
    # Start server
    try:
        with socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
            print(f"🚀 Starting Mimir Distribution Dashboard Server")
            print(f"📡 Server running at: http://localhost:{PORT}")
            print(f"🎯 Dashboard URL: http://localhost:{PORT}/{DASHBOARD_FILE}")
            print(f"🔗 WebSocket connecting to: ws://oak:5000/ws")
            print(f"📊 API connecting to: http://oak:5000/api/")
            print()
            print("Press Ctrl+C to stop the server")
            print()
            
            # Open browser automatically
            try:
                webbrowser.open(f"http://localhost:{PORT}/{DASHBOARD_FILE}")
                print("🌐 Opening dashboard in your default browser...")
            except Exception as e:
                print(f"⚠️  Could not open browser automatically: {e}")
                print(f"Please manually open: http://localhost:{PORT}/{DASHBOARD_FILE}")
            
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"❌ Port {PORT} is already in use. Try a different port or stop the existing server.")
        else:
            print(f"❌ Server error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
