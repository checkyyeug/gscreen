#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive Sync Module
Downloads and keeps media in sync with a Google Drive folder
"""

import os
import sys
import json
import hashlib
import logging
import requests
from pathlib import Path
from typing import Set, Dict
import time
from datetime import datetime

# Ensure UTF-8 encoding for file operations
if sys.platform.startswith('linux'):
    import locale
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')

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
        # Time sync settings
        self.timezone_offset = self.settings['sync'].get('timezone_offset', 8)  # Default UTC+8
        self.sync_system_time = self.settings['sync'].get('sync_system_time', True)

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
                capture_output=True, text=True, encoding='utf-8', timeout=60
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
        - Compares modification times before downloading
        - Only downloads new/changed files
        - Deletes local files that no longer exist on Drive
        - Syncs system time via NTP if enabled
        Returns True if any changes were made.
        """
        logger.info("Starting sync...")

        # Sync system time if enabled
        time_sync_ok = True
        if self.sync_system_time:
            time_sync_ok = self._sync_system_time()
            if not time_sync_ok:
                logger.warning("System time sync failed, but continuing with file sync...")

        # Try rclone first for efficient sync (can list files with mod time without downloading)
        rclone_result = self._sync_with_rclone_check_only()

        if rclone_result:
            return rclone_result

        # Fallback to gdown method
        return self._sync_with_gdown()

    def _sync_system_time(self):
        """Sync system time using NTP. Returns True if successful, False otherwise."""
        import subprocess
        import sys
        logger.info(f"[TimeSync] Starting time sync (UTC+{self.timezone_offset})...")

        # Check if running as root or with sudo capabilities
        is_root = os.geteuid() == 0
        has_tty = sys.stdin.isatty()

        if not is_root:
            if not has_tty:
                logger.warning("[TimeSync] Not running as root and no TTY available, skipping system time sync")
                logger.info("[TimeSync] To enable time sync, add this to /etc/sudoers:")
                logger.info("[TimeSync]   rpi4 ALL=(ALL) NOPASSWD: /usr/bin/timedatectl, /usr/bin/date")
                return False
            logger.info("[TimeSync] Not running as root, will try with sudo...")

        try:
            # Use timedatectl to sync time with NTP
            logger.info("[TimeSync] Using timedatectl for NTP sync...")
            cmd = ['timedatectl', 'set-ntp', 'true']
            if not is_root:
                cmd = ['sudo'] + cmd

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0:
                logger.info("[TimeSync] NTP enabled via timedatectl")
            elif "authentication is required" in result.stderr.lower() or "permission denied" in result.stderr.lower():
                logger.warning("[TimeSync] Authentication required for time sync")
                logger.info("[TimeSync] To enable auto time sync, add this to /etc/sudoers:")
                logger.info("[TimeSync]   rpi4 ALL=(ALL) NOPASSWD: /usr/bin/timedatectl, /usr/bin/date")
                return False
            else:
                logger.warning(f"[TimeSync] timedatectl set-ntp failed: {result.stderr}")
                return False

            # Set timezone if needed
            tz_map = {
                -12: 'Etc/GMT+12', -11: 'Etc/GMT+11', -10: 'Etc/GMT+10',
                -9: 'Etc/GMT+9', -8: 'Etc/GMT+8', -7: 'Etc/GMT+7',
                -6: 'Etc/GMT+6', -5: 'Etc/GMT+5', -4: 'Etc/GMT+4',
                -3: 'Etc/GMT+3', -2: 'Etc/GMT+2', -1: 'Etc/GMT+1',
                0: 'Etc/UTC', 1: 'Etc/GMT-1', 2: 'Etc/GMT-2',
                3: 'Etc/GMT-3', 4: 'Etc/GMT-4', 5: 'Etc/GMT-5',
                6: 'Etc/GMT-6', 7: 'Etc/GMT-7', 8: 'Etc/GMT-8',
                9: 'Etc/GMT-9', 10: 'Etc/GMT-10', 11: 'Etc/GMT-11',
                12: 'Etc/GMT-12', 13: 'Etc/GMT-13', 14: 'Etc/GMT-14'
            }

            # Common timezone mappings for positive offsets
            common_tz = {
                8: 'Asia/Shanghai',
                9: 'Asia/Tokyo',
                10: 'Australia/Sydney',
                12: 'Pacific/Auckland',
                -5: 'America/New_York',
                -6: 'America/Chicago',
                -7: 'America/Denver',
                -8: 'America/Los_Angeles'
            }

            # Use common timezone if available, otherwise use GMT
            tz = common_tz.get(self.timezone_offset, tz_map.get(self.timezone_offset, 'Etc/UTC'))

            logger.info(f"[TimeSync] Setting timezone to {tz} (UTC+{self.timezone_offset})...")
            cmd = ['timedatectl', 'set-timezone', tz]
            if not is_root:
                cmd = ['sudo'] + cmd

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0:
                logger.info(f"[TimeSync] Timezone set to {tz} (UTC+{self.timezone_offset})")
                # Show current time after sync
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"[TimeSync] Current system time: {current_time}")
                return True
            else:
                logger.warning(f"[TimeSync] Failed to set timezone: {result.stderr}")
                return False

        except FileNotFoundError:
            # timedatectl not available, try using ntpdate
            logger.warning("[TimeSync] timedatectl not found, trying ntpdate...")
            try:
                logger.info("[TimeSync] Syncing time via ntpdate...")
                cmd = ['ntpdate', '-u', 'pool.ntp.org']
                if not is_root:
                    cmd = ['sudo'] + cmd
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=30)
                if result.returncode == 0:
                    logger.info(f"[TimeSync] ntpdate sync successful: {result.stdout.strip()}")
                    return True
                else:
                    logger.warning(f"[TimeSync] ntpdate failed: {result.stderr}")
                    return False
            except FileNotFoundError:
                logger.warning("[TimeSync] ntpdate not found, trying Python NTP...")
                return self._sync_time_via_ntp(is_root, has_tty)
            except subprocess.TimeoutExpired:
                logger.warning("[TimeSync] ntpdate timed out, trying Python NTP...")
                return self._sync_time_via_ntp(is_root, has_tty)
        except subprocess.CalledProcessError as e:
            logger.warning(f"[TimeSync] timedatectl command failed: {e}")
            return self._sync_time_via_ntp(is_root, has_tty)
        except Exception as e:
            logger.warning(f"[TimeSync] Failed to sync system time: {e}")
            return False

    def _sync_time_via_ntp(self, is_root=False, has_tty=False):
        """Sync system time using Python NTP client"""
        import subprocess
        logger.info("[TimeSync] Using Python ntplib for NTP sync...")

        # Check if we can set time (requires root or passwordless sudo)
        if not is_root and not has_tty:
            logger.warning("[TimeSync] Cannot set time without TTY or root access")
            logger.info("[TimeSync] To enable auto time sync, add this to /etc/sudoers:")
            logger.info("[TimeSync]   rpi4 ALL=(ALL) NOPASSWD: /usr/bin/date")
            return

        try:
            import ntplib
            logger.info("[TimeSync] Connecting to pool.ntp.org...")
            ntp_client = ntplib.NTPClient()
            response = ntp_client.request('pool.ntp.org', version=3, timeout=10)

            ntp_time = datetime.fromtimestamp(response.tx_time)
            time_str = ntp_time.strftime('%Y-%m-%d %H:%M:%S')
            offset_ms = round(response.offset * 1000)

            logger.info(f"[TimeSync] NTP time: {time_str}, offset: {offset_ms}ms")

            # Set system time using date command (requires sudo)
            logger.info(f"[TimeSync] Setting system time to {time_str}...")
            cmd = ['date', '-s', time_str]
            if not is_root:
                cmd = ['sudo'] + cmd

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0:
                logger.info(f"[TimeSync] System time synced via NTP: {time_str}")
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"[TimeSync] Current system time: {current_time}")
                return True
            else:
                logger.warning(f"[TimeSync] Failed to set time: {result.stderr}")
                return False
        except ImportError:
            logger.warning("[TimeSync] ntplib not available, install with: pip install ntplib")
            logger.info("[TimeSync] Skipping time sync (ntplib required)")
            return False
        except Exception as e:
            logger.warning(f"[TimeSync] Failed to sync time via NTP: {type(e).__name__}: {e}")
            return False

    def _sync_with_rclone_check_only(self) -> bool:
        """
        Use rclone to check files and only download changed ones.
        Returns True if rclone is available and sync was attempted.
        Returns False if rclone is not available.
        """
        import subprocess

        try:
            # First, list files on Google Drive with their mod times
            list_cmd = [
                'rclone', 'lsf',
                f'remote:{self._drive_id}',
                '--format', 'tp',  # time, path
                '-R'
            ]

            result = subprocess.run(list_cmd, capture_output=True, text=True, encoding='utf-8', timeout=60)

            if result.returncode != 0:
                return False

            # Parse rclone output to get Drive files with mod times
            drive_files = {}  # filename -> mod_time
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split(None, 1)  # Split on first whitespace (time and path)
                if len(parts) != 2:
                    continue
                mod_time_str, file_path = parts
                file_path = file_path.strip('"')  # rclone outputs paths in quotes

                # Get just the filename
                filename = Path(file_path).name
                if not self._is_supported_image(filename):
                    continue

                # Parse mod time (rclone uses RFC3339 format like "2024-02-12T12:34:56.123456789Z")
                try:
                    mod_time = datetime.fromisoformat(mod_time_str.replace('Z', '+00:00'))
                    drive_files[filename] = mod_time
                except Exception as e:
                    logger.debug(f"Could not parse mod time for {filename}: {e}")
                    drive_files[filename] = None

            # Get local files with their mod times
            local_files = {}  # filename -> mod_time
            for file in self.cache_dir.iterdir():
                if file.is_file() and self._is_supported_image(file.name):
                    mod_time = datetime.fromtimestamp(file.stat().st_mtime)
                    local_files[file.name] = mod_time

            # Determine which files need action
            drive_filenames = set(drive_files.keys())
            local_filenames = set(local_files.keys())

            files_to_download = set()
            files_to_delete = local_filenames - drive_filenames

            # Check which files need to be downloaded
            for filename in drive_filenames:
                if filename not in local_filenames:
                    files_to_download.add(filename)
                else:
                    # File exists locally, check if it needs updating
                    drive_mod = drive_files[filename]
                    local_mod = local_files[filename]
                    if drive_mod and local_mod and drive_mod > local_mod:
                        files_to_download.add(filename)

            # Delete files that no longer exist on Drive
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

            # Download only changed files
            added_count = 0
            updated_count = 0

            if files_to_download:
                for filename in files_to_download:
                    is_new = filename not in local_filenames
                    try:
                        download_cmd = [
                            'rclone', 'copy',
                            f'remote:{self._drive_id}/{filename}' if '/' not in filename else f'remote:{self._drive_id}',
                            str(self.cache_dir),
                            '--include', f'/{filename}',
                            '--no-modtime',
                            '--progress'
                        ]

                        # For folders, we need to handle differently
                        dl_result = subprocess.run(download_cmd, capture_output=True, text=True, encoding='utf-8', timeout=300)

                        if dl_result.returncode == 0:
                            if is_new:
                                added_count += 1
                                logger.info(f"Added: {filename}")
                            else:
                                updated_count += 1
                                logger.info(f"Updated: {filename}")
                        else:
                            logger.warning(f"Failed to download {filename}: {dl_result.stderr}")
                    except Exception as e:
                        logger.warning(f"Error downloading {filename}: {e}")

            total_changes = added_count + updated_count + deleted_count
            if total_changes > 0:
                logger.info(f"Sync completed: +{added_count} added, ~{updated_count} updated, -{deleted_count} deleted")
            else:
                logger.info("Sync completed: No changes")

            return True

        except FileNotFoundError:
            # rclone not installed, return False to use gdown fallback
            return False
        except Exception as e:
            logger.warning(f"rclone sync failed: {e}, falling back to gdown")
            return False

    def _sync_with_gdown(self) -> bool:
        """
        Download using gdown Python module.
        First checks file list, then only downloads new or changed files using resume mode.
        """
        import shutil
        try:
            from gdown import download_folder
        except ImportError:
            logger.error("gdown module not available. Install with: pip install gdown")
            return False

        try:
            # Get list of local files with their sizes
            local_files = {}  # filename -> (size, mod_time)
            for file in self.cache_dir.iterdir():
                if file.is_file() and self._is_supported_image(file.name):
                    local_files[file.name] = (file.stat().st_size, file.stat().st_mtime)

            # Use gdown with skip_download to get file list without downloading
            logger.info("Checking Google Drive for new files...")
            drive_file_info = download_folder(
                url=f'https://drive.google.com/drive/folders/{self._drive_id}',
                skip_download=True,
                use_cookies=False,
                quiet=True
            )

            if not drive_file_info:
                logger.info("No files found on Google Drive")
                return False

            # Parse drive file info to get filenames and sizes
            drive_files = {}  # filename -> size
            for file_obj in drive_file_info:
                if hasattr(file_obj, 'path'):
                    filename = Path(file_obj.path).name
                else:
                    filename = str(file_obj).split('/')[-1]

                if not self._is_supported_image(filename):
                    continue

                # Get file size if available
                if hasattr(file_obj, 'size'):
                    drive_files[filename] = file_obj.size
                else:
                    drive_files[filename] = None

            # Determine which files need to be downloaded
            files_to_download = []
            for filename, drive_size in drive_files.items():
                if filename not in local_files:
                    files_to_download.append(filename)
                    logger.info(f"Will download new file: {filename}")
                elif drive_size is not None and local_files[filename][0] != drive_size:
                    files_to_download.append(filename)
                    logger.info(f"Will download updated file: {filename}")

            # Even if no downloads needed, continue to check for deleted files

            # Use resume=True to skip already downloaded files
            logger.info(f"Downloading {len(files_to_download)} file(s) from Google Drive...")
            download_folder(
                url=f'https://drive.google.com/drive/folders/{self._drive_id}',
                output=str(self.cache_dir),
                quiet=False,
                use_cookies=False,
                resume=True  # Skip existing files
            )

            # Count results
            added_count = len([f for f in files_to_download if f not in local_files])
            updated_count = len(files_to_download) - added_count

            # Check for deleted files
            local_filenames = set(local_files.keys())
            drive_filenames = set(drive_files.keys())
            deleted_count = 0
            for filename in local_filenames - drive_filenames:
                try:
                    (self.cache_dir / filename).unlink()
                    logger.info(f"Deleted: {filename}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {filename}: {e}")

            total_changes = added_count + updated_count + deleted_count
            if total_changes > 0:
                logger.info(f"Sync completed: +{added_count} added, ~{updated_count} updated, -{deleted_count} deleted")
            else:
                logger.info("Sync completed: No changes")

            return True

        except Exception as e:
            logger.error(f"Sync error: {e}")
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

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=600)

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
