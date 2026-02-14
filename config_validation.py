#!/usr/bin/env python3
"""
Configuration Validation Module
Validates settings.json to catch configuration errors early
"""

import logging
from typing import Dict, Any, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when configuration validation fails"""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Config error in '{field}': {message}")


def validate_color(value: Any, field_name: str) -> Tuple[int, int, int]:
    """Validate background_color is a tuple of 3 integers 0-255"""
    if not isinstance(value, list):
        raise ValidationError(field_name, "Must be a list of 3 integers")
    if len(value) != 3:
        raise ValidationError(field_name, "Must have exactly 3 values (R, G, B)")
    for i, v in enumerate(value):
        if not isinstance(v, int):
            raise ValidationError(field_name, f"Value {i} must be an integer")
        if not (0 <= v <= 255):
            raise ValidationError(field_name, f"Value {i} must be 0-255, got {v}")
    return tuple(value)


def validate_schedule_time(value: Any, field_name: str) -> str:
    """Validate time format is HH:MM"""
    if not isinstance(value, str):
        raise ValidationError(field_name, "Must be a string in HH:MM format")
    parts = value.split(':')
    if len(parts) != 2:
        raise ValidationError(field_name, "Must be in HH:MM format (e.g., '09:30')")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23):
            raise ValidationError(field_name, f"Hour must be 0-23, got {hour}")
        if not (0 <= minute <= 59):
            raise ValidationError(field_name, f"Minute must be 0-59, got {minute}")
    except ValueError:
        raise ValidationError(field_name, "Hour and minute must be valid integers")
    return value


def validate_schedule_days(value: Any, field_name: str) -> List[str]:
    """Validate schedule days is a list of valid day abbreviations"""
    valid_days = {'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'}
    if not isinstance(value, list):
        raise ValidationError(field_name, "Must be a list of day abbreviations")
    if not value:
        raise ValidationError(field_name, "Cannot be empty")
    for day in value:
        if day not in valid_days:
            raise ValidationError(field_name, f"Invalid day: '{day}'. Must be one of: {', '.join(valid_days)}")
    return value


def validate_rotation(value: Any, field_name: str) -> int:
    """Validate rotation is 0, 90, 180, or 270"""
    if not isinstance(value, int):
        raise ValidationError(field_name, "Must be an integer")
    valid_rotations = {0, 90, 180, 270}
    if value not in valid_rotations:
        raise ValidationError(field_name, f"Must be one of: {', '.join(map(str, valid_rotations))}")
    return value


def validate_scale_mode(value: Any, field_name: str) -> str:
    """Validate scale_mode is 'fit', 'fill', or 'stretch'"""
    valid_modes = {'fit', 'fill', 'stretch'}
    if value not in valid_modes:
        raise ValidationError(field_name, f"Must be one of: {', '.join(valid_modes)}")
    return value


def validate_interval(value: Any, field_name: str) -> int:
    """Validate interval_seconds is positive and reasonable"""
    if not isinstance(value, (int, float)):
        raise ValidationError(field_name, "Must be a number")
    if value < 1:
        raise ValidationError(field_name, "Must be at least 1 second")
    if value > 3600:
        raise ValidationError(field_name, "Must be at most 3600 seconds (1 hour)")
    return int(value)


def validate_url(value: Any, field_name: str) -> str:
    """Validate google_drive_url is a valid Google Drive URL"""
    if not isinstance(value, str):
        raise ValidationError(field_name, "Must be a string")
    if not value.startswith('https://'):
        raise ValidationError(field_name, "Must start with 'https://'")
    if 'drive.google.com' not in value:
        raise ValidationError(field_name, "Must be a Google Drive URL")
    return value


def validate_settings(settings: Dict[str, Any]) -> None:
    """
    Validate all settings and raise ValidationError if any issues found.
    Call this after loading settings.json but before using the values.
    """
    errors = []

    # Validate top-level required fields
    required_fields = ['google_drive_url', 'display', 'slideshow']
    for field in required_fields:
        if field not in settings:
            errors.append(f"Missing required field: '{field}'")

    # Validate display settings
    if 'display' in settings:
        display = settings['display']

        # Validate background_color
        if 'background_color' in display:
            try:
                display['background_color'] = validate_color(
                    display['background_color'], 'display.background_color'
                )
            except ValidationError as e:
                errors.append(str(e))

        # Validate rotation
        if 'rotation' in display:
            try:
                display['rotation'] = validate_rotation(
                    display.get('rotation', 0), 'display.rotation'
                )
            except ValidationError as e:
                errors.append(str(e))

        # Validate rotation_mode
        if 'rotation_mode' in display:
            valid_modes = {'hardware', 'software'}
            if display['rotation_mode'] not in valid_modes:
                errors.append(f"display.rotation_mode must be one of: {', '.join(valid_modes)}")

        # Validate scale_mode (in slideshow)
        if 'scale_mode' in display:
            try:
                display['scale_mode'] = validate_scale_mode(
                    display['scale_mode'], 'display.scale_mode'
                )
            except ValidationError as e:
                errors.append(str(e))

    # Validate slideshow settings
    if 'slideshow' in settings:
        slideshow = settings['slideshow']

        # Validate interval_seconds
        if 'interval_seconds' in slideshow:
            try:
                slideshow['interval_seconds'] = validate_interval(
                    slideshow['interval_seconds'], 'slideshow.interval_seconds'
                )
            except ValidationError as e:
                errors.append(str(e))

    # Validate schedule settings
    if 'schedule' in settings:
        schedule = settings['schedule']

        # Validate start time
        if 'start' in schedule:
            try:
                schedule['start'] = validate_schedule_time(
                    schedule['start'], 'schedule.start'
                )
            except ValidationError as e:
                errors.append(str(e))

        # Validate stop time
        if 'stop' in schedule:
            try:
                schedule['stop'] = validate_schedule_time(
                    schedule['stop'], 'schedule.stop'
                )
            except ValidationError as e:
                errors.append(str(e))

        # Validate days
        if 'days' in schedule:
            try:
                schedule['days'] = validate_schedule_days(
                    schedule['days'], 'schedule.days'
                )
            except ValidationError as e:
                errors.append(str(e))

    # Validate audio settings
    if 'audio' in settings:
        audio = settings['audio']

        # Validate volume
        if 'volume' in audio:
            if not isinstance(audio['volume'], int):
                errors.append("audio.volume must be an integer")
            elif not (0 <= audio['volume'] <= 100):
                errors.append("audio.volume must be 0-100")

        # Validate device
        if 'device' in audio:
            valid_devices = {'hdmi', 'local'}
            if audio['device'] not in valid_devices:
                errors.append(f"audio.device must be one of: {', '.join(valid_devices)}")

    # Validate sync settings
    if 'sync' in settings:
        sync = settings['sync']

        # Validate timezone_offset
        if 'timezone_offset' in sync:
            if not isinstance(sync['timezone_offset'], int):
                errors.append("sync.timezone_offset must be an integer")
            elif not (-12 <= sync['timezone_offset'] <= 14):
                errors.append("sync.timezone_offset must be -12 to +14")

        # Validate check_interval_minutes (stored in minutes, validated as 1-60 minutes)
        if 'check_interval_minutes' in sync:
            try:
                minutes = sync['check_interval_minutes']
                if not isinstance(minutes, (int, float)):
                    raise ValidationError('sync.check_interval_minutes', "Must be a number")
                if minutes < 1:
                    raise ValidationError('sync.check_interval_minutes', "Must be at least 1 minute")
                if minutes > 60:
                    raise ValidationError('sync.check_interval_minutes', "Must be at most 60 minutes")
                sync['check_interval_minutes'] = int(minutes)
            except ValidationError as e:
                errors.append(str(e))

    # Validate system settings
    if 'system' in settings:
        system = settings['system']

        # Validate paths section
        if 'paths' in system:
            paths = system['paths']
            default_paths = {
                'framebuffer_device': '/dev/fb0',
                'ram_log_dir': '/dev/shm/gscreen_logs',
                'x11_socket_dir': '/tmp/.X11-unix',
                'sysfs_graphics_path': '/sys/class/graphics',
                'sysfs_drm_path': '/sys/class/drm',
                'proc_net_wireless': '/proc/net/wireless',
                'dev_video_glob': '/dev/video*'
            }
            # Ensure all paths are strings
            for key, default_value in default_paths.items():
                if key in paths:
                    if not isinstance(paths[key], str):
                        errors.append(f"system.paths.{key} must be a string")
                    elif not paths[key]:
                        errors.append(f"system.paths.{key} cannot be empty")
                # Set defaults if not present
                elif key not in paths:
                    paths[key] = default_value
            # Set defaults for any missing paths
            for key, default_value in default_paths.items():
                if key not in paths:
                    paths[key] = default_value
        else:
            # Add default paths if not present
            system['paths'] = {
                'framebuffer_device': '/dev/fb0',
                'ram_log_dir': '/dev/shm/gscreen_logs',
                'x11_socket_dir': '/tmp/.X11-unix',
                'sysfs_graphics_path': '/sys/class/graphics',
                'sysfs_drm_path': '/sys/class/drm',
                'proc_net_wireless': '/proc/net/wireless',
                'dev_video_glob': '/dev/video*'
            }

    # Validate timeouts section
    if 'system' in settings and 'timeouts' in settings['system']:
        try:
            settings['system']['timeouts'] = validate_timeouts(
                settings['system']['timeouts'], 'system.timeouts'
            )
        except ValidationError as e:
            errors.append(str(e))

    # Validate google_drive_url
    if 'google_drive_url' in settings:
        try:
            settings['google_drive_url'] = validate_url(
                settings['google_drive_url'], 'google_drive_url'
            )
        except ValidationError as e:
            errors.append(str(e))

    # If there are errors, raise with all error messages
    if errors:
        error_msg = "Configuration validation failed:\n  - " + "\n  - ".join(errors)
        logger.error(error_msg)
        raise ValidationError("settings", error_msg)


def get_system_paths(settings: Dict[str, Any]) -> Dict[str, str]:
    """
    Get system paths from settings with defaults.

    Returns a dict of all system paths used by the application.
    """
    default_paths = {
        'framebuffer_device': '/dev/fb0',
        'ram_log_dir': '/dev/shm/gscreen_logs',
        'x11_socket_dir': '/tmp/.X11-unix',
        'sysfs_graphics_path': '/sys/class/graphics',
        'sysfs_drm_path': '/sys/class/drm',
        'proc_net_wireless': '/proc/net/wireless',
        'dev_video_glob': '/dev/video*'
    }

    # Get paths from settings or use defaults
    if 'system' in settings and 'paths' in settings['system']:
        paths = settings['system']['paths']
        # Apply defaults for missing keys
        for key, default_value in default_paths.items():
            if key not in paths:
                paths[key] = default_value
        return paths

    return default_paths.copy()


def validate_timeouts(value: Any, field_name: str) -> Dict[str, Any]:
    """Validate timeouts configuration section"""
    if not isinstance(value, dict):
        raise ValidationError(field_name, "Must be a dictionary")

    errors = []
    validated = {}

    # Validate network timeouts
    if 'network' in value:
        network = value['network']
        for key in ['download', 'list', 'head', 'default']:
            if key in network:
                timeout_val = network[key]
                if not isinstance(timeout_val, (int, float)):
                    errors.append(f"system.timeouts.network.{key} must be a number")
                elif timeout_val < 1:
                    errors.append(f"system.timeouts.network.{key} must be at least 1 second")
                elif timeout_val > 3600:
                    errors.append(f"system.timeouts.network.{key} must be at most 3600 seconds (1 hour)")
                else:
                    validated.setdefault('network', {})
                    validated['network'][key] = int(timeout_val)

    # Validate subprocess timeouts
    if 'subprocess' in value:
        subprocess = value['subprocess']
        for key in ['quick', 'normal', 'long', 'reboot']:
            if key in subprocess:
                timeout_val = subprocess[key]
                if not isinstance(timeout_val, (int, float)):
                    errors.append(f"system.timeouts.subprocess.{key} must be a number")
                elif timeout_val < 1:
                    errors.append(f"system.timeouts.subprocess.{key} must be at least 1 second")
                elif timeout_val > 600:
                    errors.append(f"system.timeouts.subprocess.{key} must be at most 600 seconds (10 minutes)")
                else:
                    validated.setdefault('subprocess', {})
                    validated['subprocess'][key] = int(timeout_val)

    if errors:
        for error in errors:
            raise ValidationError(field_name, error)

    return validated


def get_timeouts(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get timeout values from settings with defaults.

    Returns a dict with 'network' and 'subprocess' sections.
    """
    default_timeouts = {
        'network': {
            'download': 300,
            'list': 60,
            'head': 10,
            'default': 30
        },
        'subprocess': {
            'quick': 1,
            'normal': 2,
            'long': 10,
            'reboot': 10
        }
    }

    # Get timeouts from settings or use defaults
    if 'system' in settings and 'timeouts' in settings['system']:
        timeouts = settings['system']['timeouts']
        # Apply defaults for missing keys
        for section, defaults in default_timeouts.items():
            if section not in timeouts:
                timeouts[section] = {}
            for key, default_value in defaults.items():
                if key not in timeouts[section]:
                    timeouts[section][key] = default_value
        return timeouts

    return default_timeouts.copy()
