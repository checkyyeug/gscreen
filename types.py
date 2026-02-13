#!/usr/bin/env python3
"""
Type definitions for gScreen
Provides TypedDict and type hints for better type safety
"""

from typing import TypedDict, List, Tuple, Optional, Union, Literal, Dict, Any


# ============= File Info Types =============
class FileInfo(TypedDict):
    """File information for display"""
    name: str
    size: str
    modified: str
    dimensions: str
    format: str


# ============= Display Types =============
class DisplayConfig(TypedDict):
    """Display settings from configuration"""
    hdmi_port: int
    fullscreen: bool
    borderless: bool
    background_color: Tuple[int, int, int]
    hide_mouse: bool
    show_statusbar: bool
    rotation_mode: Literal['hardware', 'software']
    rotation: int
    statusbar_layout: Dict[str, Any]


class StatusBarLayout(TypedDict):
    """Status bar layout configuration"""
    opacity: float
    landscape: Dict[str, str]
    portrait: Dict[str, str]


class StatusbarConfig(TypedDict):
    """Status bar specific settings"""
    height: int
    bg_color_base: Tuple[int, int, int]
    opacity: float
    text_color: Tuple[int, int, int]
    font_size: int


# ============= Slideshow Types =============
class SlideshowConfig(TypedDict):
    """Slideshow settings from configuration"""
    interval_seconds: int
    scale_mode: Literal['fit', 'fill', 'stretch']


# ============= Audio Types =============
class AudioConfig(TypedDict):
    """Audio settings from configuration"""
    enabled: bool
    device: Literal['hdmi', 'local']
    volume: int


# ============= Schedule Types =============
class ScheduleConfig(TypedDict):
    """Schedule settings from configuration"""
    enabled: bool
    days: List[str]
    start: str  # Format: "HH:MM"
    stop: str   # Format: "HH:MM"


# ============= Sync Types =============
class SyncConfig(TypedDict):
    """Sync settings from configuration"""
    local_cache_dir: str
    download_on_start: bool
    check_interval_minutes: int
    timezone_offset: int
    sync_system_time: bool


# ============= Settings Types =============
class Settings(TypedDict):
    """Complete settings structure"""
    google_drive_url: str
    display: DisplayConfig
    slideshow: SlideshowConfig
    audio: AudioConfig
    schedule: ScheduleConfig
    sync: SyncConfig
    supported_formats: List[str]


# ============= Function Return Types =============
class DisplayDimensions(TypedDict):
    """Screen dimension information"""
    virtual_width: int
    virtual_height: int
    screen_width: int
    screen_height: int


class VideoInfo(TypedDict):
    """Video file information"""
    name: str
    dimensions: str
    fps: float
    duration: float


class WifiInfo(TypedDict):
    """WiFi signal information"""
    signal: str  # e.g., "-45 dBm" or "Excellent"
