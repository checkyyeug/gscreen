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
import re
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
        self.rotation = self.display_settings.get('rotation', 0)  # Default: 0 (no rotation)
        self.rotation_mode = self.display_settings.get('rotation_mode', 'hardware')  # 'hardware' or 'software'

        # Audio settings
        self.audio_settings = self.settings.get('audio', {})
        self.audio_enabled = self.audio_settings.get('enabled', False)
        self.audio_device = self.audio_settings.get('device', 'hdmi')  # 'hdmi' or 'local' (3.5mm jack)
        self.audio_volume = self.audio_settings.get('volume', 50)

        # Schedule settings
        self.schedule_settings = self.settings.get('schedule', {})
        self.schedule_enabled = self.schedule_settings.get('enabled', False)
        self.schedule_days = self.schedule_settings.get('days', ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        self.schedule_start = self.schedule_settings.get('start', '07:00')
        self.schedule_stop = self.schedule_settings.get('stop', '23:00')

        # Status bar layout settings for landscape and portrait
        default_layout = {
            'opacity': 0.3,
            'landscape': {'file_info_position': 'top', 'progress_position': 'bottom'},
            'portrait': {'file_info_position': 'bottom', 'progress_position': 'top'}
        }
        self.statusbar_layout = self.display_settings.get('statusbar_layout', default_layout)

        # Status bar settings
        self.statusbar_height = 30
        self.statusbar_bg_color_base = (30, 30, 30)
        self.statusbar_opacity = self.statusbar_layout.get('opacity', 0.3)
        self.statusbar_bg_color = (*self.statusbar_bg_color_base, int(self.statusbar_opacity * 255))
        self.statusbar_text_color = (200, 200, 200)
        self.statusbar_font_size = 14

        # Runtime state
        self.running = False
        self.current_image_index = 0
        self.images: list[Path] = []
        self.screen = None
        self.virtual_screen = None
        self.virt_width = 0
        self.virt_height = 0
        self.screen_info = None
        self.screen_width = 0
        self.screen_height = 0
        self.display_mode = None  # 'fbcon', 'x11', or 'sdl-default'
        self.font = None
        self.last_sync_time = None
        self.screen_asleep = False  # Track if screen is in sleep mode
        self.error_message = None  # Current error message to display
        self.error_message_time = None  # When error message was set

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

    def _is_active_time(self) -> bool:
        """Check if current time is within the scheduled active time"""
        if not self.schedule_enabled:
            return True

        try:
            now = datetime.datetime.now()
            day_abbr = now.strftime('%a')  # Mon, Tue, Wed, etc.

            # Check if today is in the scheduled days
            if day_abbr not in self.schedule_days:
                return False

            # Parse start and stop times
            start_hour, start_min = map(int, self.schedule_start.split(':'))
            stop_hour, stop_min = map(int, self.schedule_stop.split(':'))

            # Create datetime objects for today's start and stop times
            start_time = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
            stop_time = now.replace(hour=stop_hour, minute=stop_min, second=0, microsecond=0)

            # Check if current time is within the active window
            return start_time <= now < stop_time
        except Exception as e:
            logger.error(f"Error checking schedule: {e}")
            return True  # Default to active if there's an error

    def _set_screen_power(self, on: bool):
        """Turn screen on or off"""
        if self.screen is None:
            return

        pg = get_pygame()
        if on:
            # Wake up screen
            if self.screen_asleep:
                logger.info("Waking up screen")
                self.screen_asleep = False
                # Clear to black
                self.screen.fill(self.bg_color)
                pg.display.flip()
        else:
            # Put screen to sleep - fill with black
            if not self.screen_asleep:
                logger.info("Putting screen to sleep")
                self.screen_asleep = True
                # Fill entire screen with black
                if self.rotation_mode == 'software' and self.virtual_screen is not None:
                    self.virtual_screen.fill((0, 0, 0))
                    if self.rotation in [90, 180, 270]:
                        self._apply_rotation_to_screen()
                    else:
                        self.screen.blit(self.virtual_screen, (0, 0))
                else:
                    self.screen.fill((0, 0, 0))
                pg.display.flip()

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
        """Draw status bar at configured positions based on orientation"""
        if self.virtual_screen is None:
            return

        # Apply software rotation if needed (must be done even if statusbar is hidden)
        if self.rotation_mode == 'software' and self.rotation in [90, 180, 270]:
            self._apply_rotation_to_screen()

        if not self.show_statusbar:
            return

        pg = get_pygame()
        self._init_font()

        screen_width = self.virt_width
        screen_height = self.virt_height

        # Determine orientation and get corresponding layout
        is_portrait = self.rotation in [90, 270]
        orientation = 'portrait' if is_portrait else 'landscape'
        layout = self.statusbar_layout.get(orientation, {
            'file_info_position': 'top' if not is_portrait else 'bottom',
            'system_info_position': 'top' if not is_portrait else 'bottom',
            'progress_position': 'bottom' if not is_portrait else 'top'
        })

        file_info_pos = layout.get('file_info_position', 'top' if not is_portrait else 'bottom')
        system_info_pos = layout.get('system_info_position', 'top' if not is_portrait else 'bottom')
        progress_pos = layout.get('progress_position', 'bottom' if not is_portrait else 'top')

        if self.rotation in [90, 270]:
            physical_res = f"{self.screen_height}x{self.screen_width}"
        else:
            physical_res = f"{self.screen_width}x{self.screen_height}"

        # Helper to draw semi-transparent status bar surface
        def create_statusbar_surface(width, height):
            s = pg.Surface((width, height), pg.SRCALPHA)
            alpha = int(self.statusbar_opacity * 255)
            s.fill((*self.statusbar_bg_color_base, alpha))
            return s

        # Prepare file info texts
        file_texts = []
        if self.current_image_info:
            name = self.current_image_info.get('name', '')
            if len(name) > 25:
                name = name[:22] + '...'
            file_texts = [
                f"{name}",
                f"{self.current_image_info.get('modified', '')}",
            ]
            dims = self.current_image_info.get('dimensions', '')
            if dims:
                file_texts.append(f"{dims}")
            fmt = self.current_image_info.get('format', '')
            if fmt:
                file_texts.append(f"{fmt}")

        # Prepare system info texts
        sys_texts = [
            f"{physical_res}",
            f"R:{self.rotation}°",
            f"{datetime.datetime.now().strftime('%H:%M:%S')}",
            f"WiFi:{self._get_wifi_signal()}",
        ]
        if self.last_sync_time:
            sync_str = self.last_sync_time.strftime('%H:%M')
            sys_texts.append(f"Sync:{sync_str}")
        sys_texts.append(f"Total:{len(self.images)}")

        # Prepare progress texts
        progress_text = f"{self.current_image_index + 1}/{len(self.images)}"
        countdown_text = f"{max(0, countdown):.0f}s"
        progress_full = f"{progress_text} {countdown_text}"

        # Helper to measure width of texts
        def measure_texts_width(texts, spacing=8):
            width = 0
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                width += text_surface.get_width() + spacing
            return width

        # Helper to draw text on left side of surface
        def draw_texts_left(surface, texts):
            y_offset = 2
            x_offset = 10
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                surface.blit(text_surface, (x_offset, y_offset))
                x_offset += text_surface.get_width() + 8

        # Helper to draw text on right side of surface
        def draw_texts_right(surface, texts):
            y_offset = 2
            x_offset = screen_width - 10
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                x_offset -= text_surface.get_width()
                surface.blit(text_surface, (x_offset, y_offset))
                x_offset -= 8

        # Helper to draw centered text
        def draw_text_center(surface, text):
            text_surface = self.font.render(text, True, self.statusbar_text_color)
            text_x = (screen_width - text_surface.get_width()) // 2
            surface.blit(text_surface, (text_x, 2))

        # Collect what to draw on each position (top/bottom)
        # Each position can have: left content (file_info), center content (progress), right content (system_info)
        position_content = {'top': {'left': None, 'center': None, 'right': None},
                         'bottom': {'left': None, 'center': None, 'right': None}}

        # Assign content to positions based on config
        position_content[file_info_pos]['left'] = file_texts
        position_content[system_info_pos]['right'] = sys_texts
        position_content[progress_pos]['center'] = progress_full

        # Draw each position
        for pos in ['top', 'bottom']:
            content = position_content[pos]
            if content['left'] is None and content['center'] is None and content['right'] is None:
                continue  # Nothing to draw on this position

            # Create surface for this position
            surface = create_statusbar_surface(screen_width, self.statusbar_height)
            y = 0 if pos == 'top' else screen_height - self.statusbar_height

            # Pre-calculate widths to check for overlaps
            left_width = measure_texts_width(content['left']) if content['left'] else 0
            right_width = measure_texts_width(content['right']) if content['right'] else 0

            # Render center text to get its width
            center_width = 0
            center_x = 0
            if content['center']:
                center_surface = self.font.render(content['center'], True, self.statusbar_text_color)
                center_width = center_surface.get_width()
                center_x = (screen_width - center_width) // 2

            # Determine which content can be drawn without overlap
            # Priority: left > right > center
            draw_center = True
            draw_right = True

            # Check if center overlaps with left
            if content['center'] and center_x < left_width + 20:
                draw_center = False

            # Check if center overlaps with right (right starts at screen_width - right_width - 10)
            if content['center'] and center_x + center_width > screen_width - right_width - 20:
                draw_center = False

            # If center is not drawn, check if right overlaps with left
            if not draw_center and content['right'] and screen_width - right_width - 10 < left_width + 20:
                draw_right = False

            # Now draw the content
            if content['left']:
                draw_texts_left(surface, content['left'])

            if draw_center and content['center']:
                draw_text_center(surface, content['center'])

            if draw_right and content['right']:
                draw_texts_right(surface, content['right'])

            # Clear the status bar area on screen first to avoid artifacts from previous semi-transparent draws
            clear_surface = pg.Surface((screen_width, self.statusbar_height))
            clear_surface.fill(self.bg_color)
            self.virtual_screen.blit(clear_surface, (0, y))
            # Then blit the semi-transparent status bar
            self.virtual_screen.blit(surface, (0, y))


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

    def _is_x11_running(self) -> bool:
        """Check if X11 is running by checking for X11 socket files"""
        for d in [0, 1]:
            if os.path.exists(f'/tmp/.X11-unix/X{d}'):
                return True
        return False

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

                # For software rotation, create a virtual screen with rotated dimensions
                # Content is drawn to virtual_screen, then rotated and blitted to physical screen
                if self.rotation_mode == 'software' and self.rotation in [90, 270]:
                    # Swap dimensions for 90/270 degree rotation
                    self.virt_width = screen_height
                    self.virt_height = screen_width
                    self.virtual_screen = pg.Surface((self.virt_width, self.virt_height))
                    logger.info(f"Software rotation mode: virtual screen {self.virt_width}x{self.virt_height} -> physical {screen_width}x{screen_height}")
                elif self.rotation_mode == 'software' and self.rotation == 180:
                    # 180 degree rotation - same dimensions but use separate virtual screen to avoid conflicts
                    self.virt_width = screen_width
                    self.virt_height = screen_height
                    self.virtual_screen = pg.Surface((self.virt_width, self.virt_height))
                    logger.info(f"Software 180 degree rotation mode: virtual screen {self.virt_width}x{self.virt_height} -> physical {screen_width}x{screen_height}")
                else:
                    # Hardware rotation or 0 degree rotation - use screen directly
                    self.virtual_screen = self.screen
                    self.virt_width = screen_width
                    self.virt_height = screen_height

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
        Status bar overlays on top, so image uses full screen.

        Returns: (x, y, width, height)
        """
        # Use full screen (status bar is overlay)
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
        Status bar overlays on top, so image uses full screen.
        """
        # Use full screen (status bar is overlay)
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

            # Use PIL for better image loading
            if Image is not None:
                pil_image = Image.open(image_path)

                # Convert to RGB if necessary
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')

                img_width, img_height = pil_image.size
                # Use virtual screen dimensions for software rotation mode
                screen_width = self.virt_width
                screen_height = self.virt_height

                # Calculate dimensions based on scale mode
                if self.scale_mode == 'fit':
                    x, y, new_width, new_height = self.calculate_fit_size(
                        img_width, img_height, screen_width, screen_height
                    )
                    # Resize and place
                    pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    # Create background and paste
                    background = Image.new('RGB', (screen_width, screen_height), self.bg_color)
                    background.paste(pil_image, (x, y))
                    pil_image = background
                elif self.scale_mode == 'fill':
                    # Fill mode - crop to fill screen
                    crop_x, crop_y, crop_w, crop_h = self.calculate_fill_size(
                        img_width, img_height, screen_width, screen_height
                    )
                    pil_image = pil_image.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
                    pil_image = pil_image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
                else:  # stretch
                    pil_image = pil_image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)

                # Convert to pygame surface
                img_surface = pg.image.fromstring(
                    pil_image.tobytes(),
                    pil_image.size,
                    pil_image.mode
                )
            else:
                # Fallback to pygame only
                img_surface = pg.image.load(str(image_path))
                # Use virtual screen dimensions
                screen_width = self.virt_width
                screen_height = self.virt_height
                img_surface = pg.transform.scale(
                    img_surface,
                    (screen_width, screen_height)
                )

            # Display
            # Determine target screen based on rotation mode
            if self.rotation_mode == 'software':
                target_screen = self.virtual_screen
            else:
                target_screen = self.screen

            target_screen.fill(self.bg_color)
            target_screen.blit(img_surface, (0, 0))

            # Draw status bar (handles rotation internally)
            self._draw_statusbar()

            # Flip the display
            pg.display.flip()

            logger.debug(f"Displayed: {image_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error displaying {image_path}: {e}")
            return False

    def display_video(self, video_path: Path) -> bool:
        """Load and display a video file"""
        # If audio is enabled, use ffplay for audio+video playback
        if self.audio_enabled:
            return self._display_video_with_audio(video_path)
        # Otherwise use OpenCV for video-only playback
        return self._display_video_opencv(video_path)

    def _display_video_with_audio(self, video_path: Path) -> bool:
        """Play video with audio using ffplay"""
        import subprocess
        import os

        try:
            # Get video info for status bar
            self.current_image_path = video_path
            self.current_image_info = self._get_video_info(video_path)

            logger.info(f"Playing video with audio: {video_path.name}")

            # Build ffplay command
            # Use DRM/KMS display if available, otherwise use X11
            display_env = os.environ.get('DISPLAY', '')

            # Audio output device: 0=HDMI, 1=local (3.5mm jack)
            audio_device_map = {'hdmi': '0', 'local': '1'}
            alsa_device = audio_device_map.get(self.audio_device, '0')

            # Build ffplay command
            ffplay_cmd = [
                'ffplay',
                '-vn',  # Don't play video (we'll handle display)
                '-nodisp',  # Don't display ffplay window
                '-autoexit',
                '-volume', str(self.audio_volume),
                '-audio_demuxer', 'ffmpeg',
                '-i', str(video_path),
                '-ao', f'alsa:{alsa_device}'
            ]

            # Start ffplay for audio in background
            ffplay_process = subprocess.Popen(
                ffplay_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )

            # Play video without audio using OpenCV
            result = self._display_video_opencv(video_path, skip_audio_check=True)

            # Clean up ffplay process
            try:
                ffplay_process.terminate()
                ffplay_process.wait(timeout=2)
            except:
                try:
                    ffplay_process.kill()
                except:
                    pass

            return result

        except FileNotFoundError:
            logger.warning("ffplay not found. Install ffmpeg for audio support. Falling back to video-only.")
            return self._display_video_opencv(video_path)
        except Exception as e:
            logger.error(f"Error playing video with audio: {e}")
            return self._display_video_opencv(video_path)

    def _display_video_opencv(self, video_path: Path, skip_audio_check: bool = False) -> bool:
        """Load and display a video file using OpenCV (video only)"""
        pg = get_pygame()
        if cv2 is None:
            logger.error("OpenCV (cv2) is not installed. Install with: pip install opencv-python")
            return False

        try:
            # Get video info for status bar
            if not skip_audio_check:
                self.current_image_path = video_path
                self.current_image_info = self._get_video_info(video_path)

            # Video uses full virtual screen (status bar is overlay)
            video_display_y = 0
            video_display_height = self.virt_height

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
                    video_width, video_height, self.virt_width, video_display_height
                )
                y += video_display_y  # Adjust for status bar offset
            elif self.scale_mode == 'fill':
                # For fill mode in video, we'll use crop calculation
                crop_x, crop_y, crop_w, crop_h = self.calculate_fill_size(
                    video_width, video_height, self.virt_width, video_display_height
                )
                display_width = self.virt_width
                display_height = video_display_height
                x = 0
                y = video_display_y
            else:  # stretch
                display_width = self.virt_width
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
                # Determine target screen based on rotation mode
                if self.rotation_mode == 'software':
                    target_screen = self.virtual_screen
                else:
                    target_screen = self.screen

                target_screen.fill(self.bg_color)
                target_screen.blit(frame_surface, (x, y))

                # Update status bar with video progress
                current_time = time.time() - start_time
                remaining = max(0, duration - current_time)
                self._draw_statusbar_video(current_time, remaining, duration, current_frame_idx, frame_count)

                # Apply software rotation if needed
                if self.rotation_mode == 'software':
                    self._apply_rotation_to_screen()

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

    def _apply_rotation_to_screen(self):
        """Apply software rotation to virtual screen and display on physical screen"""
        if self.rotation_mode == 'software' and self.rotation in [90, 270]:
            pg = get_pygame()
            # Clear the physical screen first to avoid artifacts
            self.screen.fill(self.bg_color)
            rotated = pg.transform.rotate(self.virtual_screen, -self.rotation)
            # Center the rotated surface on the physical screen
            rot_rect = rotated.get_rect(center=(self.screen_width // 2, self.screen_height // 2))
            self.screen.blit(rotated, rot_rect)
        elif self.rotation_mode == 'software' and self.rotation == 180:
            # 180 degree rotation - virtual_screen has same dimensions as physical screen
            pg = get_pygame()
            # Clear the physical screen first
            self.screen.fill(self.bg_color)
            rotated = pg.transform.rotate(self.virtual_screen, 180)
            self.screen.blit(rotated, (0, 0))
        else:
            # No rotation needed or hardware rotation - virtual_screen is already the screen
            pass

    def _draw_statusbar_video(self, current_time: float, remaining: float, duration: float,
                              frame_idx: int, total_frames: int):
        """Draw status bar with video playback info using configured layout"""
        pg = get_pygame()
        if not self.show_statusbar or self.screen is None:
            return

        self._init_font()

        # Use virtual screen dimensions for software rotation mode
        screen_width = self.virt_width
        screen_height = self.virt_height

        # Determine orientation and get corresponding layout (same as images)
        is_portrait = self.rotation in [90, 270]
        orientation = 'portrait' if is_portrait else 'landscape'
        layout = self.statusbar_layout.get(orientation, {
            'file_info_position': 'top' if not is_portrait else 'bottom',
            'system_info_position': 'top' if not is_portrait else 'bottom',
            'progress_position': 'bottom' if not is_portrait else 'top'
        })

        file_info_pos = layout.get('file_info_position', 'top' if not is_portrait else 'bottom')
        system_info_pos = layout.get('system_info_position', 'top' if not is_portrait else 'bottom')
        progress_pos = layout.get('progress_position', 'bottom' if not is_portrait else 'top')

        if self.rotation in [90, 270]:
            physical_res = f"{self.screen_height}x{self.screen_width}"
        else:
            physical_res = f"{self.screen_width}x{self.screen_height}"

        # Helper to create status bar surface
        def create_statusbar_surface(width, height):
            s = pg.Surface((width, height), pg.SRCALPHA)
            alpha = int(self.statusbar_opacity * 255)
            s.fill((*self.statusbar_bg_color_base, alpha))
            return s

        # Format time as MM:SS
        def format_time(t):
            mins = int(t // 60)
            secs = int(t % 60)
            return f"{mins}:{secs:02d}"

        # Prepare file info texts
        file_texts = []
        if self.current_image_info:
            file_texts = [
                f"VIDEO: {self.current_image_info.get('name', '')}",
                f"{self.current_image_info.get('dimensions', '')}",
            ]

        # Prepare system info texts
        sys_texts = [
            f"Res: {physical_res}",
            f"R:{self.rotation}°",
            f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}",
            f"WiFi: {self._get_wifi_signal()}",
            f"Media: {self.current_image_index + 1}/{len(self.images)}",
        ]

        # Prepare progress texts
        progress_text = f"{format_time(current_time)} / {format_time(duration)}"
        if duration > 0:
            progress_pct = (current_time / duration) * 100
            progress_text += f" ({progress_pct:.0f}%)"

        # Helper to measure width of texts
        def measure_texts_width(texts, spacing=15):
            width = 0
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                width += text_surface.get_width() + spacing
            return width

        # Helper to draw text on left side of surface
        def draw_texts_left(surface, texts):
            y_offset = 2
            x_offset = 10
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                surface.blit(text_surface, (x_offset, y_offset))
                x_offset += text_surface.get_width() + 15

        # Helper to draw text on right side of surface
        def draw_texts_right(surface, texts):
            y_offset = 2
            x_offset = screen_width - 10
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                x_offset -= text_surface.get_width()
                surface.blit(text_surface, (x_offset, y_offset))
                x_offset -= 15

        # Helper to draw centered text
        def draw_text_center(surface, text):
            text_surface = self.font.render(text, True, self.statusbar_text_color)
            text_x = (screen_width - text_surface.get_width()) // 2
            surface.blit(text_surface, (text_x, 2))


        # Collect what to draw on each position (top/bottom)
        # Each position can have: left content (file_info), center content (progress), right content (system_info)
        position_content = {'top': {'left': None, 'center': None, 'right': None},
                         'bottom': {'left': None, 'center': None, 'right': None}}

        # Assign content to positions based on config
        position_content[file_info_pos]['left'] = file_texts
        position_content[system_info_pos]['right'] = sys_texts
        position_content[progress_pos]['center'] = progress_text

        # Draw each position
        for pos in ['top', 'bottom']:
            content = position_content[pos]
            if content['left'] is None and content['center'] is None and content['right'] is None:
                continue  # Nothing to draw on this position

            # Create surface for this position
            surface = create_statusbar_surface(screen_width, self.statusbar_height)
            y = 0 if pos == 'top' else screen_height - self.statusbar_height

            # Pre-calculate widths to check for overlaps
            left_width = measure_texts_width(content['left']) if content['left'] else 0
            right_width = measure_texts_width(content['right']) if content['right'] else 0

            # Render center text to get its width
            center_width = 0
            center_x = 0
            if content['center']:
                center_surface = self.font.render(content['center'], True, self.statusbar_text_color)
                center_width = center_surface.get_width()
                center_x = (screen_width - center_width) // 2

            # Determine which content can be drawn without overlap
            # Priority: left > right > center
            draw_center = True
            draw_right = True

            # Check if center overlaps with left
            if content['center'] and center_x < left_width + 20:
                draw_center = False

            # Check if center overlaps with right (right starts at screen_width - right_width - 10)
            if content['center'] and center_x + center_width > screen_width - right_width - 20:
                draw_center = False

            # If center is not drawn, check if right overlaps with left
            if not draw_center and content['right'] and screen_width - right_width - 10 < left_width + 20:
                draw_right = False

            # Now draw the content
            if content['left']:
                draw_texts_left(surface, content['left'])

            if draw_center and content['center']:
                draw_text_center(surface, content['center'])

            if draw_right and content['right']:
                draw_texts_right(surface, content['right'])

            # Clear the status bar area on screen first to avoid artifacts from previous semi-transparent draws
            clear_surface = pg.Surface((screen_width, self.statusbar_height))
            clear_surface.fill(self.bg_color)
            target = self.virtual_screen if self.rotation_mode == 'software' else self.screen
            target.blit(clear_surface, (0, y))
            # Then blit the semi-transparent status bar
            target.blit(surface, (0, y))


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

        # If no images found, try to sync first
        if not self.images:
            logger.warning("No media files found, attempting sync...")
            from gdrive_sync import GoogleDriveSync
            sync = GoogleDriveSync()
            try:
                sync.sync()
            except Exception as e:
                logger.error(f"Sync failed: {e}", exc_info=True)
                self._show_error_message(f"同步失败: {str(e)}")
            # Reload images after sync
            self.images = self.load_images(cache_dir)

        if not self.images:
            logger.warning("No media files to display even after sync. Please check your Google Drive folder.")
            self._show_no_media_message()
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

        # Check schedule at startup - if outside active time, show countdown
        if not self._is_active_time():
            self._show_sleep_countdown()

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

                # Check schedule - sleep if outside active time
                is_active = self._is_active_time()
                if not is_active:
                    if not self.screen_asleep:
                        self._set_screen_power(False)
                    time.sleep(5)  # Sleep longer when inactive
                    continue
                else:
                    if self.screen_asleep:
                        self._set_screen_power(True)
                        # Force display first image when waking up
                        last_change = 0

                # Update status bar time/wifi every second
                if current_time - last_statusbar_update >= 1.0:
                    if self.show_statusbar and self.screen is not None:
                        countdown = self.interval - (current_time - last_change)
                        self._draw_statusbar(countdown)
                        # Apply software rotation if needed
                        if self.rotation_mode == 'software':
                            self._apply_rotation_to_screen()
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
                    try:
                        sync.sync()
                    except Exception as e:
                        logger.error(f"Sync failed: {e}", exc_info=True)
                        self._show_error_message(f"同步失败: {str(e)}")
                    self.images = self.load_images(cache_dir)
                    self.last_sync_time = datetime.datetime.now()
                    # Reset index if out of bounds
                    if self.current_image_index >= len(self.images):
                        self.current_image_index = 0
                    last_sync = current_time

                # Display error message if any
                if self.error_message and time.time() - self.error_message_time < 30:
                    self._show_error_message(self.error_message)

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

    def _show_no_media_message(self):
        """Display a message when no media files are available and wait for files"""
        import time
        pg = get_pygame()

        self._init_font()

        # Create a larger font for the no-media message
        try:
            message_font = pg.font.SysFont('DejaVuSans', 32, bold=True)
        except:
            message_font = pg.font.Font(None, 48)

        # Screen dimensions
        screen_width = self.virt_width
        screen_height = self.virt_height

        # Messages to display
        messages = [
            "No Media Files Found",
            "Waiting for files from Google Drive...",
            "Press ESC to exit"
        ]

        # For sync checking
        from gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync()
        last_sync = time.time()
        sync_interval = self.settings['sync']['check_interval_minutes'] * 60

        logger.info("Displaying 'no media' message and waiting for files...")

        waiting = True
        while waiting:
            try:
                # Handle events
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        waiting = False
                    elif event.type == pg.KEYDOWN:
                        if event.key == pg.K_ESCAPE:
                            logger.info("ESC pressed, exiting...")
                            waiting = False
                        elif event.key == pg.K_r:
                            # Manual sync trigger
                            logger.info("Manual sync triggered (R key)")
                            try:
                                sync.sync()
                            except Exception as e:
                                logger.error(f"Sync failed: {e}", exc_info=True)
                                self._show_error_message(f"同步失败: {str(e)}")
                            # Check for new files
                            self.images = self.load_images(self.cache_dir)
                            if self.images:
                                logger.info(f"Found {len(self.images)} media file(s) after sync")
                                waiting = False
                                return  # Exit waiting mode

                # Clear screen with background color
                if self.virtual_screen:
                    self.virtual_screen.fill(self.background_color)
                else:
                    self.screen.fill(self.background_color)

                # Draw messages centered
                y_offset = screen_height // 2 - (len(messages) * 50) // 2
                for msg in messages:
                    text_surface = message_font.render(msg, True, (200, 200, 200))
                    text_x = (screen_width - text_surface.get_width()) // 2
                    if self.virtual_screen:
                        self.virtual_screen.blit(text_surface, (text_x, y_offset))
                    else:
                        self.screen.blit(text_surface, (text_x, y_offset))
                    y_offset += 50

                # Update display
                if self.virtual_screen and self.physical_screen:
                    pg.transform.scale(self.virtual_screen, (self.screen_width, self.screen_height), self.physical_screen)
                pg.display.flip()

                # Periodic sync check
                current_time = time.time()
                if current_time - last_sync >= sync_interval:
                    logger.info("Periodic sync check...")
                    try:
                        sync.sync()
                    except Exception as e:
                        logger.error(f"Sync failed: {e}", exc_info=True)
                        self._show_error_message(f"同步失败: {str(e)}")
                    last_sync = current_time
                    # Check for new files
                    self.images = self.load_images(self.cache_dir)
                    if self.images:
                        logger.info(f"Found {len(self.images)} media file(s) after sync")
                        waiting = False
                        return  # Exit waiting mode and continue to slideshow

                # Small sleep to prevent high CPU usage
                time.sleep(0.1)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                waiting = False
            except Exception as e:
                logger.error(f"Error in no-media wait mode: {e}", exc_info=True)
                time.sleep(1)

    def _show_sleep_countdown(self):
        """Display 60-second countdown when outside schedule, then go to sleep"""
        import time
        pg = get_pygame()

        self._init_font()

        # Create fonts for the countdown
        try:
            large_font = pg.font.SysFont('DejaVuSans', 48, bold=True)
            medium_font = pg.font.SysFont('DejaVuSans', 28, bold=True)
        except:
            large_font = pg.font.Font(None, 64)
            medium_font = pg.font.Font(None, 40)

        # Screen dimensions
        screen_width = self.virt_width
        screen_height = self.virt_height

        # Countdown duration
        countdown_seconds = 60
        start_time = time.time()

        logger.info("Outside schedule - showing sleep countdown...")

        counting_down = True
        while counting_down:
            try:
                # Handle events - allow early exit with ESC
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        counting_down = False
                        self.running = False
                        return
                    elif event.type == pg.KEYDOWN:
                        if event.key == pg.K_ESCAPE:
                            logger.info("ESC pressed, exiting...")
                            counting_down = False
                            self.running = False
                            return

                # Calculate remaining time
                elapsed = time.time() - start_time
                remaining = max(0, int(countdown_seconds - elapsed))

                # Clear screen with background color
                if self.virtual_screen:
                    self.virtual_screen.fill(self.background_color)
                else:
                    self.screen.fill(self.background_color)

                # Draw messages
                # Main message
                main_msg = "不在 Schedule 内"
                main_surface = medium_font.render(main_msg, True, (255, 100, 100))
                main_x = (screen_width - main_surface.get_width()) // 2
                main_y = screen_height // 2 - 60

                # Sub message
                sub_msg = "准备 Sleep"
                sub_surface = medium_font.render(sub_msg, True, (200, 200, 200))
                sub_x = (screen_width - sub_surface.get_width()) // 2
                sub_y = screen_height // 2

                # Countdown
                countdown_msg = f"{remaining} 秒"
                countdown_surface = large_font.render(countdown_msg, True, (255, 255, 255))
                countdown_x = (screen_width - countdown_surface.get_width()) // 2
                countdown_y = screen_height // 2 + 60

                # Blit messages
                if self.virtual_screen:
                    self.virtual_screen.blit(main_surface, (main_x, main_y))
                    self.virtual_screen.blit(sub_surface, (sub_x, sub_y))
                    self.virtual_screen.blit(countdown_surface, (countdown_x, countdown_y))
                else:
                    self.screen.blit(main_surface, (main_x, main_y))
                    self.screen.blit(sub_surface, (sub_x, sub_y))
                    self.screen.blit(countdown_surface, (countdown_x, countdown_y))

                # Update display
                if self.virtual_screen and self.physical_screen:
                    pg.transform.scale(self.virtual_screen, (self.screen_width, self.screen_height), self.physical_screen)
                pg.display.flip()

                # Check if countdown is finished
                if remaining <= 0:
                    logger.info("Countdown finished, going to sleep")
                    counting_down = False

                # Small sleep
                time.sleep(0.05)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                counting_down = False
                self.running = False
            except Exception as e:
                logger.error(f"Error in countdown mode: {e}", exc_info=True)
                time.sleep(0.1)

    def _show_error_message(self, message: str):
        """Display error message in red on screen"""
        pg = get_pygame()

        # Store error message to display periodically
        self.error_message = message
        self.error_message_time = time.time()

        # Create fonts for error display
        try:
            error_font = pg.font.SysFont('DejaVuSans', 32, bold=True)
        except:
            error_font = pg.font.Font(None, 40)

        # Screen dimensions
        screen_width = self.virt_width
        screen_height = self.virt_height

        # Draw error message in red
        text_surface = error_font.render(message, True, (255, 50, 50))
        text_x = (screen_width - text_surface.get_width()) // 2
        text_y = screen_height - 100

        if self.virtual_screen:
            self.virtual_screen.blit(text_surface, (text_x, text_y))
        else:
            self.screen.blit(text_surface, (text_x, text_y))

        # Update display
        if self.virtual_screen and self.physical_screen:
            pg.transform.scale(self.virtual_screen, (self.screen_width, self.screen_height), self.physical_screen)
        pg.display.flip()

    def _clear_error_message(self):
        """Clear stored error message"""
        self.error_message = None


def main():
    """Main entry point"""
    import sys

    # Get cache directory from settings or use default
    try:
        with open("settings.json", 'r') as f:
            settings = json.load(f)
        cache_dir = settings['sync']['local_cache_dir']
    except:
        cache_dir = "./media"

    slideshow = SlideshowDisplay()
    slideshow.run(cache_dir)


if __name__ == "__main__":
    main()
