#!/usr/bin/env python3
"""
Slideshow Display Module
Displays images on HDMI output
Auto-detects best display method (framebuffer or X11)
With status bar showing file info, system info, etc.
"""

import os
import json
import logging
import time
import sys
import signal
import subprocess
import datetime
from pathlib import Path
from typing import Optional, Tuple, List
import random

try:
    import pygame
except ImportError:
    pygame = None

try:
    from PIL import Image
except ImportError:
    Image = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SlideshowDisplay:
    """Fullscreen slideshow display for HDMI output with status bar"""

    def __init__(self, settings_path: str = "settings.json"):
        self.settings = self._load_settings(settings_path)
        self.display_settings = self.settings['display']
        self.slideshow_settings = self.settings['slideshow']

        self.interval = self.slideshow_settings['interval_seconds']
        self.scale_mode = self.slideshow_settings['scale_mode']
        self.bg_color = tuple(self.display_settings['background_color'])
        self.hide_mouse = self.display_settings.get('hide_mouse', True)  # Default: True
        self.show_statusbar = self.display_settings.get('show_statusbar', True)  # Default: True

        # Status bar settings
        self.statusbar_height = 30
        self.statusbar_bg_color = (30, 30, 30)
        self.statusbar_text_color = (200, 200, 200)
        self.statusbar_font_size = 14

        # Runtime state
        self.running = False
        self.current_image_index = 0
        self.images: list[Path] = []
        self.screen = None
        self.screen_info = None
        self.display_mode = None  # 'fbcon', 'x11', or 'sdl-default'
        self.font = None
        self.last_sync_time = None

        # Current image info
        self.current_image_path = None
        self.current_image_info = {}

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

    def _get_wifi_signal(self) -> str:
        """Get WiFi signal strength in dBm"""
        try:
            # Try to get WiFi signal from /proc/net/wireless
            for interface in ['wlan0', 'wlan1', 'wlp1s0', 'wlo1']:
                path = f'/proc/net/wireless'
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        lines = f.readlines()
                        if len(lines) >= 3:
                            # Parse signal quality (3rd line, 3rd value)
                            parts = lines[2].split()
                            if len(parts) >= 3:
                                signal = int(parts[2])
                                # Convert to dBm (approximately)
                                dbm = signal - 100
                                return f"{dbm} dBm"

            # Alternative: try iwconfig
            result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=1)
            if 'Signal level' in result.stdout:
                import re
                match = re.search(r'Signal level=(-?\d+) dBm', result.stdout)
                if match:
                    return f"{match.group(1)} dBm"
        except:
            pass
        return "N/A"

    def _get_file_info(self, image_path: Path) -> dict:
        """Get file information"""
        info = {
            'name': image_path.name,
            'size': '',
            'modified': '',
            'format': image_path.suffix.upper(),
            'dimensions': ''
        }

        try:
            # File size
            size_bytes = image_path.stat().st_size
            if size_bytes < 1024:
                info['size'] = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                info['size'] = f"{size_bytes / 1024:.1f} KB"
            else:
                info['size'] = f"{size_bytes / (1024 * 1024):.1f} MB"

            # Modification date
            mtime = image_path.stat().st_mtime
            mod_time = datetime.datetime.fromtimestamp(mtime)
            info['modified'] = mod_time.strftime("%Y-%m-%d %H:%M")

            # Image dimensions
            if Image is not None:
                with Image.open(image_path) as img:
                    info['dimensions'] = f"{img.width}x{img.height}"
        except Exception as e:
            logger.debug(f"Error getting file info: {e}")

        return info

    def _init_font(self):
        """Initialize font for status bar"""
        if self.font is None:
            try:
                # Try to use a system font
                self.font = pygame.font.SysFont('DejaVuSans', self.statusbar_font_size, bold=True)
            except:
                # Fallback to default font
                self.font = pygame.font.Font(None, self.statusbar_font_size)

    def _draw_statusbar(self, countdown: float = 0):
        """Draw status bar at bottom of screen"""
        if not self.show_statusbar or self.screen is None:
            return

        self._init_font()

        screen_width = self.screen_info.current_w
        screen_height = self.screen_info.current_h

        # Create status bar surface
        statusbar_y = screen_height - self.statusbar_height
        statusbar_rect = pygame.Rect(0, statusbar_y, screen_width, self.statusbar_height)

        # Draw status bar background
        pygame.draw.rect(self.screen, self.statusbar_bg_color, statusbar_rect)

        # Left side info (file info)
        left_texts = []
        if self.current_image_info:
            left_texts = [
                f"Name: {self.current_image_info.get('name', '')}",
                f"Date: {self.current_image_info.get('modified', '')}",
                f"Size: {self.current_image_info.get('size', '')}",
                f"Format: {self.current_image_info.get('format', '')}",
                f"Dim: {self.current_image_info.get('dimensions', '')}"
            ]

        # Right side info (system info)
        right_texts = [
            f"Res: {screen_width}x{screen_height}",
            f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}",
            f"WiFi: {self._get_wifi_signal()}",
            f"Img: {self.current_image_index + 1}/{len(self.images)}",
            f"Next: {max(0, countdown):.0f}s",
        ]
        if self.last_sync_time:
            sync_str = self.last_sync_time.strftime('%H:%M')
            right_texts.append(f"Sync: {sync_str}")

        # Render left text
        x_offset = 10
        y_offset = statusbar_y + 2
        for text in left_texts:
            surface = self.font.render(text, True, self.statusbar_text_color)
            self.screen.blit(surface, (x_offset, y_offset))
            x_offset += surface.get_width() + 15

        # Render right text (from right to left)
        x_offset = screen_width - 10
        for text in reversed(right_texts):
            surface = self.font.render(text, True, self.statusbar_text_color)
            x_offset -= surface.get_width() + 15
            self.screen.blit(surface, (x_offset, y_offset))

    def _is_x11_running(self) -> bool:
        """Check if X11 is running"""
        # Check for X11 socket
        if os.path.exists('/tmp/.X11-unix'):
            return True

        # Check for X11 processes (lightdm, X, Xorg)
        try:
            import subprocess
            # Check for any X server process
            result = subprocess.run(['pgrep', '-x', 'X'], capture_output=True)
            if result.returncode == 0:
                return True
            result = subprocess.run(['pgrep', '-x', 'Xorg'], capture_output=True)
            if result.returncode == 0:
                return True
            # Check for lightdm
            result = subprocess.run(['pgrep', 'lightdm'], capture_output=True)
            if result.returncode == 0:
                return True
        except:
            pass

        return False

    def _get_display_resolution(self) -> Tuple[int, int]:
        """Try to get display resolution from various sources"""
        # Try framebuffer sysfs first
        try:
            with open('/sys/class/graphics/fb0/virtual_size', 'r') as f:
                resolution = f.read().strip()
                width, height = map(int, resolution.split(','))
                logger.info(f"Framebuffer resolution: {width}x{height}")
                return width, height
        except:
            pass

        # Try drm output
        try:
            for mode in ['modes', 'mode']:
                for card in Path('/sys/class/drm').glob('card*- HDMI-*'):
                    modes_file = card / mode
                    if modes_file.exists():
                        content = modes_file.read_text().strip()
                        if content:
                            # Parse mode like "1920x1080"
                            for line in content.split('\n'):
                                if 'x' in line:
                                    w, h = line.split('x')[:2]
                                    try:
                                        return int(w), int(h)
                                    except:
                                        continue
        except:
            pass

        return 1920, 1080  # Default fallback

    def _init_display_framebuffer(self) -> bool:
        """Try to initialize display using framebuffer (fbcon)"""
        fb_device = '/dev/fb0'

        if not os.path.exists(fb_device):
            logger.debug(f"Framebuffer device not found: {fb_device}")
            return False

        if not os.access(fb_device, os.R_OK | os.W_OK):
            logger.debug(f"No permission to access {fb_device}")
            logger.debug("Add user to video group: sudo usermod -a -G video $USER")
            return False

        # Set up framebuffer environment
        os.environ['SDL_VIDEODRIVER'] = 'fbcon'
        os.environ['SDL_FBDEV'] = fb_device

        # Disable mouse cursor if configured
        if self.hide_mouse:
            os.environ['SDL_NOMOUSE'] = '1'

        logger.info(f"Trying framebuffer (fbcon) driver... (mouse: {'hidden' if self.hide_mouse else 'visible'})")
        return True

    def _init_display_x11(self) -> bool:
        """Try to initialize display using X11"""
        # Check what DISPLAY values are available
        display_nums = []

        # Check :0 and :1
        for d in [0, 1]:
            if os.path.exists(f'/tmp/.X11-unix/X{d}'):
                display_nums.append(d)

        if not display_nums:
            # Use whatever is in DISPLAY env
            display_env = os.environ.get('DISPLAY', '')
            if display_env:
                display_nums.append(int(display_env.split(':')[1].split('.')[0]))
            else:
                display_nums.append(0)

        hdmi_port = self.display_settings.get('hdmi_port', 1)
        display_num = hdmi_port if hdmi_port in display_nums else display_nums[0]

        os.environ['SDL_VIDEODRIVER'] = 'x11'
        os.environ['DISPLAY'] = f':{display_num}'

        # Disable mouse cursor if configured
        if self.hide_mouse:
            os.environ['SDL_NOMOUSE'] = '1'
            os.environ['SDL_VIDEO_X11_DGAMOUSE'] = '0'

        logger.info(f"Trying X11 driver on DISPLAY=:{display_num}... (mouse: {'hidden' if self.hide_mouse else 'visible'})")
        return True

    def init_display(self):
        """Initialize pygame display with auto-detection"""
        if pygame is None:
            raise ImportError("pygame is not installed. Install with: pip install pygame")

        # Get display resolution hint
        width, height = self._get_display_resolution()

        # Try different display drivers in order
        drivers_to_try = []

        x11_running = self._is_x11_running()
        if x11_running:
            logger.info("X11 detected, will try X11 driver first")
        else:
            logger.info("No X11 detected, will try framebuffer driver first")

        # If X11 is running, try it first, otherwise try framebuffer first
        if x11_running:
            drivers_to_try.append(('x11', self._init_display_x11))
            drivers_to_try.append(('fbcon', self._init_display_framebuffer))
        else:
            drivers_to_try.append(('fbcon', self._init_display_framebuffer))
            drivers_to_try.append(('x11', self._init_display_x11))

        # Always try SDL's default auto-detection as last resort
        def _init_sdl_default():
            logger.info("Trying SDL default driver (auto-detect)...")
            # Clear any SDL driver settings to let SDL auto-detect
            for key in list(os.environ.keys()):
                if key.startswith('SDL_'):
                    del os.environ[key]
            return True
        drivers_to_try.append(('sdl-default', _init_sdl_default))

        # Try each driver
        for driver_name, init_func in drivers_to_try:
            try:
                # Clear any previous SDL config
                for key in list(os.environ.keys()):
                    if key.startswith('SDL_'):
                        del os.environ[key]
                if 'DISPLAY' in os.environ:
                    del os.environ['DISPLAY']

                # Initialize this driver
                if not init_func():
                    continue

                # Try to initialize pygame
                pygame.init()
                pygame.display.init()

                # Get display info
                self.screen_info = pygame.display.Info()
                screen_width = self.screen_info.current_w
                screen_height = self.screen_info.current_h

                logger.info(f"Display resolution: {screen_width}x{screen_height}")

                # Set display mode (account for status bar)
                flags = pygame.FULLSCREEN | pygame.NOFRAME
                self.screen = pygame.display.set_mode((screen_width, screen_height), flags)

                # Hide cursor based on setting
                pygame.mouse.set_visible(not self.hide_mouse)
                if self.hide_mouse:
                    logger.info("Mouse cursor hidden")

                self.display_mode = driver_name
                logger.info(f"Display initialized successfully using {driver_name} driver")
                return

            except Exception as e:
                logger.warning(f"Failed to initialize {driver_name}: {e}")
                # Clean up and try next driver
                try:
                    pygame.quit()
                except:
                    pass

        # All drivers failed
        tried = ", ".join(d[0] for d in drivers_to_try)
        raise RuntimeError(
            f"Failed to initialize display. Tried: {tried}\n"
            "Troubleshooting:\n"
            "  - Ensure HDMI display is connected\n"
            "  - For framebuffer: sudo usermod -a -G video $USER (then re-login)\n"
            "  - For X11: Make sure X11 is running: echo $DISPLAY\n"
            "  - Try: export DISPLAY=:0 && python3 main.py"
        )

    def load_images(self, cache_dir: str) -> list[Path]:
        """Load all images from cache directory"""
        cache_path = Path(cache_dir)
        if not cache_path.exists():
            logger.warning(f"Cache directory not found: {cache_dir}")
            return []

        supported = set(ext.lower() for ext in self.settings.get('supported_formats', []))
        images = []

        for file in cache_path.iterdir():
            if file.is_file() and file.suffix.lower() in supported:
                images.append(file)

        logger.info(f"Loaded {len(images)} images from {cache_dir}")
        return sorted(images)

    def calculate_fit_size(self, img_width: int, img_height: int,
                         screen_width: int, screen_height: int) -> Tuple[int, int, int, int]:
        """
        Calculate scaled dimensions and position to fit image on screen
        maintaining aspect ratio (letterbox/pillarbox as needed)

        Returns: (x, y, width, height)
        """
        # Account for status bar
        effective_height = screen_height - (self.statusbar_height if self.show_statusbar else 0)

        img_ratio = img_width / img_height
        screen_ratio = screen_width / effective_height

        if img_ratio > screen_ratio:
            # Image is wider - fit to width
            new_width = screen_width
            new_height = int(screen_width / img_ratio)
        else:
            # Image is taller - fit to height
            new_height = effective_height
            new_width = int(effective_height * img_ratio)

        # Center on screen
        x = (screen_width - new_width) // 2
        y = (effective_height - new_height) // 2

        return x, y, new_width, new_height

    def calculate_fill_size(self, img_width: int, img_height: int,
                          screen_width: int, screen_height: int) -> Tuple[int, int, int, int]:
        """
        Calculate scaled dimensions to fill screen (crop if needed)
        Returns: (source_x, source_y, source_w, source_h)
        For fill mode, we return crop coordinates
        """
        # Account for status bar
        effective_height = screen_height - (self.statusbar_height if self.show_statusbar else 0)

        img_ratio = img_width / img_height
        screen_ratio = screen_width / effective_height

        if img_ratio > screen_ratio:
            # Image is wider - crop sides
            crop_height = img_height
            crop_width = int(img_height * screen_ratio)
            crop_x = (img_width - crop_width) // 2
            crop_y = 0
        else:
            # Image is taller - crop top/bottom
            crop_width = img_width
            crop_height = int(img_width / screen_ratio)
            crop_x = 0
            crop_y = (img_height - crop_height) // 2

        return crop_x, crop_y, crop_width, crop_height

    def display_image(self, image_path: Path) -> bool:
        """Load and display an image"""
        try:
            # Get file info for status bar
            self.current_image_path = image_path
            self.current_image_info = self._get_file_info(image_path)

            # Use PIL for better image loading
            if Image is not None:
                pil_image = Image.open(image_path)

                # Convert to RGB if necessary
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')

                img_width, img_height = pil_image.size
                screen_width = self.screen_info.current_w
                screen_height = self.screen_info.current_h

                # Calculate dimensions based on scale mode
                if self.scale_mode == 'fit':
                    x, y, new_width, new_height = self.calculate_fit_size(
                        img_width, img_height, screen_width, screen_height
                    )
                    # Resize and place
                    pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    # Create background and paste
                    background = Image.new('RGB', (screen_width, screen_height - (self.statusbar_height if self.show_statusbar else 0)), self.bg_color)
                    background.paste(pil_image, (x, y))
                    pil_image = background
                elif self.scale_mode == 'fill':
                    # Fill mode - crop to fill screen
                    crop_x, crop_y, crop_w, crop_h = self.calculate_fill_size(
                        img_width, img_height, screen_width, screen_height
                    )
                    pil_image = pil_image.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
                    target_height = screen_height - (self.statusbar_height if self.show_statusbar else 0)
                    pil_image = pil_image.resize((screen_width, target_height), Image.Resampling.LANCZOS)
                else:  # stretch
                    target_height = screen_height - (self.statusbar_height if self.show_statusbar else 0)
                    pil_image = pil_image.resize((screen_width, target_height), Image.Resampling.LANCZOS)

                # Convert to pygame surface
                img_surface = pygame.image.fromstring(
                    pil_image.tobytes(),
                    pil_image.size,
                    pil_image.mode
                )
            else:
                # Fallback to pygame only
                img_surface = pygame.image.load(str(image_path))
                screen_width = self.screen_info.current_w
                screen_height = self.screen_info.current_h

                target_height = screen_height - (self.statusbar_height if self.show_statusbar else 0)
                img_surface = pygame.transform.scale(
                    img_surface,
                    (screen_width, target_height)
                )

            # Display
            self.screen.fill(self.bg_color)
            self.screen.blit(img_surface, (0, 0))

            # Draw status bar
            self._draw_statusbar()

            pygame.display.flip()

            logger.debug(f"Displayed: {image_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error displaying {image_path}: {e}")
            return False

    def _signal_handler(self, signum, frame):
        """Handle signals for clean shutdown"""
        logger.info("Received signal, shutting down...")
        self.running = False

    def run(self, cache_dir: str):
        """Main slideshow loop"""
        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.init_display()

        # Load images
        self.images = self.load_images(cache_dir)

        if not self.images:
            logger.warning("No images to display")
            return

        self.running = True
        last_change = time.time()
        last_sync = time.time()
        last_statusbar_update = time.time()

        logger.info(f"Starting slideshow with {len(self.images)} images")

        # Import sync module for periodic updates
        from gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync()

        while self.running:
            try:
                # Ensure mouse cursor state matches setting
                if self.hide_mouse:
                    pygame.mouse.set_visible(False)

                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            logger.info("ESC pressed, exiting...")
                            self.running = False
                        elif event.key == pygame.K_SPACE:
                            # Skip to next image
                            last_change = 0
                        elif event.key == pygame.K_q:
                            logger.info("Q pressed, exiting...")
                            self.running = False

                current_time = time.time()

                # Update status bar time/wifi every second
                if current_time - last_statusbar_update >= 1.0:
                    if self.show_statusbar and self.screen is not None:
                        countdown = self.interval - (current_time - last_change)
                        self._draw_statusbar(countdown)
                        pygame.display.flip()
                    last_statusbar_update = current_time

                # Check if it's time to change image
                if current_time - last_change >= self.interval:
                    if self.images:
                        # Display next image
                        image_path = self.images[self.current_image_index]
                        self.display_image(image_path)

                        # Move to next image
                        self.current_image_index = (self.current_image_index + 1) % len(self.images)
                        last_change = current_time
                        last_statusbar_update = current_time  # Reset statusbar timer

                # Periodic sync check (every minute)
                sync_interval = self.settings['sync']['check_interval_minutes'] * 60
                if current_time - last_sync >= sync_interval:
                    logger.info("Checking for new images...")
                    sync.sync()
                    self.images = self.load_images(cache_dir)
                    self.last_sync_time = datetime.datetime.now()
                    # Reset index if out of bounds
                    if self.current_image_index >= len(self.images):
                        self.current_image_index = 0
                    last_sync = current_time

                # Small sleep to prevent high CPU usage
                time.sleep(0.05)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                self.running = False
            except Exception as e:
                logger.error(f"Error in slideshow: {e}", exc_info=True)
                time.sleep(1)

        # Cleanup
        pygame.quit()
        logger.info("Slideshow ended")


def main():
    """Main entry point"""
    import sys

    # Get cache directory from settings or use default
    try:
        with open("settings.json", 'r') as f:
            settings = json.load(f)
        cache_dir = settings['sync']['local_cache_dir']
    except:
        cache_dir = "./photos"

    slideshow = SlideshowDisplay()
    slideshow.run(cache_dir)


if __name__ == "__main__":
    main()
