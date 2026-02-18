#!/usr/bin/env python3
"""
gScreen Backend API Server
Provides REST API for Flutter/external clients to control the slideshow.

Endpoints:
- GET  /api/health         - Health check
- GET  /api/hardware       - Hardware information
- GET  /api/settings       - Get current settings
- PUT  /api/settings       - Update settings
- POST /api/sync/start     - Start Google Drive sync
- GET  /api/sync/status    - Get sync status
- GET  /api/media          - Get media list
- POST /api/slideshow/start - Start slideshow
- POST /api/slideshow/stop  - Stop slideshow
- GET  /api/slideshow/status - Get slideshow status
- POST /api/slideshow/next  - Next media
- POST /api/slideshow/prev  - Previous media
"""

import os
import sys
import json
import logging
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from hardware_detection import run_hardware_detection, HardwareInfo

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SlideshowState:
    """Shared state for slideshow control"""
    def __init__(self):
        self.is_playing = False
        self.current_index = 0
        self.total_media = 0
        self.current_file = ""
        self.sync_status = "idle"
        self.last_sync = "Never"
        self.total_files = 0
        self.synced_files = 0
        self._lock = threading.Lock()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_playing": self.is_playing,
                "current_index": self.current_index,
                "current_file": self.current_file,
            }


class SyncState:
    """Shared state for sync operations"""
    def __init__(self):
        self.status = "idle"
        self.last_sync = "Never"
        self.total_files = 0
        self.synced_files = 0
        self.current_file = ""
        self._lock = threading.Lock()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "last_sync": self.last_sync,
                "total_files": self.total_files,
                "synced_files": self.synced_files,
                "current_file": self.current_file,
            }


# Global state
slideshow_state = SlideshowState()
sync_state = SyncState()
hardware_info: Optional[HardwareInfo] = None
settings: Dict[str, Any] = {}
settings_path = "settings.json"


def load_settings() -> Dict[str, Any]:
    """Load settings from file"""
    global settings
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Settings file not found: {settings_path}")
        settings = {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in settings: {e}")
        settings = {}
    return settings


def save_settings(new_settings: Dict[str, Any]) -> bool:
    """Save settings to file"""
    global settings
    try:
        with open(settings_path, 'w') as f:
            json.dump(new_settings, f, indent=4)
        settings = new_settings
        return True
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return False


def get_media_list() -> list:
    """Get list of media files"""
    cache_dir = settings.get('sync', {}).get('local_cache_dir', './media')
    cache_path = Path(cache_dir)

    if not cache_path.exists():
        return []

    supported = settings.get('supported_formats', [])
    media_files = []

    for f in cache_path.iterdir():
        if f.is_file() and f.suffix.lower() in supported:
            media_files.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })

    # Sort by name
    media_files.sort(key=lambda x: x['filename'])
    return media_files


class APIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for API endpoints"""

    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

    def _send_json(self, data: Any, status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_error(self, message: str, status: int = 400):
        """Send error response"""
        self._send_json({"error": message}, status)

    def _read_body(self) -> Dict[str, Any]:
        """Read JSON body from request"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode())

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == '/api/health':
                self._send_json({"status": "ok"})

            elif path == '/api/hardware':
                if hardware_info:
                    self._send_json({
                        "model": hardware_info.rpi_model,
                        "generation": hardware_info.rpi_generation,
                        "audio_system": hardware_info.audio_system,
                        "hw_accel_available": hardware_info.hw_accel_available,
                        "hw_accel_method": hardware_info.hw_accel_method,
                    })
                else:
                    self._send_json({"error": "Hardware not detected"})

            elif path == '/api/settings':
                self._send_json(load_settings())

            elif path == '/api/sync/status':
                self._send_json(sync_state.to_dict())

            elif path == '/api/media':
                self._send_json(get_media_list())

            elif path == '/api/slideshow/status':
                self._send_json(slideshow_state.to_dict())

            elif path.startswith('/media/'):
                # Serve media file
                filename = path[7:]  # Remove '/media/' prefix
                cache_dir = settings.get('sync', {}).get('local_cache_dir', './media')
                file_path = Path(cache_dir) / filename

                if file_path.exists() and file_path.is_file():
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Length', str(file_path.stat().st_size))
                    self.end_headers()
                    with open(file_path, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self._send_error("File not found", 404)

            else:
                self._send_error("Not found", 404)

        except Exception as e:
            logger.error(f"Error handling GET {path}: {e}")
            self._send_error(str(e), 500)

    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == '/api/sync/start':
                # Start sync in background thread
                sync_state.status = "syncing"
                sync_state.current_file = "Starting..."
                threading.Thread(target=self._run_sync, daemon=True).start()
                self._send_json({"status": "started"})

            elif path == '/api/slideshow/start':
                slideshow_state.is_playing = True
                self._send_json({"status": "started"})

            elif path == '/api/slideshow/stop':
                slideshow_state.is_playing = False
                self._send_json({"status": "stopped"})

            elif path == '/api/slideshow/next':
                # Signal next media (to be handled by slideshow loop)
                slideshow_state.current_index += 1
                self._send_json({"status": "ok"})

            elif path == '/api/slideshow/prev':
                slideshow_state.current_index = max(0, slideshow_state.current_index - 1)
                self._send_json({"status": "ok"})

            else:
                self._send_error("Not found", 404)

        except Exception as e:
            logger.error(f"Error handling POST {path}: {e}")
            self._send_error(str(e), 500)

    def do_PUT(self):
        """Handle PUT requests"""
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == '/api/settings':
                body = self._read_body()
                if save_settings(body):
                    self._send_json({"status": "saved"})
                else:
                    self._send_error("Failed to save settings", 500)
            else:
                self._send_error("Not found", 404)

        except Exception as e:
            logger.error(f"Error handling PUT {path}: {e}")
            self._send_error(str(e), 500)

    def _run_sync(self):
        """Run sync in background"""
        try:
            from gdrive_sync import GoogleDriveSync
            sync = GoogleDriveSync(settings_path)
            sync.initial_sync()
            sync_state.status = "completed"
            sync_state.last_sync = "Just now"
        except Exception as e:
            logger.error(f"Sync error: {e}")
            sync_state.status = "error"


def run_server(port: int = 8080):
    """Run the API server"""
    global hardware_info

    # Load settings
    load_settings()

    # Detect hardware
    hardware_info = run_hardware_detection(settings)

    # Create server
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    logger.info(f"API server running on http://0.0.0.0:{port}")
    logger.info("Endpoints: /api/health, /api/settings, /api/sync, /api/media, /api/slideshow")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='gScreen API Server')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    parser.add_argument('--settings', default='settings.json', help='Settings file path')
    args = parser.parse_args()

    settings_path = args.settings
    run_server(args.port)
