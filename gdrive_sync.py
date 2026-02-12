#!/usr/bin/env python3
"""
Google Drive Sync Module
Downloads and keeps media in sync with a Google Drive folder
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
        Perform sync operation with Google Drive.
        - Downloads new/modified files
        - Deletes local files that no longer exist on Drive
        Returns True if any changes were made.
        """
        logger.info("Starting sync...")

        import subprocess
        import shutil

        try:
            # Create a temp directory for downloads
            temp_dir = self.cache_dir / '.temp'

            # Remove old temp directory if it exists
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(exist_ok=True)

            # Download to temp directory using gdown
            cmd = [
                'gdown',
                f'https://drive.google.com/drive/folders/{self._drive_id}',
                '--folder',
                '-O', str(temp_dir)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                logger.warning(f"gdown returned: {result.stderr}")
                # Try rclone as fallback
                return self._sync_with_rclone()

            # Get list of files before sync (from media directory)
            local_files_before = set()
            for file in self.cache_dir.iterdir():
                if file.is_file() and self._is_supported_image(file.name):
                    local_files_before.add(file.name)

            # Get list of files downloaded (from temp directory)
            drive_files = set()
            # gdown creates subdirectories, so we need to traverse
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.is_file() and self._is_supported_image(file):
                        drive_files.add(file)

            # Remove old temp subdirectories created by gdown
            for item in temp_dir.iterdir():
                if item.is_dir():
                    # Move files from subdirectory to temp root
                    for file in item.iterdir():
                        if file.is_file():
                            shutil.move(str(file), str(temp_dir / file.name))
                    # Remove the subdirectory
                    shutil.rmtree(item)

            # Now drive_files should be in the root of temp_dir
            # Get the actual list
            drive_files = set()
            for file in temp_dir.iterdir():
                if file.is_file() and self._is_supported_image(file.name):
                    drive_files.add(file.name)

            # Find files to delete (in local but not on Drive)
            files_to_delete = local_files_before - drive_files

            # Delete local files that no longer exist on Drive
            deleted_count = 0
            for filename in files_to_delete:
                try:
                    file_path = self.cache_dir / filename
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"Deleted: {filename} (removed from Drive)")
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {filename}: {e}")

            # Move new/updated files from temp to media directory
            added_count = 0
            updated_count = 0
            for filename in drive_files:
                temp_file = temp_dir / filename
                local_file = self.cache_dir / filename

                if not local_file.exists():
                    # New file
                    shutil.move(str(temp_file), str(local_file))
                    added_count += 1
                    logger.info(f"Added: {filename}")
                else:
                    # File exists, check if it's different (by size and modification time)
                    temp_size = temp_file.stat().st_size
                    local_size = local_file.stat().st_size

                    if temp_size != local_size:
                        shutil.move(str(temp_file), str(local_file))
                        updated_count += 1
                        logger.info(f"Updated: {filename}")
                    else:
                        # Same file, remove temp copy
                        temp_file.unlink()

            # Clean up temp directory
            shutil.rmtree(temp_dir)

            total_changes = added_count + updated_count + deleted_count
            if total_changes > 0:
                logger.info(f"Sync completed: +{added_count} added, ~{updated_count} updated, -{deleted_count} deleted")
            else:
                logger.info("Sync completed: No changes")

            return True

        except FileNotFoundError:
            logger.error("gdown not found. Install with: pip install gdown")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Download timed out")
            return False
        except Exception as e:
            logger.error(f"Sync error: {e}")
            # Clean up temp directory on error
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except:
                pass
            return False

    def sync_with_rclone(self) -> bool:
        """
        Alternative sync using rclone with bidirectional sync.
        Requires: rclone configured with Google Drive
        Deletes local files that no longer exist on Drive.
        """
        import subprocess

        try:
            # Use rclone sync to bidirectionally sync
            # --delete-excluded deletes local files that don't exist on remote
            cmd = [
                'rclone',
                'sync',
                f'remote:{self._drive_id}',
                str(self.cache_dir),
                '--progress',
                '--exclude', '*.tmp',
                '--delete-excluded',  # Delete local files not on remote
                '-v'  # Verbose to see what's being synced
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                logger.info("rclone sync completed successfully")
            else:
                logger.warning(f"rclone sync error: {result.stderr}")

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
