#!/usr/bin/env python3
"""
Hardware Detection Module for gScreen
Cross-platform hardware detection for Windows, Linux, macOS.
Detects platform, audio system, and hardware acceleration capabilities.
"""

import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class HardwareInfo:
    """Stores hardware detection results"""
    platform: str = "unknown"  # windows, linux, darwin
    platform_display: str = "Unknown"
    rpi_model: str = "N/A"
    rpi_generation: int = 0  # 0 = not a Pi, 3, 4, or 5
    audio_system: str = "unknown"  # alsa, pulseaudio, pipewire, wasapi, coreaudio
    hdmi_audio_card: Optional[str] = None
    headphone_available: bool = False
    hw_accel_available: bool = False
    hw_accel_method: str = "none"  # none, v4l2m2m, drm, d3d11va, videotoolbox
    recommendations: List[Tuple[str, str, str, str]] = field(default_factory=list)  # (key, current, recommended, status)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class HardwareDetector:
    """Detects hardware capabilities and generates recommendations"""

    def __init__(self, settings: dict):
        self.settings = settings
        self.info = HardwareInfo()
        self._detect_platform()

    def _detect_platform(self) -> None:
        """Detect the current platform"""
        self.info.platform = sys.platform
        if sys.platform == 'win32':
            self.info.platform_display = "Windows"
        elif sys.platform == 'darwin':
            self.info.platform_display = "macOS"
        elif sys.platform.startswith('linux'):
            self.info.platform_display = "Linux"
        else:
            self.info.platform_display = f"Unknown ({sys.platform})"

    def detect_all(self) -> HardwareInfo:
        """Run all hardware detection"""
        # Platform-specific detection
        if sys.platform.startswith('linux'):
            self._detect_linux()
        elif sys.platform == 'win32':
            self._detect_windows()
        elif sys.platform == 'darwin':
            self._detect_macos()

        self._detect_ffmpeg()
        self._generate_recommendations()
        return self.info

    def _detect_linux(self) -> None:
        """Linux-specific hardware detection"""
        self._detect_rpi_model()
        self._detect_audio_system()
        self._detect_audio_devices()
        self._detect_hw_accel()

    def _detect_windows(self) -> None:
        """Windows-specific hardware detection"""
        self.info.audio_system = "wasapi"
        self.info.hw_accel_method = "d3d11va"

        # Try to detect hardware acceleration
        try:
            result = subprocess.run(
                ['ffmpeg', '-hwaccels'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                hwaccels = result.stdout.lower()
                if 'd3d11va' in hwaccels or 'dxva2' in hwaccels:
                    self.info.hw_accel_available = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_macos(self) -> None:
        """macOS-specific hardware detection"""
        self.info.audio_system = "coreaudio"
        self.info.hw_accel_method = "videotoolbox"

        # Try to detect hardware acceleration
        try:
            result = subprocess.run(
                ['ffmpeg', '-hwaccels'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                hwaccels = result.stdout.lower()
                if 'videotoolbox' in hwaccels:
                    self.info.hw_accel_available = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_rpi_model(self) -> None:
        """Detect Raspberry Pi model from /proc/cpuinfo (Linux only)"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()

            # Look for Raspberry Pi model
            model_match = re.search(r'Model\s*:\s*(.+)', cpuinfo)
            if model_match:
                self.info.rpi_model = model_match.group(1).strip()
            else:
                # Try alternative format
                hardware_match = re.search(r'Hardware\s*:\s*(.+)', cpuinfo)
                if hardware_match:
                    self.info.rpi_model = hardware_match.group(1).strip()

            # Detect generation from model string
            model_lower = self.info.rpi_model.lower()
            if 'raspberry pi 5' in model_lower or 'rpi 5' in model_lower or 'rp1' in model_lower:
                self.info.rpi_generation = 5
            elif 'raspberry pi 4' in model_lower or 'rpi 4' in model_lower or 'bcm2711' in cpuinfo.lower():
                self.info.rpi_generation = 4
            elif 'raspberry pi 3' in model_lower or 'rpi 3' in model_lower or 'bcm2837' in cpuinfo.lower():
                self.info.rpi_generation = 3
            elif 'raspberry pi 2' in model_lower or 'rpi 2' in model_lower:
                self.info.rpi_generation = 2
            elif 'raspberry pi' in model_lower or 'bcm2835' in cpuinfo.lower() or 'bcm2836' in cpuinfo.lower():
                # Default to Pi 1/Zero for older models
                self.info.rpi_generation = 1

        except (FileNotFoundError, PermissionError):
            self.info.rpi_model = "Not a Raspberry Pi"
            self.info.rpi_generation = 0

    def _detect_audio_system(self) -> None:
        """Detect audio system on Linux (ALSA, PulseAudio, PipeWire)"""
        # Check for PipeWire first (newest)
        try:
            result = subprocess.run(['pw-cli', '--version'], capture_output=True, timeout=2)
            if result.returncode == 0:
                self.info.audio_system = "pipewire"
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check for PulseAudio
        try:
            result = subprocess.run(['pactl', 'info'], capture_output=True, timeout=2)
            if result.returncode == 0:
                self.info.audio_system = "pulseaudio"
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Default to ALSA
        self.info.audio_system = "alsa"

    def _detect_audio_devices(self) -> None:
        """Detect available audio devices on Linux"""
        try:
            result = subprocess.run(
                ['aplay', '-l'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                output = result.stdout

                # Find HDMI audio cards
                hdmi_match = re.search(r'card (\d+).*\[HDMI|vc4hdmi', output, re.IGNORECASE)
                if hdmi_match:
                    self.info.hdmi_audio_card = f"Card [{hdmi_match.group(1)}]"

                # Check for headphone jack
                if re.search(r'card \d+.*\[Headphone|bcm2835 Headphone', output, re.IGNORECASE):
                    self.info.headphone_available = True

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _detect_hw_accel(self) -> None:
        """Detect hardware video acceleration capabilities on Linux"""
        # Check for v4l2m2m support
        try:
            result = subprocess.run(
                ['ffmpeg', '-hwaccels'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                hwaccels = result.stdout.lower()
                if 'v4l2m2m' in hwaccels:
                    self.info.hw_accel_available = True
                    self.info.hw_accel_method = 'v4l2m2m'
                elif 'drm' in hwaccels:
                    self.info.hw_accel_available = True
                    self.info.hw_accel_method = 'drm'

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Override based on RPi generation
        if self.info.rpi_generation == 3:
            # RPi 3 has limited hardware acceleration support
            self.info.hw_accel_available = False
            self.info.hw_accel_method = 'none'

    def _detect_ffmpeg(self) -> None:
        """Check if ffmpeg is available (all platforms)"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5,
                # On Windows, suppress the console window
                **({'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {})
            )
            if result.returncode != 0:
                self.info.warnings.append("ffmpeg not found - video playback may not work")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.info.warnings.append("ffmpeg not found - video playback may not work")

    def _generate_recommendations(self) -> None:
        """Generate configuration recommendations based on detected hardware"""
        display_settings = self.settings.get('display', {})
        audio_settings = self.settings.get('audio', {})

        # Platform-specific recommendations
        if sys.platform.startswith('linux'):
            self._generate_linux_recommendations(display_settings, audio_settings)
        elif sys.platform == 'win32':
            self._generate_windows_recommendations(display_settings)
        elif sys.platform == 'darwin':
            self._generate_macos_recommendations(display_settings)

    def _generate_linux_recommendations(self, display_settings: dict, audio_settings: dict) -> None:
        """Generate recommendations for Linux"""
        # HW acceleration recommendation
        current_hw_accel = display_settings.get('hw_accel', 'auto')
        if self.info.rpi_generation == 3:
            if current_hw_accel not in ['none', False]:
                self.info.recommendations.append(
                    ('display.hw_accel', str(current_hw_accel), 'none', 'RECOMMEND CHANGE')
                )
            else:
                self.info.recommendations.append(
                    ('display.hw_accel', str(current_hw_accel), 'none', 'OK')
                )
            self.info.warnings.append(
                "RPi 3 detected. Hardware acceleration may not work. "
                "Recommend setting hw_accel to 'none'."
            )
        elif self.info.rpi_generation >= 4:
            if self.info.hw_accel_available:
                if current_hw_accel == 'none':
                    self.info.recommendations.append(
                        ('display.hw_accel', str(current_hw_accel), 'auto', 'OPTIONAL')
                    )
                else:
                    self.info.recommendations.append(
                        ('display.hw_accel', str(current_hw_accel), str(current_hw_accel), 'OK')
                    )
            else:
                self.info.recommendations.append(
                    ('display.hw_accel', str(current_hw_accel), 'none', 'OK')
                )

        # Audio device recommendation
        current_audio = audio_settings.get('device', 'hdmi')
        if self.info.hdmi_audio_card:
            self.info.recommendations.append(
                ('audio.device', str(current_audio), str(current_audio), 'OK')
            )
        else:
            self.info.warnings.append(
                "No HDMI audio device detected. Audio may not work via HDMI."
            )

        # SDL audio driver
        self.info.recommendations.append(
            ('SDL_AUDIODRIVER', self.info.audio_system, self.info.audio_system, 'INFO')
        )

        # Add suggestions
        if self.info.audio_system == 'alsa':
            self.info.suggestions.append(
                "Using ALSA directly. ALSA warning messages are harmless."
            )

    def _generate_windows_recommendations(self, display_settings: dict) -> None:
        """Generate recommendations for Windows"""
        current_hw_accel = display_settings.get('hw_accel', 'auto')
        if self.info.hw_accel_available:
            self.info.recommendations.append(
                ('display.hw_accel', str(current_hw_accel), 'auto', 'OK')
            )
        else:
            self.info.recommendations.append(
                ('display.hw_accel', str(current_hw_accel), 'none', 'OK')
            )

        self.info.recommendations.append(
            ('SDL_AUDIODRIVER', 'wasapi', 'wasapi', 'INFO')
        )

        self.info.suggestions.append(
            "Windows detected. Using WASAPI for audio and DirectX for video acceleration."
        )

    def _generate_macos_recommendations(self, display_settings: dict) -> None:
        """Generate recommendations for macOS"""
        current_hw_accel = display_settings.get('hw_accel', 'auto')
        if self.info.hw_accel_available:
            self.info.recommendations.append(
                ('display.hw_accel', str(current_hw_accel), 'auto', 'OK')
            )
        else:
            self.info.recommendations.append(
                ('display.hw_accel', str(current_hw_accel), 'none', 'OK')
            )

        self.info.recommendations.append(
            ('SDL_AUDIODRIVER', 'coreaudio', 'coreaudio', 'INFO')
        )

        self.info.suggestions.append(
            "macOS detected. Using CoreAudio for audio and VideoToolbox for video acceleration."
        )


def suppress_alsa_messages() -> None:
    """Apply environment variables to suppress ALSA messages (Linux only)"""
    if sys.platform.startswith('linux'):
        os.environ['ALSA_CONFIG_PATH'] = '/dev/null'
        # Keep PYTHONWARNINGS if not already set
        if 'PYTHONWARNINGS' not in os.environ:
            os.environ['PYTHONWARNINGS'] = 'ignore'


def run_hardware_detection(settings: dict) -> HardwareInfo:
    """Run hardware detection and return results"""
    detector = HardwareDetector(settings)
    return detector.detect_all()


def print_config_recommendations(hw_info: HardwareInfo) -> None:
    """Print a friendly hardware detection report"""
    print()
    print("=" * 60)
    print("         HARDWARE DETECTION REPORT")
    print("=" * 60)
    print()

    # Platform section
    print("[Platform]")
    print(f"  OS:            {hw_info.platform_display}")
    print()

    # Hardware section (Linux/RPi specific)
    if sys.platform.startswith('linux'):
        print("[Hardware]")
        if hw_info.rpi_generation > 0:
            print(f"  Model:         {hw_info.rpi_model}")
            gen_name = f"Raspberry Pi {hw_info.rpi_generation}"
            print(f"  Generation:    {gen_name}")
        else:
            print(f"  Model:         {hw_info.rpi_model}")
        accel_status = hw_info.hw_accel_method if hw_info.hw_accel_available else "Not available"
        print(f"  HW Accel:      {accel_status}")
        print()

        # Audio section (Linux specific)
        print("[Audio System]")
        print(f"  System:        {hw_info.audio_system}")
        hdmi_audio = hw_info.hdmi_audio_card or "Not detected"
        print(f"  HDMI Audio:    {hdmi_audio}")
        headphone = "Available" if hw_info.headphone_available else "Not available"
        print(f"  Headphone:     {headphone}")
        print()
    else:
        # Non-Linux platform info
        print("[Hardware]")
        print(f"  HW Accel:      {hw_info.hw_accel_method}")
        print()

    # Recommendations section
    if hw_info.recommendations:
        print("[Configuration Recommendations]")
        print("-" * 40)
        for key, current, recommended, status in hw_info.recommendations:
            status_display = f"[{status}]"
            print(f"  {key:<22} '{current}' -> '{recommended}' {status_display}")
        print()

    # Warnings section
    if hw_info.warnings:
        print("[Warnings]")
        for warning in hw_info.warnings:
            print(f"  ! {warning}")
        print()

    # Suggestions section
    if hw_info.suggestions:
        print("[Suggestions]")
        for suggestion in hw_info.suggestions:
            print(f"  * {suggestion}")
        print()

    print("=" * 60)
    print()


if __name__ == "__main__":
    # Test hardware detection
    suppress_alsa_messages()
    hw_info = run_hardware_detection({})
    print_config_recommendations(hw_info)
