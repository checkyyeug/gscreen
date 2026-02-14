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
import gc
import threading
import queue
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from contextlib import contextmanager
# Don't import pygame yet - we need to set SDL_VIDEODRIVER first
pygame = None
_pygame_lock = threading.Lock()

def get_pygame():
    global pygame
    if pygame is not None:
        return pygame
    with _pygame_lock:
        # Double-check after acquiring lock
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
    try:
        from PIL import UnidentifiedImageError as PILUnidentifiedImageError
    except ImportError:
        PILUnidentifiedImageError = None
except ImportError:
    Image = None
    PILUnidentifiedImageError = None

try:
    import cv2
except ImportError:
    cv2 = None

# SD Card Protection: Setup logging (will be reconfigured in SlideshowDisplay.__init__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SlideshowDisplay:
    """Fullscreen slideshow display for HDMI output with status bar"""

    def __init__(self, settings_path: str = "settings.json"):
        self.settings_path = settings_path
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

        # System settings (SD card protection)
        self.system_settings = self.settings.get('system', {})
        self.weekly_auto_restart = self.system_settings.get('weekly_auto_restart', True)  # Default: enabled

        # Parse weekly_restart_day: support both string ("Mon"..."Sun") and integer (0=Sun, 1=Mon) for backward compatibility
        restart_day_config = self.system_settings.get('weekly_restart_day', 'Sun')
        self.weekly_restart_day = self._parse_restart_day(restart_day_config)

        # Restart time uses schedule.start (e.g., if display starts at 07:00, restart at 07:00)
        self._restart_scheduled = False
        self._restart_check_interval = 3600  # Check every hour

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

        # Sync settings
        self.sync_interval = self.settings['sync']['check_interval_minutes'] * 60
        self._last_sync_time = time.time()
        self._sync_instance = None

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
        self.was_active_time = True  # Track previous schedule state for countdown
        self.error_message_time = None  # When error message was set

        # Image cache to avoid repeated loading/scaling
        self._image_cache = {}  # {(path, width, height, scale_mode): (surface, bytesize)}
        self._max_cache_size = 50  # Maximum number of cached images
        self._max_cache_memory_mb = 100  # Maximum cache memory in MB
        self._cache_access_order = []  # Track access order for LRU eviction
        self._cache_lock = threading.Lock()  # Thread-safe cache access

        # Thread-safe locks for shared state
        self._state_lock = threading.Lock()  # For error_message, _last_sync_time
        self._gc_lock = threading.Lock()  # For _last_gc_time

        # Current image info
        self.current_image_path = None
        self.current_image_info = {}

        # Memory management: periodic garbage collection
        self._last_gc_time = time.time()
        self._gc_interval = 300  # Run GC every 5 minutes (300 seconds)
        self._frame_count = 0  # Track frames for more frequent light cleanup

        # Surface memory pool for video playback (prevents memory fragmentation)
        self._surface_pool: List[pg.Surface] = []
        self._surface_pool_max = 3  # Keep only a few surfaces in pool
        self._surface_pool_lock = threading.Lock()

        # WiFi signal cache (reduces subprocess calls)
        self._wifi_signal_cache = ("N/A", 0)
        self._wifi_cache_ttl = 30  # 30 seconds cache

        # Hardware video acceleration (will be set by _detect_hw_accel)
        self.hw_accel_method = None  # 'v4l2m2m', 'drm', or None
        self.hw_accel_enabled = self._detect_hw_accel()

    def _parse_restart_day(self, day_config) -> int:
        """Parse restart day from config, supporting both string and integer formats.

        String format: "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"
        Integer format (legacy): 0=Sunday, 1=Monday, ..., 6=Saturday

        Returns: Python weekday (0=Monday, ..., 6=Sunday)
        """
        # Day name to weekday mapping (Python: 0=Monday, 6=Sunday)
        DAY_TO_WEEKDAY = {
            'Mon': 0, 'Monday': 0,
            'Tue': 1, 'Tuesday': 1,
            'Wed': 2, 'Wednesday': 2,
            'Thu': 3, 'Thursday': 3,
            'Fri': 4, 'Friday': 4,
            'Sat': 5, 'Saturday': 5,
            'Sun': 6, 'Sunday': 6,
        }

        # If string, look up in mapping
        if isinstance(day_config, str):
            return DAY_TO_WEEKDAY.get(day_config.capitalize(), 6)  # Default to Sunday

        # Legacy integer format: 0=Sunday, 1=Monday, ..., 6=Saturday
        # Convert to Python weekday: 0=Monday, ..., 6=Sunday
        if isinstance(day_config, int):
            if day_config == 0:  # Sunday
                return 6
            else:  # 1=Monday -> 0, 2=Tuesday -> 1, ..., 6=Saturday -> 5
                return day_config - 1

        # Default to Sunday if invalid
        return 6

    def _detect_hw_accel(self) -> bool:
        """Detect if hardware video acceleration is available"""
        # Check for ffmpeg with hardware acceleration support
        try:
            result = subprocess.run(
                ['ffmpeg', '-hwaccels'],
                capture_output=True,
                text=True,
                timeout=2
            )
            hwaccels = result.stdout

            # Check for V4L2 M2M (VideoCore VI on Raspberry Pi)
            if 'v4l2m2m' in hwaccels:
                self.hw_accel_method = 'v4l2m2m'
                logger.info("Hardware acceleration detected: v4l2m2m (VideoCore VI)")
                return True

            # Check for other methods
            if 'drm' in hwaccels:
                self.hw_accel_method = 'drm'
                logger.info("Hardware acceleration detected: drm")
                return True

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check for V4L2 devices (fallback detection)
        try:
            v4l2_devices = list(Path('/dev').glob('video*'))
            if v4l2_devices:
                logger.info(f"V4L2 devices found: {len(v4l2_devices)}, trying hardware acceleration")
                self.hw_accel_method = 'v4l2m2m'
                return True
        except (OSError, PermissionError):
            pass

        logger.info("No hardware acceleration detected, using CPU decoding")
        self.hw_accel_method = None
        return False

    def _load_settings(self, path: str) -> dict:
        """Load and validate settings from JSON file"""
        try:
            with open(path, 'r') as f:
                settings = json.load(f)
        except FileNotFoundError:
            logger.error(f"Settings file not found: {path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in settings file: {e}")
            raise

        # Validate settings
        try:
            from config_validation import validate_settings
            validate_settings(settings)
        except ImportError:
            logger.warning("config_validation module not found, skipping validation")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

        return settings

    def _get_wifi_signal(self) -> str:
        """Get WiFi signal strength in dBm with caching"""
        now = time.time()
        cached_signal, cached_time = self._wifi_signal_cache
        
        # Return cached value if still valid
        if now - cached_time < self._wifi_cache_ttl:
            return cached_signal
        
        signal = "N/A"

        # Try iwconfig first (more reliable)
        try:
            result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=1)
            if 'Signal level' in result.stdout:
                match = re.search(r'Signal level=(-?\d+) dBm', result.stdout)
                if match:
                    signal = f"{match.group(1)} dBm"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        # Fallback: try /proc/net/wireless
        if signal == "N/A":
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
                                signal = f"{signal} dBm"
            except (OSError, ValueError, IndexError):
                pass

        # Update cache
        self._wifi_signal_cache = (signal, now)
        return signal

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
        except (ValueError, AttributeError) as e:
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

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _format_file_time(self, mtime: float) -> str:
        """Format modification time in readable format"""
        mod_time = datetime.datetime.fromtimestamp(mtime)
        return mod_time.strftime("%Y-%m-%d %H:%M")

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
            info['size'] = self._format_file_size(size_bytes)

            # Modification date
            info['modified'] = self._format_file_time(image_path.stat().st_mtime)

            # Image dimensions
            if Image is not None:
                with Image.open(image_path) as img:
                    info['dimensions'] = f"{img.width}x{img.height}"
        except (OSError, IOError) as e:
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
            info['size'] = self._format_file_size(size_bytes)

            # Modification date
            info['modified'] = self._format_file_time(video_path.stat().st_mtime)

            # Video info using cv2
            if cv2 is not None:
                cap = cv2.VideoCapture(str(video_path))
                if cap.isOpened():
                    try:
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        duration = frame_count / fps if fps > 0 else 0

                        info['dimensions'] = f"{width}x{height}"
                        info['duration'] = f"{int(duration // 60)}:{int(duration % 60):02d}"
                    finally:
                        cap.release()
                else:
                    cap.release()
        except (OSError, IOError, ValueError, ZeroDivisionError, cv2.error) as e:
            logger.debug(f"Error getting video info: {e}")

        return info

    def _init_font(self):
        """Initialize font for status bar"""
        if self.font is None:
            pg = get_pygame()
            try:
                # Try Noto Sans CJK for Chinese/Japanese/Korean support
                self.font = pg.font.SysFont('Noto Sans CJK SC', self.statusbar_font_size, bold=True)
            except (pg.error, FileNotFoundError):
                try:
                    # Fallback to DejaVuSans
                    self.font = pg.font.SysFont('DejaVuSans', self.statusbar_font_size, bold=True)
                except (pg.error, FileNotFoundError):
                    # Fallback to default font
                    self.font = pg.font.Font(None, self.statusbar_font_size)

    def _get_statusbar_layout_config(self):
        """
        Get common status bar layout configuration.

        Returns a dict with:
        - screen_width, screen_height: virtual screen dimensions
        - layout: the layout configuration for current orientation
        - file_info_pos, system_info_pos, progress_pos: position settings
        - physical_res: formatted resolution string
        """
        screen_width = self.virt_width
        screen_height = self.virt_height

        # Determine orientation and get corresponding layout
        is_portrait = self.rotation in [90, 270]
        orientation = 'portrait' if is_portrait else 'landscape'
        layout = self.statusbar_layout.get(orientation, {
            'file_info_position': 'top' if not is_portrait else 'bottom',
            'system_info_position': 'bottom' if not is_portrait else 'top',
            'progress_position': 'bottom' if not is_portrait else 'top'
        })

        file_info_pos = layout.get('file_info_position', 'top' if not is_portrait else 'bottom')
        system_info_pos = layout.get('system_info_position', 'bottom' if not is_portrait else 'top')
        progress_pos = layout.get('progress_position', 'bottom' if not is_portrait else 'top')

        # Determine physical resolution based on rotation
        if self.rotation in [90, 270]:
            physical_res = f"{self.screen_height}x{self.screen_width}"
        else:
            physical_res = f"{self.screen_width}x{self.screen_height}"

        return {
            'screen_width': screen_width,
            'screen_height': screen_height,
            'layout': layout,
            'file_info_pos': file_info_pos,
            'system_info_pos': system_info_pos,
            'progress_pos': progress_pos,
            'physical_res': physical_res
        }

    def _draw_statusbar(self, countdown: float):
        """Draw status bar at configured positions based on orientation"""
        if self.virtual_screen is None:
            return

        pg = get_pygame()
        self._init_font()

        # Get common layout configuration
        config = self._get_statusbar_layout_config()
        screen_width = config['screen_width']
        screen_height = config['screen_height']
        layout = config['layout']
        file_info_pos = config['file_info_pos']
        system_info_pos = config['system_info_pos']
        progress_pos = config['progress_pos']
        physical_res = config['physical_res']

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
        # Use the countdown parameter passed in, default to 0 if None
        countdown_val = countdown if countdown is not None else 0
        countdown_text = f"{countdown_val:.0f}s"

        progress_full = f"{progress_text} {countdown_text}"
        # Call common rendering method
        self._render_statusbar_common(
            screen_width, screen_height, layout,
            file_info_pos, system_info_pos, progress_pos,
            file_texts, sys_texts, progress_full
        )

    def _render_statusbar_common(self, screen_width: int, screen_height: int, layout: dict,
                               file_info_pos: str, system_info_pos: str, progress_pos: str,
                               file_texts: list, sys_texts: list, progress_text: str,
                               text_spacing: int = 8, countdown: float = 0):
        """Common status bar rendering logic shared by image and video display"""
        pg = get_pygame()

        # Helper to create status bar surface
        def create_statusbar_surface(width, height):
            s = pg.Surface((width, height), pg.SRCALPHA)
            alpha = int(self.statusbar_opacity * 255)
            s.fill((*self.statusbar_bg_color_base, alpha))
            return s

        # Helper to measure width of texts without creating persistent surfaces
        def measure_texts_width(texts, spacing=text_spacing):
            width = 0
            for text in texts:
                # Use size() which doesn't create a surface
                text_size = self.font.size(text)
                width += text_size[0] + spacing
            return width

        # Helper to draw text on left side of surface
        def draw_texts_left(surface, texts):
            y_offset = 2
            x_offset = 10
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                surface.blit(text_surface, (x_offset, y_offset))
                x_offset += text_surface.get_width() + text_spacing
                # Explicitly delete to help GC
                del text_surface

        # Helper to draw text on right side of surface
        def draw_texts_right(surface, texts):
            y_offset = 2
            x_offset = screen_width - 10
            for text in texts:
                text_surface = self.font.render(text, True, self.statusbar_text_color)
                x_offset -= text_surface.get_width()
                surface.blit(text_surface, (x_offset, y_offset))
                x_offset -= text_spacing
                del text_surface

        # Helper to draw centered text
        def draw_text_center(surface, text):
            text_surface = self.font.render(text, True, self.statusbar_text_color)
            text_x = (screen_width - text_surface.get_width()) // 2
            surface.blit(text_surface, (text_x, 2))
            del text_surface

        # Collect content for each position (top/bottom)
        position_content = {'top': {'left': None, 'center': None, 'right': None},
                         'bottom': {'left': None, 'center': None, 'right': None}}

        position_content[file_info_pos]['left'] = file_texts
        position_content[system_info_pos]['right'] = sys_texts
        position_content[progress_pos]['center'] = progress_text

        target = self.virtual_screen if self.rotation_mode == 'software' else self.screen

        # Draw each position
        for pos in ['top', 'bottom']:
            content = position_content[pos]
            if content['left'] is None and content['center'] is None and content['right'] is None:
                continue

            surface = create_statusbar_surface(screen_width, self.statusbar_height)
            y = 0 if pos == 'top' else screen_height - self.statusbar_height

            left_width = measure_texts_width(content['left']) if content['left'] else 0
            right_width = measure_texts_width(content['right']) if content['right'] else 0

            center_width = 0
            center_x = 0
            if content['center']:
                center_size = self.font.size(content['center'])
                center_width = center_size[0]
                center_x = (screen_width - center_width) // 2

            draw_center = True
            draw_right = True

            if content['center'] and center_x < left_width + 20:
                draw_center = False
            if content['center'] and center_x + center_width > screen_width - right_width - 20:
                draw_center = False
            if not draw_center and content['right'] and screen_width - right_width - 10 < left_width + 20:
                draw_right = False

            if content['left']:
                draw_texts_left(surface, content['left'])
            if draw_center and content['center']:
                draw_text_center(surface, content['center'])
            if draw_right and content['right']:
                draw_texts_right(surface, content['right'])

            clear_surface = pg.Surface((screen_width, self.statusbar_height))
            clear_surface.fill(self.bg_color)
            target.blit(clear_surface, (0, y))
            target.blit(surface, (0, y))

        # Apply software rotation if needed (must be done even if statusbar is hidden)
        if self.rotation_mode == 'software' and self.rotation in [90, 180, 270]:
            self._apply_rotation_to_screen()


    def _get_display_resolution(self) -> Tuple[int, int]:
        """Try to get display resolution from various sources"""
        # Try framebuffer sysfs first
        try:
            with open('/sys/class/graphics/fb0/virtual_size', 'r') as f:
                resolution = f.read().strip()
                width, height = map(int, resolution.split(','))
                logger.info(f"Framebuffer resolution: {width}x{height}")
                return width, height
        except (OSError, ValueError):
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
                                    except (ValueError, IndexError):
                                        continue
        except (OSError, ValueError):
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
                except (pg.error, OSError):
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

    # Maximum number of media files to prevent memory issues
    MAX_MEDIA_FILES = 2000

    def load_images(self, cache_dir: str) -> list[Path]:
        """
        Load all images from cache directory with limit to prevent memory issues

        Uses os.scandir() for better performance than Path.iterdir(),
        especially when there are many files.
        """
        cache_path = Path(cache_dir)
        if not cache_path.exists():
            logger.warning(f"Cache directory not found: {cache_dir}")
            return []

        supported = set(ext.lower() for ext in self.settings.get('supported_formats', []))
        images = []

        # Use os.scandir() for better performance (fewer stat calls)
        with os.scandir(str(cache_path)) as it:
            for entry in it:
                if entry.is_file():
                    suffix = Path(entry.name).suffix.lower()
                    if suffix in supported:
                        images.append(cache_path / entry.name)
                        # Prevent unbounded growth
                        if len(images) >= self.MAX_MEDIA_FILES:
                            logger.warning(f"Reached maximum media file limit ({self.MAX_MEDIA_FILES}), skipping remaining files")
                            break

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

    def _get_cache_key(self, image_path: Path, width: int, height: int) -> tuple:
        """Generate cache key for an image"""
        return (str(image_path), width, height, self.scale_mode)

    def _cache_image(self, image_path: Path, width: int, height: int, surface):
        """
        Cache an image surface with LRU eviction and memory limit

        Stores (surface, bytesize) tuple to track actual memory usage
        using surface.get_bytesize() for accurate calculation.
        """
        key = self._get_cache_key(image_path, width, height)

        with self._cache_lock:
            # Get actual bytes per pixel from the surface
            bytes_per_pixel = surface.get_bytesize()
            surface_memory_mb = (width * height * bytes_per_pixel) / (1024 * 1024)

            # Calculate current cache memory usage using stored bytesizes
            current_memory_mb = sum(
                (k[1] * k[2] * v[1]) / (1024 * 1024)
                for k, v in self._image_cache.items()
            )

            # Evict oldest entries until we have room (memory-based eviction)
            while (self._cache_access_order and
                   (len(self._image_cache) >= self._max_cache_size or
                    current_memory_mb + surface_memory_mb > self._max_cache_memory_mb)):
                oldest_key = self._cache_access_order.pop(0)
                if oldest_key in self._image_cache:
                    # Subtract evicted item's memory using its stored bytesize
                    _, old_w, old_h, _ = oldest_key
                    old_bytesize = self._image_cache[oldest_key][1]
                    current_memory_mb -= (old_w * old_h * old_bytesize) / (1024 * 1024)
                    del self._image_cache[oldest_key]

            # Store (surface, bytesize) tuple
            self._image_cache[key] = (surface, bytes_per_pixel)
            self._cache_access_order.append(key)
    
    def _get_cached_image(self, image_path: Path, width: int, height: int):
        """Get cached image surface if available"""
        key = self._get_cache_key(image_path, width, height)
        with self._cache_lock:
            if key in self._image_cache:
                # Update access order for LRU
                if key in self._cache_access_order:
                    self._cache_access_order.remove(key)
                self._cache_access_order.append(key)
                # Return just the surface from the (surface, bytesize) tuple
                return self._image_cache[key][0]
            return None

    def _get_surface_from_pool(self, width: int, height: int) -> Optional['pg.Surface']:
        """Get a surface from the pool or create new one"""
        with self._surface_pool_lock:
            for i, surf in enumerate(self._surface_pool):
                if surf.get_width() == width and surf.get_height() == height:
                    return self._surface_pool.pop(i)
        return None
    
    def _return_surface_to_pool(self, surf: 'pg.Surface'):
        """Return a surface to the pool for reuse"""
        if surf is None:
            return
        with self._surface_pool_lock:
            if len(self._surface_pool) < self._surface_pool_max:
                self._surface_pool.append(surf)
            else:
                # Pool is full, just let GC handle it
                pass

    def _clear_image_cache(self):
        """Clear the image cache (call when settings change)"""
        with self._cache_lock:
            self._image_cache.clear()
            self._cache_access_order.clear()

    def _periodic_cleanup(self):
        """Periodic garbage collection to prevent memory leaks"""
        current_time = time.time()
        self._frame_count += 1

        # Full GC every 5 minutes
        with self._gc_lock:
            if current_time - self._last_gc_time >= self._gc_interval:
                gc.collect()
                self._last_gc_time = current_time
                # Clean up surface pool periodically
                with self._surface_pool_lock:
                    self._surface_pool.clear()
                logger.debug("Ran periodic garbage collection and cleared surface pool")

        # Light cleanup every 100 frames (approx every 5 seconds at 20fps)
        elif self._frame_count % 100 == 0:
            # Young generation GC only (faster, less disruptive)
            gc.collect(generation=0)
    
    def _log_memory_usage(self):
        """Log current memory usage for monitoring"""
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            # Calculate cache memory
            cache_memory_mb = sum(
                (k[1] * k[2] * 3) / (1024 * 1024) for k in self._image_cache.keys()
            )
            logger.info(
                f"Memory: RSS={mem_info.rss/1024/1024:.1f}MB, "
                f"VMS={mem_info.vms/1024/1024:.1f}MB, "
                f"Cache={len(self._image_cache)} imgs ({cache_memory_mb:.1f}MB), "
                f"Pool={len(self._surface_pool)} surfaces"
            )
        except ImportError:
            # psutil not available, skip memory logging
            pass
        except Exception as e:
            logger.debug(f"Could not log memory usage: {e}")

    def display_image(self, image_path: Path) -> bool:
        """Load and display an image"""
        pg = get_pygame()
        try:
            # Get file info for status bar
            self.current_image_path = image_path
            self.current_image_info = self._get_file_info(image_path)

            # Use virtual screen dimensions for software rotation mode
            screen_width = self.virt_width
            screen_height = self.virt_height

            # Use virtual screen dimensions for software rotation mode
            screen_width = self.virt_width
            screen_height = self.virt_height

            # Check cache first
            cached_surface = self._get_cached_image(image_path, screen_width, screen_height)
            if cached_surface is not None:
                img_surface = cached_surface
                logger.debug(f"Using cached image: {image_path.name}")
            else:
                # Use PIL for better image loading
                if Image is not None:
                    with Image.open(image_path) as pil_image:
                        # Convert to RGB if necessary
                        if pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')

                        img_width, img_height = pil_image.size

                        # Calculate dimensions based on scale mode
                        if self.scale_mode == 'fit':
                            x, y, new_width, new_height = self.calculate_fit_size(
                                img_width, img_height, screen_width, screen_height
                            )
                            # Resize and place
                            resized = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            # Create background and paste
                            background = Image.new('RGB', (screen_width, screen_height), self.bg_color)
                            background.paste(resized, (x, y))
                            final_image = background
                        elif self.scale_mode == 'fill':
                            # Fill mode - crop to fill screen
                            crop_x, crop_y, crop_w, crop_h = self.calculate_fill_size(
                                img_width, img_height, screen_width, screen_height
                            )
                            cropped = pil_image.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
                            final_image = cropped.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
                        else:  # stretch
                            final_image = pil_image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)

                        # Convert to pygame surface
                        img_surface = pg.image.fromstring(
                            final_image.tobytes(),
                            final_image.size,
                            final_image.mode
                        )
                    # Cache the result
                    self._cache_image(image_path, screen_width, screen_height, img_surface)
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
                    # Cache the result
                    self._cache_image(image_path, screen_width, screen_height, img_surface)

            # Display
            # Determine target screen based on rotation mode
            if self.rotation_mode == 'software':
                target_screen = self.virtual_screen
            else:
                target_screen = self.screen

            target_screen.fill(self.bg_color)
            target_screen.blit(img_surface, (0, 0))

            # Draw status bar (handles rotation internally)
            # For images, countdown is not applicable (shown as 0s)
            self._draw_statusbar(0)

            # Flip the display
            pg.display.flip()

            logger.debug(f"Displayed: {image_path.name}")
            return True

        except Exception as e:
            if PILUnidentifiedImageError is not None and isinstance(e, PILUnidentifiedImageError):
                logger.error(f"Unsupported image format {image_path}: {e}")
            elif isinstance(e, (IOError, OSError)):
                logger.error(f"Cannot load image {image_path}: {e}")
            elif isinstance(e, (pg.error, ValueError)):
                logger.error(f"Error rendering image {image_path}: {e}")
            elif isinstance(e, MemoryError):
                logger.error(f"Out of memory loading {image_path}")
            else:
                logger.error(f"Unexpected error displaying {image_path}: {e}")
            return False

    def display_video(self, video_path: Path) -> bool:
        """Load and display a video file"""
        # If audio is enabled, use ffplay for audio+video playback
        if self.audio_enabled:
            if self.hw_accel_enabled:
                return self._display_video_with_audio_hw(video_path)
            return self._display_video_with_audio(video_path)
        # Try hardware accelerated playback first
        if self.hw_accel_enabled:
            return self._display_video_hw_accel(video_path)
        # Fallback to OpenCV for video-only playback
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
            self._cleanup_process(ffplay_process, timeout=2.0)

            return result

        except FileNotFoundError:
            logger.warning("ffplay not found. Install ffmpeg for audio support. Falling back to video-only.")
            return self._display_video_opencv(video_path)
        except Exception as e:
            logger.error(f"Error playing video with audio: {e}")
            return self._display_video_opencv(video_path)

    def _display_video_hw_accel(self, video_path: Path) -> bool:
        """Play video with hardware acceleration (ffmpeg v4l2m2m/drm)"""
        import subprocess
        pg = get_pygame()

        # Get video info for status bar
        self.current_image_path = video_path
        self.current_image_info = self._get_video_info(video_path)

        video_width = self.virt_width
        video_height = self.virt_height

        # Calculate display dimensions based on scale mode
        # Track actual output dimensions from ffmpeg
        output_width = video_width
        output_height = video_height

        if self.scale_mode == 'fit':
            # Get original video dimensions first
            temp_cap = cv2.VideoCapture(str(video_path))
            try:
                if temp_cap.isOpened():
                    orig_w = int(temp_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    orig_h = int(temp_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    x, y, new_width, new_height = self.calculate_fit_size(
                        orig_w, orig_h, video_width, video_height
                    )
                    scale_filter = f'scale={new_width}:{new_height}'
                    output_width = new_width
                    output_height = new_height
                    x_offset = (video_width - new_width) // 2
                    y_offset = (video_height - new_height) // 2
                else:
                    scale_filter = f'scale={video_width}:{video_height}'
                    x_offset = y_offset = 0
            finally:
                temp_cap.release()
        elif self.scale_mode == 'fill':
            scale_filter = f'scale={video_width}:{video_height}:force_original_aspect_ratio=decrease,crop={video_width}:{video_height}'
            x_offset = y_offset = 0
        else:  # stretch
            scale_filter = f'scale={video_width}:{video_height}'
            x_offset = y_offset = 0

        # Build ffmpeg command with hardware acceleration
        ffmpeg_cmd = [
            'ffmpeg',
            '-threads', '1',  # Single thread for hardware decoding
            '-loglevel', 'error',  # Reduce log output
        ]

        # Add hardware acceleration options
        if self.hw_accel_method == 'v4l2m2m':
            ffmpeg_cmd.extend(['-hwaccel', 'v4l2m2m', '-hwaccel_output_format', 'drm_prime'])
        elif self.hw_accel_method == 'drm':
            ffmpeg_cmd.extend(['-hwaccel', 'drm'])

        ffmpeg_cmd.extend([
            '-i', str(video_path),
            '-vf', scale_filter,
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            'pipe:1'
        ])

        try:
            # Start ffmpeg process
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL
            )

            # Calculate frame size (use actual output dimensions)
            frame_size = output_width * output_height * 3  # RGB24 = 3 bytes per pixel

            start_time = time.time()
            fps = 30  # Default FPS estimation
            last_statusbar_update = start_time

            # Thread for reading frames from ffmpeg
            frame_queue = queue.Queue(maxsize=5)  # Increased from 2 to prevent frame drops
            stop_event = threading.Event()

            def frame_reader():
                """Read frames from ffmpeg in separate thread"""
                try:
                    while not stop_event.is_set():
                        frame_data = process.stdout.read(frame_size)
                        if len(frame_data) < frame_size:
                            break
                        try:
                            frame_queue.put(frame_data, timeout=1.0)
                        except queue.Full:
                            pass  # Skip frame if queue is full
                except Exception as e:
                    logger.debug(f"Frame reader error: {e}")
                finally:
                    frame_queue.put(None)  # Signal end of stream

            # Start frame reader thread
            reader_thread = threading.Thread(target=frame_reader, daemon=True)
            reader_thread.start()

            target_screen = self.virtual_screen if self.rotation_mode == 'software' else self.screen

            while self.running:
                # Handle events
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        self.running = False
                        break
                    elif event.type == pg.KEYDOWN:
                        if event.key == pg.K_ESCAPE:
                            self.running = False
                            break
                        elif event.key == pg.K_SPACE:
                            return True  # Skip to next
                        elif event.key == pg.K_q:
                            self.running = False
                            break

                if not self.running:
                    break

                # Get frame from queue
                try:
                    frame_data = frame_queue.get(timeout=0.1)
                    if frame_data is None:
                        break  # End of stream
                except queue.Empty:
                    # Check for sync even when queue is empty
                    self._check_and_sync()
                    continue
                
                # Periodic sync check during video playback (throttled internally)
                self._check_and_sync()

                # Create pygame surface from frame data
                # Use actual ffmpeg output dimensions (may differ from video_width/height for 'fit' mode)
                frame_surface = pg.image.frombuffer(frame_data, (output_width, output_height), 'RGB')

                # Display frame
                target_screen.fill(self.bg_color)
                target_screen.blit(frame_surface, (x_offset, y_offset))

                # Update status bar periodically
                current_time = time.time()
                if current_time - last_statusbar_update >= 0.5:
                    elapsed = current_time - start_time
                    # Estimate duration from video info
                    duration_str = self.current_image_info.get('duration', '0:00')
                    mins, secs = map(int, duration_str.split(':'))
                    duration = mins * 60 + secs
                    remaining = max(0, duration - elapsed)

                    self._draw_statusbar_video(
                        elapsed, remaining, duration,
                        0, 0  # Frame info not available with ffmpeg
                    )
                    last_statusbar_update = current_time

                # Periodic sync check during video playback (every frame, throttled internally)
                self._check_and_sync()

                # Apply software rotation if needed
                if self.rotation_mode == 'software' and self.rotation in [90, 180, 270]:
                    self._apply_rotation_to_screen()

                pg.display.flip()

                # Maintain frame rate
                time.sleep(1.0 / fps)

            # Cleanup
            stop_event.set()
            reader_thread.join(timeout=1.0)

            self._cleanup_process(process, timeout=2.0)

            logger.info(f"Video playback finished: {video_path.name}")
            return True

        except FileNotFoundError:
            logger.warning("ffmpeg not found. Falling back to OpenCV.")
            return self._display_video_opencv(video_path)
        except Exception as e:
            logger.error(f"Error in HW accelerated playback: {e}, falling back to OpenCV")
            return self._display_video_opencv(video_path)

    def _display_video_with_audio_hw(self, video_path: Path) -> bool:
        """Play video with audio using hardware-accelerated video + ffplay audio"""
        import subprocess
        import os

        try:
            # Get video info for status bar
            self.current_image_path = video_path
            self.current_image_info = self._get_video_info(video_path)

            logger.info(f"Playing video with audio + HW acceleration: {video_path.name}")

            # Audio output device mapping
            audio_device_map = {'hdmi': '0', 'local': '1'}
            alsa_device = audio_device_map.get(self.audio_device, '0')

            # Build ffplay command for audio only
            ffplay_cmd = [
                'ffplay',
                '-vn',  # Don't play video (we'll handle display)
                '-nodisp',  # Don't display ffplay window
                '-autoexit',
                '-volume', str(self.audio_volume),
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

            # Play video with hardware acceleration
            result = self._display_video_hw_accel(video_path)

            # Clean up ffplay process
            self._cleanup_process(ffplay_process, timeout=2.0)

            return result

        except FileNotFoundError:
            logger.warning("ffplay not found. Install ffmpeg for audio support.")
            return self._display_video_hw_accel(video_path)
        except Exception as e:
            logger.error(f"Error playing video with audio: {e}")
            return self._display_video_hw_accel(video_path)

    @contextmanager
    def _video_capture(self, video_path: Path):
        """Context manager for cv2.VideoCapture to ensure proper cleanup"""
        cap = None
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                yield None
            else:
                yield cap
        finally:
            if cap is not None:
                cap.release()

    def _display_video_opencv(self, video_path: Path, skip_audio_check: bool = False) -> bool:
        """Load and display a video file using OpenCV (video only)"""
        pg = get_pygame()
        if cv2 is None:
            logger.error("OpenCV (cv2) is not installed. Install with: pip install opencv-python")
            return False

        # Get video info for status bar
        if not skip_audio_check:
            self.current_image_path = video_path
            self.current_image_info = self._get_video_info(video_path)

        # Video uses full virtual screen (status bar is overlay)
        video_display_y = 0
        video_display_height = self.virt_height

        try:
            with self._video_capture(video_path) as cap:
                if cap is None:
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
                            self.running = False
                            return False
                        elif event.type == pg.KEYDOWN:
                            if event.key == pg.K_ESCAPE:
                                self.running = False
                                return False
                            elif event.key == pg.K_SPACE:
                                return True  # Skip to next
                            elif event.key == pg.K_q:
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

                    # Create pygame surface from frame data
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

                    # Return surface to pool for reuse (prevents memory leak)
                    self._return_surface_to_pool(frame_surface)
                    
                    # Periodic sync check during video playback (throttled internally)
                    self._check_and_sync()

                    # Maintain frame rate timing (ensure minimum delay)
                    elapsed = (time.time() - frame_start_time) * 1000
                    wait_time = frame_delay - int(elapsed)
                    if wait_time > 0:
                        time.sleep(wait_time / 1000.0)
                    else:
                        # If we're behind, yield to prevent CPU spinning
                        time.sleep(0.001)
                    frame_start_time = time.time()

                logger.info(f"Video playback finished: {video_path.name}")
                return True

        except Exception as e:
            logger.error(f"Error displaying video {video_path}: {e}")
            return False

    @staticmethod
    def _cleanup_process(process, timeout: float = 2.0):
        """Safely cleanup a subprocess, preventing zombie processes"""
        if process is None:
            return
        try:
            # Check if process is still running
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
        except (ProcessLookupError, OSError):
            pass  # Process already gone
        finally:
            # Ensure pipes are closed to prevent file descriptor leaks
            for pipe in [process.stdout, process.stderr, process.stdin]:
                if pipe is not None:
                    try:
                        pipe.close()
                    except (OSError, ValueError):
                        pass

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

        # Get common layout configuration
        config = self._get_statusbar_layout_config()
        screen_width = config['screen_width']
        screen_height = config['screen_height']
        layout = config['layout']
        file_info_pos = config['file_info_pos']
        system_info_pos = config['system_info_pos']
        progress_pos = config['progress_pos']
        physical_res = config['physical_res']

        # Helper to format time as MM:SS
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

        # Call common rendering method
        self._render_statusbar_common(
            screen_width, screen_height, layout,
            file_info_pos, system_info_pos, progress_pos,
            file_texts, sys_texts, progress_text, text_spacing=15
        )

    def _should_restart(self) -> bool:
        """Check if weekly auto-restart should be triggered.
        Uses schedule.start as the restart time (e.g., if display starts at 07:00, restart at 07:00).
        """
        if not self.weekly_auto_restart:
            return False

        now = datetime.datetime.now()

        # Check if today is the restart day
        if now.weekday() != self.weekly_restart_day:
            return False

        # Use schedule.start as restart time
        restart_time_str = self.schedule_start
        try:
            restart_hour, restart_min = map(int, restart_time_str.split(':'))
        except (ValueError, AttributeError):
            restart_hour, restart_min = 7, 0  # Default: 7:00 AM (same as schedule default)

        # Create today's restart datetime
        restart_datetime = now.replace(hour=restart_hour, minute=restart_min,
                                        second=0, microsecond=0)

        # Check if we've passed the restart time
        if now < restart_datetime:
            return False  # Haven't reached restart time yet

        # Only restart within 1 hour window after restart time
        # This prevents immediate restart if program starts after the scheduled time
        if now - restart_datetime > datetime.timedelta(hours=1):
            return False  # Missed the restart window, wait until next week

        # Check if we already restarted today (prevent multiple restarts)
        restart_marker = Path("/tmp/gscreen_restarted_today")
        if restart_marker.exists():
            try:
                if restart_marker.read_text().strip() == now.date().isoformat():
                    return False  # Already restarted today
            except (OSError, IOError):
                pass  # Marker file corrupted, proceed with restart

        return True

    def _do_restart(self):
        """Perform system restart"""
        import subprocess

        # Create marker file with today's date to prevent multiple restarts
        restart_marker = Path("/tmp/gscreen_restarted_today")
        restart_marker.write_text(datetime.datetime.now().date().isoformat())

        logger.info(f"Executing weekly auto-restart at {datetime.datetime.now()}")
        try:
            # Use systemctl for clean reboot
            subprocess.run(['sudo', 'systemctl', 'reboot'], check=False, timeout=10)
        except Exception as e:
            logger.error(f"Failed to restart: {e}")

    def _signal_handler(self, signum, frame):
        """Handle signals for clean shutdown"""
        logger.info("Received signal, shutting down...")
        self.running = False

    def _check_and_sync(self, force: bool = False) -> bool:
        """
        Check if it's time to sync and perform sync if needed.
        Returns True if sync was performed.
        Thread-safe: uses _state_lock to protect _last_sync_time.
        """
        current_time = time.time()
        with self._state_lock:
            elapsed = current_time - self._last_sync_time
        # Log every 30 seconds to show we're alive
        if int(elapsed) % 30 == 0:
            logger.info(f"Sync check: elapsed={elapsed:.1f}s, interval={self.sync_interval}s")
        if not force and elapsed < self.sync_interval:
            return False

        logger.info("Checking for new images...")

        # Lazy init sync instance
        if self._sync_instance is None:
            from gdrive_sync import GoogleDriveSync
            self._sync_instance = GoogleDriveSync(self.settings_path)

        try:
            self._sync_instance.sync()
        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            self._show_error_message(f"同步失败: {str(e)}")

        if hasattr(self, 'cache_dir'):
            self.images = self.load_images(self.cache_dir)
            with self._state_lock:
                self.last_sync_time = datetime.datetime.now()
                self._last_sync_time = time.time()
            # Reset index if out of bounds
            if self.current_image_index >= len(self.images):
                self.current_image_index = 0
        
        self._last_sync_time = current_time
        return True

    def run(self, cache_dir: str):
        """Main slideshow loop"""
        pg = get_pygame()
        self.cache_dir = cache_dir  # Save for sync usage
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
            sync = GoogleDriveSync(self.settings_path)
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
        self._last_sync_time = time.time()
        last_statusbar_update = time.time()

        # Count videos vs images
        video_count = sum(1 for img in self.images if self._is_video(img))
        image_count = len(self.images) - video_count
        logger.info(f"Starting slideshow with {len(self.images)} media files ({image_count} images, {video_count} videos)")

        # Import sync module for periodic updates
        from gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync(self.settings_path)

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

                # Check schedule - show countdown then sleep if outside active time
                is_active = self._is_active_time()
                if not is_active:
                    # Just became inactive - show countdown first
                    if self.was_active_time:
                        self._show_sleep_countdown()
                        self.was_active_time = False
                    # After countdown, go to sleep
                    if not self.screen_asleep:
                        self._set_screen_power(False)
                    time.sleep(5)  # Sleep longer when inactive
                    continue
                else:
                    if not self.was_active_time:
                        self.was_active_time = True
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

                # Periodic sync check
                self._check_and_sync()

                # Display error message if any (with auto-clear)
                with self._state_lock:
                    if self.error_message:
                        if time.time() - self.error_message_time < 30:
                            self._show_error_message(self.error_message)
                        else:
                            # Auto-clear expired error message
                            self._clear_error_message()

                # Periodic cleanup to prevent memory leaks
                self._periodic_cleanup()
                
                # Periodic memory logging (every 10 minutes)
                if self._frame_count % 12000 == 0:  # ~10 minutes at 20fps
                    self._log_memory_usage()

                # Check for weekly auto-restart
                if self.weekly_auto_restart and self._should_restart():
                    logger.info("Weekly auto-restart triggered. Restarting system...")
                    self._do_restart()
                    return  # Exit cleanly

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
        except (pg.error, FileNotFoundError):
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
        sync = GoogleDriveSync(self.settings_path)
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
                    self.virtual_screen.fill(self.bg_color)
                else:
                    self.screen.fill(self.bg_color)

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
                if self.virtual_screen and self.screen:
                    pg.transform.scale(self.virtual_screen, (self.screen_width, self.screen_height), self.screen)
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
            # Try Noto Sans CJK for Chinese/Japanese/Korean support
            large_font = pg.font.SysFont('Noto Sans CJK SC', 48, bold=True)
            medium_font = pg.font.SysFont('Noto Sans CJK SC', 28, bold=True)
        except (pg.error, FileNotFoundError):
            try:
                # Fallback to DejaVuSans
                large_font = pg.font.SysFont('DejaVuSans', 48, bold=True)
                medium_font = pg.font.SysFont('DejaVuSans', 28, bold=True)
            except (pg.error, FileNotFoundError):
                # Fallback to default font
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
                    self.virtual_screen.fill(self.bg_color)
                else:
                    self.screen.fill(self.bg_color)

                # Draw messages
                # Main message - show schedule time
                main_msg = f"Schedule: {self.schedule_start} - {self.schedule_stop}"
                main_surface = medium_font.render(main_msg, True, (255, 100, 100))
                main_x = (screen_width - main_surface.get_width()) // 2
                main_y = screen_height // 2 - 60

                # Sub message
                sub_msg = "Outside scheduled hours - Sleeping..."
                sub_surface = medium_font.render(sub_msg, True, (200, 200, 200))
                sub_x = (screen_width - sub_surface.get_width()) // 2
                sub_y = screen_height // 2

                # Countdown
                countdown_msg = f"Sleep in {remaining}s"
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

                # Update display with rotation if needed
                if self.rotation_mode == 'software' and self.rotation in [90, 180, 270]:
                    self._apply_rotation_to_screen()
                elif self.virtual_screen is not self.screen:
                    # No software rotation, but virtual screen exists
                    pg.transform.scale(self.virtual_screen, (self.screen_width, self.screen_height), self.screen)
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

        # Store error message to display periodically (thread-safe)
        with self._state_lock:
            self.error_message = message
            self.error_message_time = time.time()

        # Create fonts for error display
        try:
            error_font = pg.font.SysFont('Noto Sans CJK SC', 32, bold=True)
        except (pg.error, FileNotFoundError):
            try:
                error_font = pg.font.SysFont('DejaVuSans', 32, bold=True)
            except (pg.error, FileNotFoundError):
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

        # Update display with rotation if needed
        if self.rotation_mode == 'software' and self.rotation in [90, 180, 270]:
            self._apply_rotation_to_screen()
        elif self.virtual_screen is not self.screen:
            # No software rotation, but virtual screen exists
            pg.transform.scale(self.virtual_screen, (self.screen_width, self.screen_height), self.screen)
        pg.display.flip()

    def _clear_error_message(self):
        """Clear stored error message (thread-safe)"""
        with self._state_lock:
            self.error_message = None


def main():
    """Main entry point"""
    import sys

    # Get cache directory from settings or use default
    try:
        with open("settings.json", 'r') as f:
            settings = json.load(f)
        cache_dir = settings['sync']['local_cache_dir']
    except (OSError, json.JSONDecodeError, KeyError):
        cache_dir = "./media"

    slideshow = SlideshowDisplay()
    slideshow.run(cache_dir)


if __name__ == "__main__":
    main()
