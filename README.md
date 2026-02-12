# gScreen - Google Drive Photo Slideshow for Raspberry Pi

A lightweight photo and video slideshow application that displays media from Google Drive on HDMI output.

**Auto-detects display mode** - Works on Raspberry Pi OS with or without desktop.

## Features

- Displays photos and videos from Google Drive on HDMI output
- **Auto-detects display mode**: X11 (with desktop) or framebuffer (headless)
- Images scaled to fit/fill screen with aspect ratio preservation
- Fullscreen borderless display
- Configurable slideshow interval (default: 5 seconds)
- Auto-sync with Google Drive (configurable interval)
- Supports images: JPG, PNG, GIF, BMP, WebP, TIFF, and more
- Supports videos: MP4, AVI, MOV, MKV, WebM
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

| Setting | Description | Default |
|---------|-------------|---------|
| `google_drive_url` | Google Drive folder URL (public link) | Required |
| `display.hdmi_port` | HDMI port preference (0 or 1) | 1 |
| `display.background_color` | Background color [R,G,B] | [0,0,0] |
| `display.hide_mouse` | Hide mouse cursor on display | true |
| `display.show_statusbar` | Show status bar | true |
| `display.statusbar_position` | Status bar position: "top" or "bottom" | "bottom" |
| `display.rotation` | Display rotation: 0, 90, 180, or 270 | 0 |
| `display.rotation_mode` | Rotation method: "hardware" or "software" | "hardware" |
| `slideshow.interval_seconds` | Time between images/videos | 5 |
| `slideshow.scale_mode` | "fit", "fill", or "stretch" | "fit" |
| `sync.check_interval_minutes` | Sync check interval | 1 |
| `sync.local_cache_dir` | Local media cache directory | ./photos |
| `supported_formats` | File extensions to display | jpg,jpeg,png,gif,bmp,webp,tiff,mp4,avi,mov,mkv,webm |

**Supported formats:**
- Images: JPG, JPEG, PNG, GIF, BMP, WebP, TIFF, TIF, TGA, PBM, PGM, PPM, PNM, ICO, PCX, DIB, XBM
- Videos: MP4, AVI, MOV, MKV, WebM (via OpenCV)

### Status Bar Information

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
- Try using `gdown` manually: `gdown --folder <url> -O photos`
- Consider installing `rclone` for better reliability
- Check internet connection

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

## Keyboard Controls (when keyboard connected)

- `ESC` or `Q` - Quit slideshow
- `SPACE` - Skip to next image

Note: Keyboard input requires a USB keyboard connected directly to the Pi.

## Technical Details

This application uses:
- **SDL 2** with auto-detected driver (x11 or fbcon)
- **Pygame** for image rendering
- **Pillow** for image processing
- **gdown** or manual requests for Google Drive downloads

No specific desktop environment is required, making it ideal for:
- Digital photo frames
- Information displays
- Kiosks
- 24/7 signage displays

## License

MIT License - Feel free to use and modify for your projects.
