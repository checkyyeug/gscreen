# gScreen - Google Drive Photo Slideshow for Raspberry Pi

A lightweight photo and video slideshow application that displays media from Google Drive on HDMI output.

**Auto-detects display mode** - Works on Raspberry Pi OS with or without desktop.

## Features

- Displays media from Google Drive on HDMI output
- **Auto-detects display mode**: X11 (with desktop) or framebuffer (headless)
- Images scaled to fit/fill screen with aspect ratio preservation
- Fullscreen borderless display
- Configurable slideshow interval (default: 5 seconds)
- **Incremental sync**: Only downloads new/changed files from Google Drive
- Smart sync: Compares file sizes before downloading to save bandwidth
- **No-media waiting mode**: Displays message when no files are available, auto-starts when files arrive
- **Schedule countdown**: Shows 60-second countdown when starting outside scheduled hours
- **UTF-8 support**: Handles Chinese and other non-ASCII filenames correctly
- **System time sync**: Automatically syncs system time via NTP during sync operations
- Supports images: JPG, PNG, GIF, BMP, WebP, TIFF, and more
- Supports videos: MP4, AVI, MOV, MKV, WebM
- Optional audio playback for videos (via ffmpeg)
- Software display rotation (0°, 90°, 180°, 270°)
- Configurable status bar with orientation-based layouts
- Auto-start on boot via systemd service
- Low CPU usage, suitable for 24/7 operation

## Requirements

- Raspberry Pi 3/4/5 (or any Linux system with HDMI output)
- Python 3.8+
- Internet connection for Google Drive sync
- **No desktop environment required** (works on Raspberry Pi OS Lite)

## How Display Mode Works

The application automatically detects and uses the best available display method:

| System Type | Display Method | Requirements |
|-------------|----------------|--------------|
| Raspberry Pi OS (with desktop) | X11 | None (uses existing X server) |
| Raspberry Pi OS Lite | Framebuffer (fbcon) | User in `video` group |
| Any Linux with X11 running | X11 | X11 running |

## Installation

### 1. Clone or download the project

```bash
cd /home/pi/Projects/gScreen
```

### 2. Run the installation script

```bash
chmod +x install.sh
./install.sh
```

The installation script will:
- Install system dependencies (SDL2, Python packages)
- Create a Python virtual environment
- Install required Python packages
- Add your user to the `video` group (for display access)
- Create wrapper scripts (`run.sh`, `sync.sh`)

### 3. Log out and log back in

**Important:** After installation, log out and log back in for the `video` group membership to take effect.

### 4. Configure settings

Edit `settings.json` and add your Google Drive folder URL:

```json
{
    "google_drive_url": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID?usp=sharing",
    ...
}
```

The Google Drive folder must be set to "Anyone with the link can view".

### 5. Run the application

```bash
./run.sh
```

### 6. (Optional) Install systemd service

For auto-start on boot:

```bash
chmod +x install_service.sh
sudo ./install_service.sh
```

## Usage

### Manual start

```bash
./run.sh
```

or

```bash
python3 main.py
```

### Command-line options

```bash
python3 main.py [OPTIONS]

Options:
  --sync-only       Only sync from Google Drive, don't start slideshow
  --display-only    Skip initial sync, just start slideshow
  --settings FILE   Use custom settings file
```

### Service control

```bash
# Start service
sudo systemctl start gscreen

# Stop service
sudo systemctl stop gscreen

# Restart service
sudo systemctl restart gscreen

# Check status
sudo systemctl status gscreen

# View logs
sudo journalctl -u gscreen -f
```

## Configuration (settings.json)

The `settings.json` file controls all aspects of gScreen. Below is a complete reference of all available options.

### Complete Example

```json
{
    "google_drive_url": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID",
    "display": {
        "hdmi_port": 1,
        "fullscreen": true,
        "borderless": true,
        "background_color": [0, 0, 0],
        "hide_mouse": true,
        "show_statusbar": true,
        "rotation": 0,
        "rotation_mode": "hardware",
        "statusbar_layout": {
            "opacity": 0.3,
            "landscape": {
                "file_info_position": "top",
                "system_info_position": "bottom",
                "progress_position": "bottom"
            },
            "portrait": {
                "file_info_position": "bottom",
                "system_info_position": "top",
                "progress_position": "top"
            }
        }
    },
    "slideshow": {
        "interval_seconds": 5,
        "scale_mode": "fit"
    },
    "schedule": {
        "enabled": false,
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "start": "07:00",
        "stop": "23:00"
    },
    "audio": {
        "enabled": false,
        "device": "hdmi",
        "volume": 50
    },
    "sync": {
        "check_interval_minutes": 1,
        "local_cache_dir": "./media",
        "download_on_start": false
    },
    "supported_formats": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
        ".mp4", ".avi", ".mov", ".mkv", ".webm"
    ]
}
```

### Option Reference

#### Root Level Options

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `google_drive_url` | string | Yes | - | Public Google Drive folder URL |
| `supported_formats` | array | No | see below | File extensions to display |

#### Display Options (`display`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `hdmi_port` | integer | `1` | HDMI port to use (0 or 1) |
| `fullscreen` | boolean | `true` | Run in fullscreen mode |
| `borderless` | boolean | `true` | Remove window borders |
| `background_color` | array | `[0,0,0]` | Background color [R, G, B] (0-255 each) |
| `hide_mouse` | boolean | `true` | Hide mouse cursor after inactivity |
| `show_statusbar` | boolean | `true` | Show status bar overlay |
| `rotation` | integer | `0` | Display rotation: 0, 90, 180, or 270 |
| `rotation_mode` | string | `"hardware"` | Rotation method: `"hardware"` or `"software"` |
| `statusbar_layout` | object | see below | Status bar configuration per orientation |

**Rotation Options:**
- `0` - No rotation (default)
- `90` - Rotate 90° counter-clockwise (portrait)
- `180` - Rotate 180° (upside-down)
- `270` - Rotate 270° (90° clockwise, portrait)

**Rotation Modes:**
- `hardware` - Use system-level rotation (requires config file edit)
- `software` - Use pygame for rotation (recommended, easier)

#### Status Bar Layout (`display.statusbar_layout`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `opacity` | float | `0.3` | Status bar opacity (0.0-1.0) |
| `landscape` | object | see below | Layout for 0°/180° rotation |
| `portrait` | object | see below | Layout for 90°/270° rotation |

**Orientation Layout Options** (apply to both `landscape` and `portrait`):

| Option | Type | Values | Description |
|--------|------|--------|-------------|
| `file_info_position` | string | `"top"`, `"bottom"` | Where to show file info (left side) |
| `system_info_position` | string | `"top"`, `"bottom"` | Where to show system info (right side) |
| `progress_position` | string | `"top"`, `"bottom"` | Where to show progress (center) |

**Status Bar Sections:**
- **File Info** (left): File name, date, size, format, dimensions
- **System Info** (right): Resolution, rotation, WiFi, time, total count
- **Progress** (center): Current/total count and countdown

#### Slideshow Options (`slideshow`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `interval_seconds` | integer | `5` | Seconds between images |
| `scale_mode` | string | `"fit"` | How to scale images: `"fit"`, `"fill"`, or `"stretch"` |

**Scale Modes:**
- `"fit"` - Letterbox/pillarbox (show full image with borders)
- `"fill"` - Crop to fill screen (no borders, may crop edges)
- `"stretch"` - Stretch to fill (may distort aspect ratio)

#### Schedule Options (`schedule`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable scheduled on/off times |
| `days` | array | All days | Days to run: `["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]` |
| `start` | string | `"07:00"` | Start time (HH:MM format, 24-hour) |
| `stop` | string | `"23:00"` | Stop time (HH:MM format, 24-hour) |

**Schedule Behavior:**
- During active time: Normal slideshow operation
- Outside active time: Screen goes black (sleep mode), playback stops
- When schedule ends during active playback: Screen sleeps, resumes at same position when schedule starts again
- **Startup outside schedule**: Shows 60-second countdown before entering sleep mode, displays "不在 Schedule 内" message

**Schedule Examples:**
```json
// Business hours (weekdays 9am-6pm)
"schedule": {
    "enabled": true,
    "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "start": "09:00",
    "stop": "18:00"
}

// All day, every day
"schedule": {
    "enabled": true,
    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "start": "00:00",
    "stop": "23:59"
}

// Weekend only
"schedule": {
    "enabled": true,
    "days": ["Sat", "Sun"],
    "start": "08:00",
    "stop": "22:00"
}
```

#### Audio Options (`audio`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable audio for video playback |
| `device` | string | `"hdmi"` | Audio output: `"hdmi"` or `"local"` |
| `volume` | integer | `50` | Volume level (0-100) |

**Audio Devices:**
- `"hdmi"` - Output through HDMI (default)
- `"local"` - Output through 3.5mm headphone jack

**Note:** Audio requires ffmpeg to be installed (included in install.sh). If you ran install.sh before audio support was added:
```bash
sudo apt install ffmpeg
```

#### Sync Options (`sync`)

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `check_interval_minutes` | integer | `1` | Minutes between sync checks |
| `local_cache_dir` | string | `"./media"` | Directory to store downloaded media |
| `download_on_start` | boolean | `false` | Download all media on startup |
| `timezone_offset` | integer | `8` | Timezone offset from UTC (-12 to +14) |
| `sync_system_time` | boolean | `true` | Enable automatic system time sync via NTP |

**Sync Behavior:**
- The app uses incremental sync to save bandwidth
- Only downloads new or changed files from Google Drive
- Compares file sizes before downloading
- Skips files that already exist locally with the same size
- If no media files are found, displays a waiting message and checks periodically for new files
- Supports Chinese and UTF-8 filenames

**Timezone Settings:**
The `timezone_offset` sets your local timezone offset from UTC. Common values:
- `8` - Beijing, Shanghai, Singapore (UTC+8)
- `9` - Tokyo, Seoul (UTC+9)
- `0` - London, Dublin (UTC+0)
- `-5` - New York, Eastern Time (UTC-5)
- `-8` - Los Angeles, Pacific Time (UTC-8)

**System Time Sync:**
When `sync_system_time` is enabled, the app will automatically sync the system time during each sync operation. This requires sudo permissions. To enable passwordless time sync for the systemd service:

```bash
sudo visudo
# Add the following line:
rpi4 ALL=(ALL) NOPASSWD: /usr/bin/timedatectl, /usr/bin/date
```

Replace `rpi4` with your actual username. This allows the service to set the time without requiring a password prompt.

#### Supported Formats

Default supported formats:

**Images:** `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`, `.tif`, `.tga`, `.pbm`, `.pgm`, `.ppm`, `.pnm`, `.ico`, `.pcx`, `.dib`, `.xbm`

**Videos:** `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`

You can customize this list in `settings.json`. Images are displayed via pygame/Pillow, videos via OpenCV.

**Format Notes:**
- MP4 with H.264 codec is recommended for best performance on Raspberry Pi
- GIF animations are displayed as static images (first frame)
- Large videos may have performance issues on older Raspberry Pi models

### Display Rotation

**Landscape mode (rotation 0° or 180°):**

Status bar at **top**:
- Center: Image progress (current/total) and countdown

Status bar at **bottom**:
- Left side: File name, date, size, format, dimensions
- Right side: Resolution, rotation, WiFi, time, total count

**Portrait mode (rotation 90° or 270°):**

Status bar at **top**:
- Left side: Resolution, WiFi, sync time, total count

Status bar at **bottom**:
- Right side: Date, time, file name, format, dimensions, progress

### Display Rotation

For portrait or upside-down displays, you can rotate the output:

```json
"display": {
    "rotation": 270,
    "rotation_mode": "software"
}
```

**Rotation values:**
- `0` - No rotation (default)
- `90` - Rotate 90° counter-clockwise (portrait mode)
- `180` - Rotate 180° (upside-down)
- `270` - Rotate 270° (or 90° clockwise, portrait mode)

**Rotation modes:**

| Mode | Description | Pros | Cons |
|------|-------------|------|------|
| `hardware` | Rotate via system config (default) | No CPU overhead, full performance | Requires editing `/boot/firmware/cmdline.txt` |
| `software` | Rotate via pygame (recommended) | Easy to configure, works immediately | Slight CPU usage, minor performance impact |

**Hardware rotation setup (for KMS/DRM systems):**

Edit `/boot/firmware/cmdline.txt` and add to the end of the line:
```
video=HDMI-A-1:270x16   # For HDMI (270° rotation)
```
or
```
video=DSI-1:270x16     # For DSI/official display
```

Then reboot:
```bash
sudo reboot
```

**Software rotation setup:**

Simply set `rotation_mode` to `software` in settings.json - no system changes needed!

## Display Setup on Raspberry Pi

### HDMI Configuration

If HDMI output is not detected, edit `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Add/uncomment:
```
hdmi_force_hotplug=1
hdmi_drive=1
```

For specific HDMI ports:
```
hdmi_force_hotplug:0=1
hdmi_drive:0=1
```

### Disable Screen Blanking

To prevent the screen from turning off:

**For Raspberry Pi OS Lite (console):**
```bash
sudo nano /etc/kbd/config
# Set: BLANK_TIME=0, POWERDOWN_TIME=0
```

**For Raspberry Pi OS with desktop:**
```bash
# Disable screen blanking in lightdm
sudo nano /etc/lightdm/lightdm.conf
# Add under [SeatDefaults]: xserver-command=X -s 0 -dpms
```

**Alternative using systemd (works for both):**
```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

## Troubleshooting

### "No permission to access /dev/fb0"
- Add user to video group: `sudo usermod -a -G video $USER`
- Log out and log back in (or reboot)
- Verify with: `groups` (should include `video`)

### Black screen on startup
- Check if HDMI is connected: `ls /sys/class/drm/`
- Verify framebuffer exists: `ls -l /dev/fb0`
- Check display detection: `cat /sys/class/graphics/fb0/virtual_size`

### Google Drive sync not working
- Verify folder is public (Anyone with link can view)
- **Recommended**: Install `rclone` for efficient sync with modification time checking
  - `sudo apt install rclone && rclone config` (follow prompts to set up Google Drive)
- Alternatively, try `gdown` manually: `gdown --folder <url> -O media`
- Check internet connection

**Sync methods comparison:**
| Method | Modification Time Check | Incremental Download | Setup |
|--------|------------------------|---------------------|-------|
| rclone (recommended) | Yes | Yes | Requires config |
| gdown (fallback) | Yes | Yes | Works immediately |

**Note:** Both methods now support incremental sync - only downloading new or changed files.

### Images not scaling correctly
- Change `scale_mode` in settings.json:
  - "fit" = letterbox/pillarbox (shows full image with borders)
  - "fill" = crop to fill screen (no borders)
  - "stretch" = stretch to fill (may distort)

### High CPU usage
- Increase `interval_seconds` in settings
- Lower resolution images recommended (1920x1080 max)
- Use optimized JPEG images

### Display initialization errors
- The app auto-detects X11 or framebuffer
- If detection fails, try: `export DISPLAY=:0 && ./run.sh`
- Check what's available: `ls /tmp/.X11-unix/` `ls /dev/fb*`

### System time sync not working
- Time sync requires sudo permissions to modify system time
- If running as a service, add passwordless sudo entry (see Sync Options above)
- Check logs for `[TimeSync]` messages to see what's happening
- If you see "Authentication required", configure sudoers as shown above
- Available time sync methods (tried in order):
  1. `timedatectl` - Systemd time service (preferred)
  2. `ntpdate` - Traditional NTP client
  3. Python `ntplib` - Pure Python NTP (fallback)

### Chinese filenames not displaying correctly
- The app uses UTF-8 encoding for all operations
- Ensure your terminal locale supports UTF-8: `locale charmap`
- If needed, set locale: `sudo raspi-config` → Internationalisation Options → Locale
- Select `en_US.UTF-8` or `zh_CN.UTF-8`

## Keyboard Controls (when keyboard connected)

- `ESC` or `Q` - Quit slideshow
- `SPACE` - Skip to next image

Note: Keyboard input requires a USB keyboard connected directly to the Pi.

## Technical Details

This application uses:
- **SDL 2** with auto-detected driver (KMSDRM, fbcon, or x11)
- **pygame-ce** for image and video rendering
- **OpenCV** for video frame decoding
- **ffmpeg/ffplay** for audio playback (when enabled)
- **Pillow** for image processing
- **gdown** or manual requests for Google Drive downloads

No specific desktop environment is required, making it ideal for:
- Digital photo frames
- Information displays
- Kiosks
- 24/7 signage displays

## License

MIT License - Feel free to use and modify for your projects.
