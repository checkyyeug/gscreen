# gScreen - Google Drive Photo Slideshow for Raspberry Pi

A lightweight photo slideshow application that displays images from Google Drive on HDMI output.

**No desktop environment required** - runs directly on Raspberry Pi OS Lite using framebuffer.

## Features

- Displays photos from Google Drive on HDMI output
- Uses framebuffer directly - no X11/desktop required
- Images scaled to fit/fill screen with aspect ratio preservation
- Fullscreen borderless display
- Configurable slideshow interval (default: 5 seconds)
- Auto-sync with Google Drive (configurable interval)
- Supports: JPG, PNG, GIF, BMP, WebP
- Auto-start on boot via systemd service
- Low CPU usage, suitable for 24/7 operation

## Requirements

- Raspberry Pi 3/4/5 (or any Linux system with HDMI output)
- Python 3.8+
- Internet connection for Google Drive sync
- **No desktop environment required** (works on Raspberry Pi OS Lite)

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

### 3. Add user to video group (required for framebuffer access)

```bash
sudo usermod -a -G video $USER
```

**Important:** Log out and log back in (or reboot) for the group change to take effect.

### 4. Configure settings

Edit `settings.json` and add your Google Drive folder URL:

```json
{
    "google_drive_url": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID?usp=sharing",
    ...
}
```

The Google Drive folder must be set to "Anyone with the link can view".

### 5. (Optional) Install systemd service

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

# Check status
sudo systemctl status gscreen

# View logs
sudo journalctl -u gscreen -f
```

## Configuration (settings.json)

| Setting | Description | Default |
|---------|-------------|---------|
| `google_drive_url` | Google Drive folder URL (public link) | Required |
| `display.background_color` | Background color [R,G,B] | [0,0,0] |
| `slideshow.interval_seconds` | Time between images | 5 |
| `slideshow.scale_mode` | "fit", "fill", or "stretch" | "fit" |
| `sync.check_interval_minutes` | Sync check interval | 1 |
| `sync.local_cache_dir` | Local photo cache directory | ./photos |
| `supported_formats` | Image file extensions | jpg,jpeg,png,gif,bmp,webp |

**Note:** `hdmi_port` setting is kept for compatibility but not used in framebuffer mode. The system uses `/dev/fb0` which corresponds to the active HDMI output.

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

```bash
# Disable screen blanking
sudo nano /etc/lightdm/lightdm.conf
# Add: xserver-command=X -s 0 -dpms

# Or use console (for Lite version)
sudo nano /etc/kbd/config
# Set: BLANK_TIME=0, POWERDOWN_TIME=0
```

## Troubleshooting

### "No permission to access /dev/fb0"
- Add user to video group: `sudo usermod -a -G video $USER`
- Log out and log back in (or reboot)

### Black screen
- Check if HDMI is connected: `ls /sys/class/drm/`
- Verify framebuffer exists: `ls -l /dev/fb0`
- Check permissions: `groups` (should include `video`)

### Google Drive sync not working
- Verify folder is public (Anyone with link can view)
- Try using `gdown` manually: `gdown --folder <url> -O photos`
- Check internet connection

### Images not scaling correctly
- Change `scale_mode` in settings.json
- "fit" = letterbox/pillarbox (shows full image)
- "fill" = crop to fill screen (no borders)
- "stretch" = stretch to fill (may distort)

### High CPU usage
- Increase `interval_seconds` in settings
- Lower resolution images recommended (1920x1080 max)
- Use optimized JPEG images

## Keyboard Controls (when connected)

- `ESC` or `Q` - Quit slideshow
- `SPACE` - Skip to next image

Note: Keyboard input may not work without a USB keyboard connected directly to the Pi.

## Technical Details

This application uses:
- **SDL with fbcon driver** for direct framebuffer access
- **Pygame** for image rendering
- **Pillow** for image processing
- **gdown** for Google Drive downloads

No X11 or desktop environment is required, making it ideal for:
- Digital photo frames
- Information displays
- Kiosks
- 24/7 signage displays
