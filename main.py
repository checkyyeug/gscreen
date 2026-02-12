#!/usr/bin/env python3
"""
gScreen - Google Drive Photo Slideshow for Raspberry Pi
Displays photos from Google Drive on HDMI output

Usage:
    python main.py [--sync-only] [--display-only]

Display:
    - Auto-detects X11 or framebuffer (no desktop required)
    - For framebuffer: Add user to video group: sudo usermod -a -G video $USER
    - HDMI display must be connected
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if required dependencies are installed"""
    missing = []

    try:
        import pygame
    except ImportError:
        missing.append('pygame')

    try:
        from PIL import Image
    except ImportError:
        missing.append('Pillow')

    try:
        import requests
    except ImportError:
        missing.append('requests')

    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.info("Install with: pip install " + " ".join(missing))
        return False

    return True


def load_settings(settings_path: str = "settings.json") -> dict:
    """Load settings from JSON file"""
    try:
        with open(settings_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Settings file not found: {settings_path}")
        logger.info("Creating default settings file...")
        create_default_settings(settings_path)
        return load_settings(settings_path)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in settings file: {e}")
        sys.exit(1)


def create_default_settings(path: str):
    """Create a default settings file"""
    default_settings = {
        "google_drive_url": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID_HERE?usp=sharing",
        "display": {
            "hdmi_port": 1,
            "fullscreen": True,
            "borderless": True,
            "background_color": [0, 0, 0],
            "hide_mouse": True
        },
        "slideshow": {
            "interval_seconds": 5,
            "scale_mode": "fit"
        },
        "sync": {
            "check_interval_minutes": 1,
            "local_cache_dir": "./photos",
            "download_on_start": True
        },
        "supported_formats": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]
    }

    with open(path, 'w') as f:
        json.dump(default_settings, f, indent=4)

    logger.info(f"Created default settings at: {path}")
    logger.warning("Please edit settings.json and add your Google Drive URL!")


def check_framebuffer():
    """Check if framebuffer is accessible"""
    fb_device = '/dev/fb0'
    if not os.path.exists(fb_device):
        logger.error(f"Framebuffer device not found: {fb_device}")
        logger.error("Make sure HDMI is connected and the system is running on Raspberry Pi")
        return False

    if not os.access(fb_device, os.R_OK | os.W_OK):
        logger.error(f"No permission to access {fb_device}")
        logger.error("Add user to video group: sudo usermod -a -G video $USER")
        logger.error("Then logout and login again (or reboot)")
        return False

    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='gScreen - Google Drive Photo Slideshow'
    )
    parser.add_argument(
        '--sync-only',
        action='store_true',
        help='Only sync from Google Drive, do not start slideshow'
    )
    parser.add_argument(
        '--display-only',
        action='store_true',
        help='Skip initial sync, just start slideshow'
    )
    parser.add_argument(
        '--settings',
        default='settings.json',
        help='Path to settings file (default: settings.json)'
    )
    parser.add_argument(
        '--hdmi',
        type=int,
        default=None,
        help='HDMI port to use (0 or 1, overrides settings)'
    )

    args = parser.parse_args()

    # Load settings
    settings = load_settings(args.settings)

    # Override HDMI port if specified
    if args.hdmi is not None:
        settings['display']['hdmi_port'] = args.hdmi

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check framebuffer access
    if not check_framebuffer():
        sys.exit(1)

    # Note: hdmi_port setting is kept for compatibility but not used in framebuffer mode
    # The system will use /dev/fb0 which corresponds to the active HDMI output

    # Import modules after environment setup
    from gdrive_sync import GoogleDriveSync
    from slideshow import SlideshowDisplay

    cache_dir = settings['sync']['local_cache_dir']

    # Initial sync if requested
    if not args.display_only and settings['sync'].get('download_on_start', True):
        logger.info("Starting initial sync...")
        sync = GoogleDriveSync(args.settings)
        sync.initial_sync()
    elif args.sync_only:
        logger.info("Sync-only mode: syncing and exiting...")
        sync = GoogleDriveSync(args.settings)
        sync.initial_sync()
        logger.info("Sync complete")
        return

    # Ensure cache directory exists
    Path(cache_dir).mkdir(exist_ok=True)

    # Start slideshow
    logger.info("Starting slideshow...")
    slideshow = SlideshowDisplay(args.settings)
    try:
        slideshow.run(cache_dir)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
