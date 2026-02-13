#!/usr/bin/env python3
"""
Custom exception types for gScreen
Provides specific exception types for better error handling and debugging
"""

from typing import Optional


# ============= Configuration Errors =============
class ConfigurationError(Exception):
    """Base class for configuration-related errors"""
    pass


class ConfigValidationError(ConfigurationError):
    """Raised when configuration validation fails"""

    def __init__(self, field: str, message: str, value: Optional[str] = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Config error in '{field}': {message}{f' (value: {value})' if value else ''}")


class InvalidURL(ConfigurationError):
    """Raised when Google Drive URL is invalid"""
    pass


class InvalidColor(ConfigValidationError):
    """Raised when background_color is invalid"""
    pass


class InvalidTimeFormat(ConfigValidationError):
    """Raised when time format is invalid"""
    pass


class InvalidScaleMode(ConfigValidationError):
    """Raised when scale_mode is invalid"""
    pass


class InvalidRotation(ConfigValidationError):
    """Raised when rotation value is invalid"""
    pass


# ============= File Errors =============
class FileError(Exception):
    """Base class for file-related errors"""
    pass


class UnsupportedFormat(FileError):
    """Raised when file format is not supported"""
    pass


class CorruptedFile(FileError):
    """Raised when file is corrupted and cannot be opened"""
    pass


# ============= Network Errors =============
class NetworkError(Exception):
    """Base class for network-related errors"""
    pass


class DownloadFailed(NetworkError):
    """Raised when file download fails"""
    pass


class ConnectionTimeout(NetworkError):
    """Raised when network connection times out"""
    pass


class APIError(NetworkError):
    """Raised when API call fails"""
    pass


# ============= Display Errors =============
class DisplayError(Exception):
    """Base class for display-related errors"""
    pass


class InitializationFailed(DisplayError):
    """Raised when display initialization fails"""
    pass


class DriverError(DisplayError):
    """Raised when no display driver is available"""
    pass


# ============= Media Errors =============
class MediaError(Exception):
    """Base class for media-related errors"""
    pass


class UnsupportedImageFormat(MediaError):
    """Raised when image format cannot be loaded"""
    pass


class VideoPlaybackError(MediaError):
    """Raised when video playback fails"""
    pass


class VideoOpenError(MediaError):
    """Raised when video file cannot be opened"""
    pass


# ============= Sync Errors =============
class SyncError(Exception):
    """Base class for sync-related errors"""
    pass


class TimeSyncError(SyncError):
    """Raised when time synchronization fails"""
    pass


class AuthenticationError(SyncError):
    """Raised when authentication fails"""
    pass