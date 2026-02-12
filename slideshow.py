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

# Don't import pygame yet - we need to set SDL_VIDEODRIVER first
pygame = None
def get_pygame():
    global pygame
    if pygame is not None:
        return pygame
    try:
        import pygame as pg
        pygame = pg
        return pygame
    except ImportError:
        return None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import cv2
except ImportError:
    cv2 = None

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
        self.statusbar_position = self.display_settings.get('statusbar_position', 'bottom')  # Default: 'bottom'

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
        self.screen_width = 0
        self.screen_height = 0
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
        # Try iwconfig first (more reliable)
        try:
            result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=1)
            if 'Signal level' in result.stdout:
                match = re.search(r'Signal level=(-?\d+) dBm', result.stdout)
                if match:
                    return f"{match.group(1)} dBm"
        except:
            pass

        # Fallback: try /proc/net/wireless
        try:
            if os.path.exists('/proc/net/wireless'):
                with open('/proc/net/wireless', 'r') as f:
                    lines = f.readlines()
                    if len(lines) >= 3:
                        # Parse signal level (4th column on data line)
                        parts = lines[2].split()
                        if len(parts) >= 4:
                            # Signal is in dBm already (negative value with decimal)
                            signal = int(float(parts[3]))
                            return f"{signal} dBm"
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

    def _is_video(self, filepath: Path) -> bool:
        """Check if file is a video based on extension"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v'}
        return filepath.suffix.lower() in video_extensions

    def _get_video_info(self, video_path: Path) -> dict:
        """Get video file information"""
        info = {
            'name': video_path.name,
            'size': '',
            'modified': '',
            'format': video_path.suffix.upper(),
            'dimensions': '',
            'duration': ''
        }

        try:
            # File size
            size_bytes = video_path.stat().st_size
            if size_bytes < 1024:
                info['size'] = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                info['size'] = f"{size_bytes / 1024:.1f} KB"
            else:
                info['size'] = f"{size_bytes / (1024 * 1024):.1f} MB"

            # Modification date
            mtime = video_path.stat().st_mtime
            mod_time = datetime.datetime.fromtimestamp(mtime)
            info['modified'] = mod_time.strftime("%Y-%m-%d %H:%M")

            # Video info using cv2
            if cv2 is not None:
                cap = cv2.VideoCapture(str(video_path))
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    duration = frame_count / fps if fps > 0 else 0

                    info['dimensions'] = f"{width}x{height}"
                    info['duration'] = f"{int(duration // 60)}:{int(duration % 60):02d}"
                    cap.release()
        except Exception as e:
            logger.debug(f"Error getting video info: {e}")

        return info

    def _init_font(self):
        """Initialize font for status bar"""
        if self.font is None:
            pg = get_pygame()
            try:
                # Try to use a system font
                self.font = pg.font.SysFont('DejaVuSans', self.statusbar_font_size, bold=True)
            except:
                # Fallback to default font
                self.font = pg.font.Font(None, self.statusbar_font_size)

    def _draw_statusbar(self, countdown: float = 0):
        """Draw status bar at top or bottom of screen"""
        if not self.show_statusbar or self.screen is None:
            return

        pg = get_pygame()
        self._init_font()

        screen_width = self.screen_width
        screen_height = self.screen_height

        # Determine status bar position based on setting
        if self.statusbar_position == 'top':
            statusbar_y = 0
        else:  # 'bottom' or default
            statusbar_y = screen_height - self.statusbar_height

        statusbar_rect = pg.Rect(0, statusbar_y, screen_width, self.statusbar_height)

        # Draw status bar background
        pg.draw.rect(self.screen, self.statusbar_bg_color, statusbar_rect)

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

        # Text vertical offset (center in status bar)
        y_offset = statusbar_y + 2

        # Render left text
        x_offset = 10
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
        pg = get_pygame()
        if pg is None:
            raise ImportError("pygame-ce is not installed. Install with: pip install pygame-ce")

        # Get display resolution hint
        width, height = self._get_display_resolution()

        # Try different display drivers in order
        drivers_to_try = []

        x11_running = self._is_x11_running()
        if x11_running:
            logger.info("X11 detected, will try X11 driver first")
        else:
            logger.info("No X11 detected, will try KMSDRM driver first")

        # Priority: KMSDRM (modern framebuffer) > fbcon > x11
        def _init_kmsdrm():
            logger.info("Trying KMSDRM driver... (mouse: hidden)")
            os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'
            os.environ['SDL_NOMOUSE'] = '1'
            return True

        if not x11_running:
            drivers_to_try.append(('kmsdrm', _init_kmsdrm))
            drivers_to_try.append(('fbcon', self._init_display_framebuffer))
            drivers_to_try.append(('x11', self._init_display_x11))
        else:
            drivers_to_try.append(('x11', self._init_display_x11))
            drivers_to_try.append(('kmsdrm', _init_kmsdrm))
            drivers_to_try.append(('fbcon', self._init_display_framebuffer))

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
                pg.init()
                pg.display.init()

                # Use detected resolution for proper display sizing
                screen_width = width
                screen_height = height

                # Get display info for other purposes (but use detected resolution)
                self.screen_info = pg.display.Info()
                # Store detected resolution for consistent access
                self.screen_width = screen_width
                self.screen_height = screen_height

                logger.info(f"Display resolution: {screen_width}x{screen_height}")

                # Set display mode with double buffering for smooth rendering
                flags = pg.FULLSCREEN | pg.DOUBLEBUF | pg.HWSURFACE | pg.NOFRAME
                self.screen = pg.display.set_mode((screen_width, screen_height), flags)

                # Hide cursor based on setting
                pg.mouse.set_visible(not self.hide_mouse)
                if self.hide_mouse:
                    logger.info("Mouse cursor hidden")

                self.display_mode = driver_name
                logger.info(f"Display initialized successfully using {driver_name} driver")
                return

            except Exception as e:
                logger.warning(f"Failed to initialize {driver_name}: {e}")
                # Clean up and try next driver
                try:
                    pg.quit()
                except:
                    pass

        # All drivers failed
        tried = ", ".join(d[0] for d in drivers_to_try)
        raise RuntimeError(
            f"Failed to initialize display. Tried: {tried}\n"
            "Troubleshooting:\n"
            "  - Ensure HDMI display is connected\n"
            "  - Install pygame-ce: pip install pygame-ce\n"
            "  - Make sure you're in the video group: groups $USER"
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
        if self.show_statusbar:
            if self.statusbar_position == 'top':
                image_start_y = self.statusbar_height
            else:  # 'bottom' or default
                image_start_y = 0
            effective_height = screen_height - self.statusbar_height
        else:
            image_start_y = 0
            effective_height = screen_height

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

        # Center on screen (accounting for status bar position)
        x = (screen_width - new_width) // 2
        y = image_start_y + (effective_height - new_height) // 2

        return x, y, new_width, new_height

    def calculate_fill_size(self, img_width: int, img_height: int,
                          screen_width: int, screen_height: int) -> Tuple[int, int, int, int]:
        """
        Calculate scaled dimensions to fill screen (crop if needed)
        Returns: (source_x, source_y, source_w, source_h)
        For fill mode, we return crop coordinates
        """
        # Account for status bar
        if self.show_statusbar:
            effective_height = screen_height - self.statusbar_height
        else:
            effective_height = screen_height

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
        pg = get_pygame()
        try:
            # Get file info for status bar
            self.current_image_path = image_path
            self.current_image_info = self._get_file_info(image_path)

            # Determine image display area based on status bar position
            if self.show_statusbar:
                if self.statusbar_position == 'top':
                    image_display_y = self.statusbar_height
                    image_display_height = self.screen_height - self.statusbar_height
                else:  # 'bottom' or default
                    image_display_y = 0
                    image_display_height = self.screen_height - self.statusbar_height
            else:
                image_display_y = 0
                image_display_height = self.screen_height

            # Use PIL for better image loading
            if Image is not None:
                pil_image = Image.open(image_path)

                # Convert to RGB if necessary
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')

                img_width, img_height = pil_image.size
                screen_width = self.screen_width
                screen_height = self.screen_height

                # Calculate dimensions based on scale mode
                if self.scale_mode == 'fit':
                    x, y, new_width, new_height = self.calculate_fit_size(
                        img_width, img_height, screen_width, screen_height
                    )
                    # Resize and place
                    pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    # Create background and paste
                    background = Image.new('RGB', (screen_width, image_display_height), self.bg_color)
                    background.paste(pil_image, (x, y))
                    pil_image = background
                elif self.scale_mode == 'fill':
                    # Fill mode - crop to fill screen
                    crop_x, crop_y, crop_w, crop_h = self.calculate_fill_size(
                        img_width, img_height, screen_width, screen_height
                    )
                    pil_image = pil_image.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
                    pil_image = pil_image.resize((screen_width, image_display_height), Image.Resampling.LANCZOS)
                else:  # stretch
                    pil_image = pil_image.resize((screen_width, image_display_height), Image.Resampling.LANCZOS)

                # Convert to pygame surface
                img_surface = pg.image.fromstring(
                    pil_image.tobytes(),
                    pil_image.size,
                    pil_image.mode
                )
            else:
                # Fallback to pygame only
                img_surface = pg.image.load(str(image_path))
                screen_width = self.screen_width
                img_surface = pg.transform.scale(
                    img_surface,
                    (screen_width, image_display_height)
                )

            # Display
            self.screen.fill(self.bg_color)
            self.screen.blit(img_surface, (0, image_display_y))

            # Draw status bar
            self._draw_statusbar()

            pg.display.flip()

            logger.debug(f"Displayed: {image_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error displaying {image_path}: {e}")
            return False

    def display_video(self, video_path: Path) -> bool:
        """Load and display a video file using OpenCV"""
        pg = get_pygame()
        if cv2 is None:
            logger.error("OpenCV (cv2) is not installed. Install with: pip install opencv-python")
            return False

        try:
            # Get video info for status bar
            self.current_image_path = video_path
            self.current_image_info = self._get_video_info(video_path)

            # Determine video display area based on status bar position
            if self.show_statusbar:
                if self.statusbar_position == 'top':
                    video_display_y = self.statusbar_height
                    video_display_height = self.screen_height - self.statusbar_height
                else:  # 'bottom' or default
                    video_display_y = 0
                    video_display_height = self.screen_height - self.statusbar_height
            else:
                video_display_y = 0
                video_display_height = self.screen_height

            # Open video file
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return False

            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            # Calculate display dimensions based on scale mode
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if self.scale_mode == 'fit':
                x, y, display_width, display_height = self.calculate_fit_size(
                    video_width, video_height, self.screen_width, video_display_height
                )
                y += video_display_y  # Adjust for status bar offset
            elif self.scale_mode == 'fill':
                # For fill mode in video, we'll use crop calculation
                crop_x, crop_y, crop_w, crop_h = self.calculate_fill_size(
                    video_width, video_height, self.screen_width, video_display_height
                )
                display_width = self.screen_width
                display_height = video_display_height
                x = 0
                y = video_display_y
            else:  # stretch
                display_width = self.screen_width
                display_height = video_display_height
                x = 0
                y = video_display_y
                crop_x, crop_y, crop_w, crop_h = 0, 0, video_width, video_height

            frame_delay = int(1000 / fps) if fps > 0 else 33  # ms between frames

            logger.info(f"Playing video: {video_path.name} ({video_width}x{video_height} @ {fps:.1f}fps)")

            start_time = time.time()
            frame_start_time = start_time
            current_frame_idx = 0

            while self.running:
                # Handle events
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        cap.release()
                        self.running = False
                        return False
                    elif event.type == pg.KEYDOWN:
                        if event.key == pg.K_ESCAPE:
                            cap.release()
                            self.running = False
                            return False
                        elif event.key == pg.K_SPACE:
                            cap.release()
                            return True  # Skip to next
                        elif event.key == pg.K_q:
                            cap.release()
                            self.running = False
                            return False

                # Read frame
                ret, frame = cap.read()
                if not ret:
                    # End of video
                    break

                # Crop if in fill mode
                if self.scale_mode == 'fill':
                    frame = frame[crop_y:crop_y + crop_h, crop_x:crop_x + crop_w]

                # Resize frame
                if frame.shape[1] != display_width or frame.shape[0] != display_height:
                    frame = cv2.resize(frame, (display_width, display_height),
                                       interpolation=cv2.INTER_LINEAR)

                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Create pygame surface
                frame_surface = pg.image.frombuffer(
                    frame_rgb.tobytes(),
                    (display_width, display_height),
                    'RGB'
                )

                # Display frame
                self.screen.fill(self.bg_color)
                self.screen.blit(frame_surface, (x, y))

                # Update status bar with video progress
                current_time = time.time() - start_time
                remaining = max(0, duration - current_time)
                self._draw_statusbar_video(current_time, remaining, duration, current_frame_idx, frame_count)
                pg.display.flip()

                current_frame_idx += 1

                # Maintain frame rate timing
                elapsed = (time.time() - frame_start_time) * 1000
                wait_time = max(1, frame_delay - int(elapsed))
                time.sleep(wait_time / 1000.0)
                frame_start_time = time.time()

            cap.release()
            logger.info(f"Video playback finished: {video_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error displaying video {video_path}: {e}")
            return False

    def _draw_statusbar_video(self, current_time: float, remaining: float, duration: float,
                              frame_idx: int, total_frames: int):
        """Draw status bar with video playback info"""
        pg = get_pygame()
        if not self.show_statusbar or self.screen is None:
            return

        self._init_font()

        screen_width = self.screen_width
        screen_height = self.screen_height

        # Determine status bar position based on setting
        if self.statusbar_position == 'top':
            statusbar_y = 0
        else:  # 'bottom' or default
            statusbar_y = screen_height - self.statusbar_height

        statusbar_rect = pg.Rect(0, statusbar_y, screen_width, self.statusbar_height)

        # Draw status bar background
        pg.draw.rect(self.screen, self.statusbar_bg_color, statusbar_rect)

        # Format time as MM:SS
        def format_time(t):
            mins = int(t // 60)
            secs = int(t % 60)
            return f"{mins}:{secs:02d}"

        # Left side info (file info)
        left_texts = []
        if self.current_image_info:
            left_texts = [
                f"VIDEO: {self.current_image_info.get('name', '')}",
                f"{self.current_image_info.get('dimensions', '')}",
            ]

        # Video progress info
        progress_text = f"{format_time(current_time)} / {format_time(duration)}"
        if duration > 0:
            progress_pct = (current_time / duration) * 100
            progress_text += f" ({progress_pct:.0f}%)"

        # Right side info
        right_texts = [
            f"Res: {screen_width}x{screen_height}",
            f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}",
            f"WiFi: {self._get_wifi_signal()}",
            f"Media: {self.current_image_index + 1}/{len(self.images)}",
            progress_text,
        ]

        # Text vertical offset (center in status bar)
        y_offset = statusbar_y + 2

        # Render left text
        x_offset = 10
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

    def _signal_handler(self, signum, frame):
        """Handle signals for clean shutdown"""
        logger.info("Received signal, shutting down...")
        self.running = False

    def run(self, cache_dir: str):
        """Main slideshow loop"""
        pg = get_pygame()
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
        # Set last_change to 0 to trigger immediate display of first media
        last_change = 0
        last_sync = time.time()
        last_statusbar_update = time.time()

        # Count videos vs images
        video_count = sum(1 for img in self.images if self._is_video(img))
        image_count = len(self.images) - video_count
        logger.info(f"Starting slideshow with {len(self.images)} media files ({image_count} images, {video_count} videos)")

        # Import sync module for periodic updates
        from gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync()

        # Display first media immediately
        if self.images:
            media_path = self.images[self.current_image_index]
            if self._is_video(media_path):
                self.display_video(media_path)
            else:
                self.display_image(media_path)
            last_change = time.time()

        while self.running:
            try:
                # Ensure mouse cursor state matches setting
                if self.hide_mouse:
                    pg.mouse.set_visible(False)

                # Handle events
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        self.running = False
                    elif event.type == pg.KEYDOWN:
                        if event.key == pg.K_ESCAPE:
                            logger.info("ESC pressed, exiting...")
                            self.running = False
                        elif event.key == pg.K_SPACE:
                            # Skip to next image
                            last_change = 0
                        elif event.key == pg.K_q:
                            logger.info("Q pressed, exiting...")
                            self.running = False

                current_time = time.time()

                # Update status bar time/wifi every second
                if current_time - last_statusbar_update >= 1.0:
                    if self.show_statusbar and self.screen is not None:
                        countdown = self.interval - (current_time - last_change)
                        self._draw_statusbar(countdown)
                        pg.display.flip()
                    last_statusbar_update = current_time

                # Check if it's time to change image/video
                if current_time - last_change >= self.interval:
                    if self.images:
                        # Display next media
                        media_path = self.images[self.current_image_index]

                        if self._is_video(media_path):
                            # Play the full video
                            self.display_video(media_path)
                        else:
                            # Display image
                            self.display_image(media_path)

                        # Move to next media
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
        pg.quit()
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
