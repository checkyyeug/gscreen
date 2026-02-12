#!/usr/bin/env python3
"""
Google Drive Sync Module
Downloads and keeps photos in sync with a Google Drive folder
"""

import os
import json
import hashlib
import logging
import requests
from pathlib import Path
from typing import Set, Dict
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GoogleDriveSync:
    """Syncs files from a Google Drive shared folder"""

    def __init__(self, settings_path: str = "settings.json"):
        self.settings = self._load_settings(settings_path)
        self.cache_dir = Path(self.settings['sync']['local_cache_dir'])
        self.cache_dir.mkdir(exist_ok=True)
        self.supported_formats = set(ext.lower() for ext in self.settings['supported_formats'])
        self._current_files: Dict[str, str] = {}  # filename -> file hash
        self._drive_id = self._extract_drive_id(self.settings['google_drive_url'])

    def _load_settings(self, path: str) -> dict:
        """Load settings from JSON file"""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Settings file not found: {path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
            raise

    def _extract_drive_id(self, url: str) -> str:
        """Extract folder/file ID from Google Drive URL"""
        # Handle various Google Drive URL formats
        if '/folders/' in url:
            return url.split('/folders/')[1].split('/')[0].split('?')[0]
        elif '/file/d/' in url:
            return url.split('/file/d/')[1].split('/')[0].split('?')[0]
        elif 'id=' in url:
            return url.split('id=')[1].split('&')[0]
        else:
            # Assume the URL is already just an ID
            return url.strip('/')

    def _get_file_hash(self, filepath: Path) -> str:
        """Calculate MD5 hash of a file"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _is_supported_image(self, filename: str) -> bool:
        """Check if file has supported image extension"""
        return Path(filename).suffix.lower() in self.supported_formats

    def list_local_files(self) -> Dict[str, str]:
        """List all image files in cache with their hashes"""
        files = {}
        for file in self.cache_dir.iterdir():
            if file.is_file() and self._is_supported_image(file.name):
                try:
                    files[file.name] = self._get_file_hash(file)
                except Exception as e:
                    logger.warning(f"Could not hash {file.name}: {e}")
        return files

    def download_file(self, direct_url: str, destination: Path) -> bool:
        """Download a file from URL to destination"""
        try:
            response = requests.get(direct_url, stream=True, timeout=30)
            response.raise_for_status()

            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error(f"Failed to download {direct_url}: {e}")
            return False

    def get_drive_files(self) -> Dict[str, str]:
        """
        Get list of files from Google Drive.
        For public folders, uses directory listing API.

        Returns dict of {filename: direct_download_url}
        """
        # For public folders, we need to use a different approach
        # This is a simplified version - in production you might want to use
        # google-api-python-client or gdown

        logger.warning("Direct Google Drive API access requires OAuth. "
                      "Consider using rclone or gdown for better integration.")

        # Using a workaround with gdown for public folders
        import subprocess

        try:
            # Try to get file list using gdown
            result = subprocess.run(
                ['gdown', '--list', f'https://drive.google.com/drive/folders/{self._drive_id}'],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                files = {}
                for line in result.stdout.split('\n'):
                    if line.strip():
                        files[line.strip()] = f'https://drive.google.com/uc?id={self._drive_id}'
                return files
        except Exception as e:
            logger.error(f"Failed to list drive files: {e}")

        return {}

    def sync(self) -> bool:
        """
        Perform sync operation.
        Returns True if any changes were made.
        """
        logger.info("Starting sync...")

        # Use rclone or gdown for actual syncing
        # This is a more practical approach for Raspberry Pi

        import subprocess

        # First, try using gdown to download the folder
        try:
            # Create a temp directory for downloads
            temp_dir = self.cache_dir / '.temp'
            temp_dir.mkdir(exist_ok=True)

            # Download folder using gdown
            cmd = [
                'gdown',
                f'https://drive.google.com/drive/folders/{self._drive_id}',
                '--folder',
                '-O', str(self.cache_dir)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.info("Download completed successfully")
                return True
            else:
                logger.warning(f"gdown returned: {result.stderr}")

        except FileNotFoundError:
            logger.error("gdown not found. Install with: pip install gdown")
        except subprocess.TimeoutExpired:
            logger.error("Download timed out")
        except Exception as e:
            logger.error(f"Sync error: {e}")

        return False

    def sync_with_rclone(self) -> bool:
        """
        Alternative sync using rclone (more reliable for large folders)
        Requires: rclone configured with Google Drive
        """
        import subprocess

        try:
            cmd = [
                'rclone',
                'copy',
                f'remote:{self._drive_id}',
                str(self.cache_dir),
                '--progress',
                '--exclude', '*.tmp'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            return result.returncode == 0

        except FileNotFoundError:
            logger.error("rclone not found. Install with: sudo apt install rclone")
        except Exception as e:
            logger.error(f"rclone sync error: {e}")

        return False

    def get_images(self) -> list[Path]:
        """Get list of all downloaded image files"""
        images = []
        for ext in self.supported_formats:
            images.extend(self.cache_dir.glob(f'*{ext}'))
            images.extend(self.cache_dir.glob(f'*{ext.upper()}'))
        return sorted(images)

    def initial_sync(self):
        """Perform initial sync on startup"""
        logger.info("Performing initial sync from Google Drive...")

        # Try gdown first
        success = self.sync()

        # If gdown fails, try rclone
        if not success:
            logger.info("Trying rclone...")
            success = self.sync_with_rclone()

        if success:
            count = len(self.get_images())
            logger.info(f"Initial sync complete. Found {count} images.")
        else:
            logger.warning("Initial sync had issues. Check your Google Drive URL.")


if __name__ == "__main__":
    sync = GoogleDriveSync()
    sync.initial_sync()
