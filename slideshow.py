#!/usr/bin/env python3
"""
Slideshow Display Module
Displays images on specified HDMI output with fullscreen borderless window
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Optional, Tuple
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
    """Fullscreen slideshow display for HDMI output"""

    def __init__(self, settings_path: str = "settings.json"):
        self.settings = self._load_settings(settings_path)
        self.display_settings = self.settings['display']
        self.slideshow_settings = self.settings['slideshow']

        self.interval = self.slideshow_settings['interval_seconds']
        self.scale_mode = self.slideshow_settings['scale_mode']
        self.bg_color = tuple(self.display_settings['background_color'])

        self.running = False
        self.current_image_index = 0
        self.images: list[Path] = []
        self.screen = None
        self.screen_info = None

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

    def _get_display_env(self, hdmi_port: int) -> dict:
        """Get environment variables for specific HDMI output"""
        # HDMI ports on Raspberry Pi
        # HDMI0 is usually :0, HDMI1 is usually :1
        display_num = hdmi_port if hdmi_port in [0, 1] else 0
        return {
            'DISPLAY': f':{display_num}',
            'SDL_VIDEO_FULLSCREEN_HEAD': str(display_num)
        }

    def init_display(self):
        """Initialize pygame display on specified HDMI port"""
        if pygame is None:
            raise ImportError("pygame is not installed. Install with: pip install pygame")

        hdmi_port = self.display_settings.get('hdmi_port', 1)
        display_env = self._get_display_env(hdmi_port)

        # Update environment for this process
        for key, value in display_env.items():
            os.environ[key] = value

        logger.info(f"Initializing display on HDMI{hdmi_port} ({display_env['DISPLAY']})")

        # Initialize pygame
        pygame.init()

        # Get display info
        pygame.display.init()
        self.screen_info = pygame.display.Info()
        screen_width = self.screen_info.current_w
        screen_height = self.screen_info.current_h

        logger.info(f"Display resolution: {screen_width}x{screen_height}")

        # Set display mode
        flags = pygame.FULLSCREEN | pygame.NOFRAME
        self.screen = pygame.display.set_mode((screen_width, screen_height), flags)

        # Hide cursor
        pygame.mouse.set_visible(False)

        logger.info("Display initialized successfully")

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
        img_ratio = img_width / img_height
        screen_ratio = screen_width / screen_height

        if img_ratio > screen_ratio:
            # Image is wider - fit to width
            new_width = screen_width
            new_height = int(screen_width / img_ratio)
        else:
            # Image is taller - fit to height
            new_height = screen_height
            new_width = int(screen_height * img_ratio)

        # Center on screen
        x = (screen_width - new_width) // 2
        y = (screen_height - new_height) // 2

        return x, y, new_width, new_height

    def calculate_fill_size(self, img_width: int, img_height: int,
                          screen_width: int, screen_height: int) -> Tuple[int, int, int, int]:
        """
        Calculate scaled dimensions to fill screen (crop if needed)
        Returns: (source_x, source_y, source_w, source_h)
        For fill mode, we return crop coordinates
        """
        img_ratio = img_width / img_height
        screen_ratio = screen_width / screen_height

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

                img_surface = pygame.transform.scale(
                    img_surface,
                    (screen_width, screen_height)
                )

            # Display
            self.screen.fill(self.bg_color)
            self.screen.blit(img_surface, (0, 0))
            pygame.display.flip()

            logger.debug(f"Displayed: {image_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error displaying {image_path}: {e}")
            return False

    def run(self, cache_dir: str):
        """Main slideshow loop"""
        self.init_display()

        # Load images
        self.images = self.load_images(cache_dir)

        if not self.images:
            logger.warning("No images to display")
            return

        self.running = True
        last_change = time.time()
        last_sync = time.time()

        logger.info(f"Starting slideshow with {len(self.images)} images")

        # Import sync module for periodic updates
        from gdrive_sync import GoogleDriveSync
        sync = GoogleDriveSync()

        while self.running:
            try:
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

                current_time = time.time()

                # Check if it's time to change image
                if current_time - last_change >= self.interval:
                    if self.images:
                        # Display next image
                        image_path = self.images[self.current_image_index]
                        self.display_image(image_path)

                        # Move to next image
                        self.current_image_index = (self.current_image_index + 1) % len(self.images)
                        last_change = current_time

                # Periodic sync check (every minute)
                sync_interval = self.settings['sync']['check_interval_minutes'] * 60
                if current_time - last_sync >= sync_interval:
                    logger.info("Checking for new images...")
                    sync.sync()
                    self.images = self.load_images(cache_dir)
                    # Reset index if out of bounds
                    if self.current_image_index >= len(self.images):
                        self.current_image_index = 0
                    last_sync = current_time

                # Small sleep to prevent high CPU usage
                time.sleep(0.1)

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
