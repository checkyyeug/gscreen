#!/usr/bin/env python3
"""
gScreen Flet App - Cross-platform UI for gScreen
Supports: Android, Windows, Linux, macOS, iOS, Web

Architecture:
┌─────────────────────────────────────────────┐
│           Flet UI Layer (Python)            │
│  (Android / Windows / Linux / iOS / Web)   │
├─────────────────────────────────────────────┤
│         Python Core (Direct Import)         │
│  - Google Drive Sync                        │
│  - Media Processing                         │
│  - Hardware Detection                       │
│  - Slideshow Control                        │
└─────────────────────────────────────────────┘
"""

import flet as ft
import threading
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hardware_detection import run_hardware_detection, HardwareInfo


class AppState:
    """Global application state"""
    def __init__(self):
        self.settings: Dict[str, Any] = {}
        self.hardware_info: Optional[HardwareInfo] = None
        self.media_list: List[Dict[str, Any]] = []
        self.current_index: int = 0
        self.is_playing: bool = False
        self.is_syncing: bool = False
        self.sync_status: str = "idle"
        self.page: Optional[ft.Page] = None
        self.settings_path: str = "settings.json"

    def load_settings(self):
        """Load settings from file"""
        try:
            with open(self.settings_path, 'r') as f:
                self.settings = __import__('json').load(f)
        except FileNotFoundError:
            self.settings = {}
        except Exception as e:
            print(f"Error loading settings: {e}")
            self.settings = {}

    def save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_path, 'w') as f:
                __import__('json').dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False


state = AppState()


def get_media_files() -> List[Dict[str, Any]]:
    """Get list of media files from cache directory"""
    cache_dir = state.settings.get('sync', {}).get('local_cache_dir', './media')
    cache_path = Path(cache_dir)

    if not cache_path.exists():
        return []

    supported = state.settings.get('supported_formats', [])
    media_files = []

    for f in cache_path.iterdir():
        if f.is_file() and f.suffix.lower() in supported:
            media_files.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "is_video": f.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv', '.webm']
            })

    media_files.sort(key=lambda x: x['name'])
    return media_files


def get_file_url(filename: str) -> str:
    """Get URL for media file (for web/remote access)"""
    # In local mode, return file path
    # In web mode, would return HTTP URL
    return str(Path(state.settings.get('sync', {}).get('local_cache_dir', './media')) / filename)


# ============== UI Components ==============

def create_drawer(page: ft.Page) -> ft.NavigationDrawer:
    """Create navigation drawer"""
    def on_nav_change(e):
        page.drawer.open = False
        index = e.control.selected_index
        if index == 0:
            page.go("/")
        elif index == 1:
            page.go("/sync")
        elif index == 2:
            page.go("/settings")
        elif index == 3:
            page.go("/hardware")

    return ft.NavigationDrawer(
        on_change=on_nav_change,
        controls=[
            ft.Container(height=20),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.SLIDESHOW,
                label="Slideshow",
            ),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.CLOUD_SYNC,
                label="Sync",
            ),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.SETTINGS,
                label="Settings",
            ),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.DEVICES,
                label="Hardware",
            ),
        ],
    )


def create_app_bar(title: str, page: ft.Page) -> ft.AppBar:
    """Create app bar"""
    return ft.AppBar(
        title=ft.Text(title),
        leading=ft.IconButton(
            icon=ft.Icons.MENU,
            on_click=lambda _: page.open(page.drawer),
        ),
        bgcolor=ft.Colors.BLUE_GREY_900,
    )


# ============== Pages ==============

def slideshow_view(page: ft.Page) -> ft.View:
    """Main slideshow view"""
    media_list = get_media_files()
    state.media_list = media_list

    # Current media info
    current_media = media_list[state.current_index] if media_list else None

    # Status text
    status_text = ft.Text(
        value=f"{state.current_index + 1} / {len(media_list)}" if media_list else "No media",
        size=14,
        color=ft.Colors.GREY_400,
    )

    filename_text = ft.Text(
        value=current_media["name"] if current_media else "No files",
        size=16,
        weight=ft.FontWeight.BOLD,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    # Image display
    image_control = ft.Image(
        src=get_file_url(current_media["name"]) if current_media and not current_media["is_video"] else None,
        fit=ft.ImageFit.CONTAIN,
        width=page.window_width - 40,
        height=page.window_height - 200,
    )

    if current_media and current_media["is_video"]:
        image_control = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.VIDEO_FILE, size=64, color=ft.Colors.GREY_400),
                ft.Text(current_media["name"], size=16),
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            bgcolor=ft.Colors.GREY_900,
            width=page.window_width - 40,
            height=page.window_height - 200,
        )

    # Control buttons
    def prev_media(e):
        if media_list:
            state.current_index = (state.current_index - 1) % len(media_list)
            page.go("/")
            page.update()

    def next_media(e):
        if media_list:
            state.current_index = (state.current_index + 1) % len(media_list)
            page.go("/")
            page.update()

    def toggle_play(e):
        state.is_playing = not state.is_playing
        play_btn.icon = ft.Icons.PAUSE if state.is_playing else ft.Icons.PLAY_ARROW
        page.update()

    play_btn = ft.IconButton(
        icon=ft.Icons.PLAY_ARROW if not state.is_playing else ft.Icons.PAUSE,
        icon_size=48,
        on_click=toggle_play,
    )

    # Progress bar
    progress = ft.ProgressBar(
        value=(state.current_index + 1) / len(media_list) if media_list else 0,
        width=page.window_width - 80,
        bar_height=4,
    )

    return ft.View(
        "/",
        appbar=create_app_bar("gScreen Slideshow", page),
        controls=[
            ft.Container(
                content=image_control,
                alignment=ft.alignment.center,
                expand=True,
            ),
            ft.Container(
                content=ft.Column([
                    progress,
                    ft.Row([
                        ft.IconButton(icon=ft.Icons.SKIP_PREVIOUS, icon_size=36, on_click=prev_media),
                        play_btn,
                        ft.IconButton(icon=ft.Icons.SKIP_NEXT, icon_size=36, on_click=next_media),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([
                        ft.Column([filename_text, status_text]),
                    ], alignment=ft.MainAxisAlignment.CENTER),
                ]),
                padding=20,
            ),
        ],
        drawer=page.drawer,
    )


def sync_view(page: ft.Page) -> ft.View:
    """Sync management view"""
    sync_status_text = ft.Text(value=state.sync_status.capitalize(), size=16)
    sync_progress = ft.ProgressBar(value=0, width=300)
    sync_log = ft.TextField(
        value="",
        multiline=True,
        read_only=True,
        min_lines=5,
        max_lines=10,
        width=page.window_width - 40,
    )

    def start_sync(e):
        state.is_syncing = True
        state.sync_status = "syncing"
        sync_status_text.value = "Syncing..."
        sync_btn.disabled = True
        page.update()

        # Run sync in background
        def run_sync():
            try:
                from gdrive_sync import GoogleDriveSync
                sync = GoogleDriveSync(state.settings_path)
                sync.initial_sync()
                state.sync_status = "completed"
                sync_status_text.value = "Completed"
            except Exception as ex:
                state.sync_status = "error"
                sync_status_text.value = f"Error: {ex}"
            finally:
                state.is_syncing = False
                sync_btn.disabled = False
                page.update()

        threading.Thread(target=run_sync, daemon=True).start()

    sync_btn = ft.ElevatedButton(
        "Sync Now",
        icon=ft.Icons.SYNC,
        on_click=start_sync,
        disabled=state.is_syncing,
    )

    # Google Drive URL display
    url = state.settings.get('google_drive_url', 'Not configured')
    if url.startswith('file:'):
        url_display = ft.Text(value=f"Loaded from: {url[5:]}", color=ft.Colors.GREY_400)
    else:
        url_display = ft.Text(value=url[:50] + "..." if len(url) > 50 else url, color=ft.Colors.GREY_400)

    return ft.View(
        "/sync",
        appbar=create_app_bar("Sync", page),
        controls=[
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.CLOUD),
                            title=ft.Text("Google Drive"),
                            subtitle=url_display,
                        ),
                        ft.Divider(),
                        ft.Container(
                            content=ft.Column([
                                ft.Row([ft.Text("Status:"), sync_status_text]),
                                sync_progress,
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                            padding=20,
                        ),
                        ft.Container(
                            content=sync_btn,
                            alignment=ft.alignment.center,
                            padding=10,
                        ),
                    ]),
                    padding=10,
                ),
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Sync Log", size=16, weight=ft.FontWeight.BOLD),
                        sync_log,
                    ]),
                    padding=15,
                ),
            ),
        ],
        drawer=page.drawer,
    )


def settings_view(page: ft.Page) -> ft.View:
    """Settings view"""
    display_settings = state.settings.get('display', {})
    audio_settings = state.settings.get('audio', {})
    slideshow_settings = state.settings.get('slideshow', {})
    sync_settings = state.settings.get('sync', {})

    # Google Drive URL
    url_field = ft.TextField(
        label="Google Drive URL",
        value=state.settings.get('google_drive_url', ''),
        hint_text="https://drive.google.com/drive/folders/... or file:url.txt",
        width=page.window_width - 60,
    )

    # Scale mode dropdown
    scale_dropdown = ft.Dropdown(
        label="Scale Mode",
        value=slideshow_settings.get('scale_mode', 'fit'),
        options=[
            ft.dropdown.Option("fit", "Fit (letterbox)"),
            ft.dropdown.Option("fill", "Fill (crop)"),
            ft.dropdown.Option("stretch", "Stretch"),
        ],
        width=200,
    )

    # HW accel dropdown
    hw_accel_dropdown = ft.Dropdown(
        label="Hardware Acceleration",
        value=display_settings.get('hw_accel', 'auto'),
        options=[
            ft.dropdown.Option("auto", "Auto"),
            ft.dropdown.Option("v4l2m2m", "V4L2 M2M"),
            ft.dropdown.Option("drm", "DRM"),
            ft.dropdown.Option("none", "None"),
        ],
        width=200,
    )

    # Rotation dropdown
    rotation_dropdown = ft.Dropdown(
        label="Rotation",
        value=str(display_settings.get('rotation', 0)),
        options=[
            ft.dropdown.Option("0", "0° (Landscape)"),
            ft.dropdown.Option("90", "90° CCW"),
            ft.dropdown.Option("180", "180°"),
            ft.dropdown.Option("270", "270° (90° CW)"),
        ],
        width=200,
    )

    # Audio switches
    audio_enabled = ft.Switch(
        label="Enable Audio",
        value=audio_settings.get('enabled', False),
    )

    audio_device = ft.Dropdown(
        label="Audio Device",
        value=audio_settings.get('device', 'hdmi'),
        options=[
            ft.dropdown.Option("hdmi", "HDMI"),
            ft.dropdown.Option("local", "Headphone"),
        ],
        width=200,
    )

    volume_slider = ft.Slider(
        min=0,
        max=100,
        value=audio_settings.get('volume', 50),
        label="Volume: {value}%",
        width=300,
    )

    # Sync interval
    sync_interval = ft.TextField(
        label="Sync Interval (minutes)",
        value=str(sync_settings.get('check_interval_minutes', 1)),
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def save_settings(e):
        state.settings['google_drive_url'] = url_field.value
        state.settings['slideshow']['scale_mode'] = scale_dropdown.value
        state.settings['display']['hw_accel'] = hw_accel_dropdown.value
        state.settings['display']['rotation'] = int(rotation_dropdown.value)
        state.settings['audio']['enabled'] = audio_enabled.value
        state.settings['audio']['device'] = audio_device.value
        state.settings['audio']['volume'] = int(volume_slider.value)
        state.settings['sync']['check_interval_minutes'] = int(sync_interval.value or 1)

        if state.save_settings():
            page.snack_bar = ft.SnackBar(ft.Text("Settings saved!"))
            page.snack_bar.open = True
        else:
            page.snack_bar = ft.SnackBar(ft.Text("Failed to save settings"))
            page.snack_bar.open = True
        page.update()

    save_btn = ft.ElevatedButton(
        "Save Settings",
        icon=ft.Icons.SAVE,
        on_click=save_settings,
    )

    return ft.View(
        "/settings",
        appbar=create_app_bar("Settings", page),
        controls=[
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Google Drive", size=16, weight=ft.FontWeight.BOLD),
                        url_field,
                    ]),
                    padding=15,
                ),
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Display", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row([scale_dropdown, hw_accel_dropdown]),
                        rotation_dropdown,
                    ]),
                    padding=15,
                ),
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Audio", size=16, weight=ft.FontWeight.BOLD),
                        ft.Row([audio_enabled, audio_device]),
                        ft.Row([ft.Text("Volume:"), volume_slider]),
                    ]),
                    padding=15,
                ),
            ),
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Sync", size=16, weight=ft.FontWeight.BOLD),
                        sync_interval,
                    ]),
                    padding=15,
                ),
            ),
            ft.Container(
                content=save_btn,
                alignment=ft.alignment.center,
                padding=20,
            ),
        ],
        drawer=page.drawer,
        scroll=ft.ScrollMode.AUTO,
    )


def hardware_view(page: ft.Page) -> ft.View:
    """Hardware information view"""
    hw = state.hardware_info

    if not hw:
        return ft.View(
            "/hardware",
            appbar=create_app_bar("Hardware Info", page),
            controls=[
                ft.Container(
                    content=ft.Text("Hardware detection not run"),
                    alignment=ft.alignment.center,
                    expand=True,
                )
            ],
            drawer=page.drawer,
        )

    # Build hardware info cards
    controls = []

    # Hardware card
    controls.append(
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.COMPUTER),
                        title=ft.Text("Hardware", size=16, weight=ft.FontWeight.BOLD),
                    ),
                    ft.Divider(),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([ft.Text("Model:", width=100), ft.Text(hw.rpi_model)]),
                            ft.Row([ft.Text("Generation:", width=100), ft.Text(f"Pi {hw.rpi_generation}" if hw.rpi_generation else "Unknown")]),
                            ft.Row([ft.Text("HW Accel:", width=100), ft.Text(hw.hw_accel_method if hw.hw_accel_available else "Not available")]),
                        ]),
                        padding=15,
                    ),
                ]),
            ),
        )
    )

    # Audio card
    controls.append(
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.SPEAKER),
                        title=ft.Text("Audio System", size=16, weight=ft.FontWeight.BOLD),
                    ),
                    ft.Divider(),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([ft.Text("System:", width=100), ft.Text(hw.audio_system)]),
                            ft.Row([ft.Text("HDMI Audio:", width=100), ft.Text(hw.hdmi_audio_card or "Not detected")]),
                            ft.Row([ft.Text("Headphone:", width=100), ft.Text("Available" if hw.headphone_available else "Not available")]),
                        ]),
                        padding=15,
                    ),
                ]),
            ),
        )
    )

    # Warnings card
    if hw.warnings:
        warnings_controls = []
        for w in hw.warnings:
            warnings_controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.WARNING, color=ft.Colors.AMBER),
                        ft.Text(w, color=ft.Colors.AMBER),
                    ]),
                    padding=5,
                )
            )
        controls.append(
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Warnings", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER),
                        *warnings_controls,
                    ]),
                    padding=15,
                ),
            )
        )

    # Suggestions card
    if hw.suggestions:
        suggestions_controls = []
        for s in hw.suggestions:
            suggestions_controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO, color=ft.Colors.BLUE),
                        ft.Text(s),
                    ]),
                    padding=5,
                )
            )
        controls.append(
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("Suggestions", size=16, weight=ft.FontWeight.BOLD),
                        *suggestions_controls,
                    ]),
                    padding=15,
                ),
            )
        )

    return ft.View(
        "/hardware",
        appbar=create_app_bar("Hardware Info", page),
        controls=controls,
        drawer=page.drawer,
        scroll=ft.ScrollMode.AUTO,
    )


# ============== Main App ==============

def main(page: ft.Page):
    """Main app entry point"""
    state.page = page

    # Page configuration
    page.title = "gScreen"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 400
    page.window.height = 700

    # Load settings
    state.load_settings()

    # Run hardware detection
    state.hardware_info = run_hardware_detection(state.settings)

    # Create navigation drawer
    page.drawer = create_drawer(page)

    # Route handling
    def route_change(route):
        page.views.clear()
        if page.route == "/":
            page.views.append(slideshow_view(page))
        elif page.route == "/sync":
            page.views.append(sync_view(page))
        elif page.route == "/settings":
            page.views.append(settings_view(page))
        elif page.route == "/hardware":
            page.views.append(hardware_view(page))
        else:
            page.views.append(slideshow_view(page))
        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Initial route
    page.go(page.route or "/")


def run_app():
    """Run the Flet app"""
    ft.app(target=main)


if __name__ == "__main__":
    run_app()
