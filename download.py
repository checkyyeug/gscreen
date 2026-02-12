#!/usr/bin/env python3
"""
Alternative Google Drive download using direct API
Works with public folders without OAuth
"""

import os
import json
import re
import logging
import requests
from pathlib import Path
from typing import List, Dict
import subprocess
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_drive_id(url: str) -> str:
    """Extract folder ID from various Google Drive URL formats"""
    patterns = [
        r'/folders/([a-zA-Z0-9_-]+)',
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'[?&]id=([a-zA-Z0-9_-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # If no pattern matches, assume URL is already an ID
    return url.strip('/')


def get_folder_contents(folder_id: str) -> List[Dict]:
    """
    Get folder contents using public directory listing.
    Note: This method has limitations and may not work for all folders.
    """
    # For public folders, we use the directory listing API
    # This returns HTML that we parse for file IDs

    url = f"https://drive.google.com/drive/folders/{folder_id}"
    params = {'usp': 'sharing'}

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    # Parse HTML to find file entries
        # This is a simplified approach - production code should use proper HTML parsing
        contents = []

        # Look for data-id attributes in the HTML
        import re
        file_ids = re.findall(r'"([^"]{20,})"', response.text)

        # Filter for file-like IDs (not folder metadata)
        for file_id in set(file_ids):
            if len(file_id) > 20 and file_id not in [folder_id]:
                contents.append({
                    'id': file_id,
                    'name': f'file_{file_id[:8]}',
                    'direct_url': f'https://drive.google.com/uc?id={file_id}&export=download'
                })

        return contents


def download_with_gdown(folder_url: str, output_dir: str) -> bool:
    """Download folder using gdown (recommended method)"""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            'gdown',
            '--folder',
            '--continue',
            '-O', str(output_path),
            folder_url
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=True
        )

        logger.info("Download completed successfully")
        logger.debug(result.stdout)
        return True

    except subprocess.TimeoutExpired:
        logger.error("Download timed out")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"gdown failed: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("gdown not installed. Install with: pip install gdown")
        return False
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30)
)
def download_file_requests(url: str, dest_path: Path) -> bool:
    """Download a single file using requests with retry"""
    # Handle Google Drive's warning page for large files
    session = requests.Session()
    response = session.get(url, stream=True, timeout=60)
    response.raise_for_status()

    # Check for virus scan warning page
    if 'text/html' in response.headers.get('content-type', '') and 'Google Drive' in response.text:
        # Need to confirm download
        confirm_match = re.search(r'confirm=([0-9A-Za-z]+)', response.text)
        if confirm_match:
            confirm_token = confirm_match.group(1)
            url = f"{url}&confirm={confirm_token}"
            response = session.get(url, stream=True, timeout=60)

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    logger.info(f"Downloaded: {dest_path.name}")
    return True


def main():
    """Test download functionality"""
    import sys

    # Load settings
    try:
        with open('settings.json', 'r') as f:
            settings = json.load(f)
    except FileNotFoundError:
        print("settings.json not found")
        sys.exit(1)

    folder_url = settings['google_drive_url']
    output_dir = settings['sync']['local_cache_dir']

    # Method 1: Try gdown (best for folders)
    print("Attempting download with gdown...")
    if download_with_gdown(folder_url, output_dir):
        print("Success!")
        return

    # Method 2: Manual file listing and download
    print("gdown failed, trying manual download...")
    folder_id = extract_drive_id(folder_url)
    files = get_folder_contents(folder_id)

    print(f"Found {len(files)} files")

    for file in files:
        dest = Path(output_dir) / file['name']
        download_file_requests(file['direct_url'], dest)


if __name__ == "__main__":
    main()
