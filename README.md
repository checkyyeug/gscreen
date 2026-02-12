# gScreen - Google Drive Photo Slideshow for Raspberry Pi 4

A photo slideshow application that displays images from Google Drive on HDMI1 output.

## Features

- Displays photos from Google Drive on HDMI1 (secondary display)
- Images scaled to fit/fill screen with aspect ratio preservation
- Borderless fullscreen display
- 5-second slideshow interval (configurable)
- Auto-sync with Google Drive every minute
- Supports: JPG, PNG, GIF, BMP, WebP
- Auto-start on boot via systemd service

## Requirements

- Raspberry Pi 4 (or any Linux system with dual HDMI output)
- Python 3.8+
- Internet connection for Google Drive sync

## Installation

### 1. Clone or download the project

```bash
cd /home/rpi4/Projects/gScreen
```

### 2. Run the installation script

```bash
chmod +x install.sh
./install.sh
```

### 3. Configure settings

Edit `settings.json` and add your Google Drive folder URL:

```json
{
    "google_drive_url": "https://drive.google.com/drive/folders/YOUR_FOLDER_ID?usp=sharing",
    ...
}
```

### 4. (Optional) Install systemd service

For auto-start on boot:

```bash
chmod +x install_service.sh
sudo ./install_service.sh
```

## Usage

### Manual start

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
  --hdmi PORT       Override HDMI port (0 or 1)
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
| `display.hdmi_port` | HDMI output (0 or 1) | 1 |
| `display.background_color` | Background color [R,G,B] | [0,0,0] |
| `slideshow.interval_seconds` | Time between images | 5 |
| `slideshow.scale_mode` | "fit", "fill", or "stretch" | "fit" |
| `sync.check_interval_minutes` | Sync check interval | 1 |
| `sync.local_cache_dir` | Local photo cache directory | ./photos |
| `supported_formats` | Image file extensions | jpg,jpeg,png,gif,bmp,webp |

## Display Setup on Raspberry Pi

### HDMI1 Configuration

If HDMI1 is not detected, edit `/boot/config.txt`:

```bash
sudo nano /boot/config.txt
```

Add/uncomment:
```
hdmi_force_hotplug=1
hdmi_drive=1
```

For HDMI1 specifically:
```
hdmi_force_hotplug:1=1
hdmi_drive:1=1
```

### Mirror vs Extended Display

By default, Raspberry Pi mirrors HDMI outputs. For extended display:

1. Install Screen Configuration tool:
```bash
sudo apt install arandr
```

2. Or use command line:
```bash
# Set HDMI1 to the right of HDMI0
xrandr --output HDMI-1 --auto --right-of HDMI-0
```

## Troubleshooting

### Black screen on HDMI1
- Check if HDMI1 is detected: `ls /sys/class/drm/`
- Try: `export DISPLAY=:1` then `python3 main.py`

### Google Drive sync not working
- Verify folder is public (Anyone with link can view)
- Try using `gdown` manually: `gdown --folder <url> -O photos`
- Consider using rclone for better reliability

### Images not scaling correctly
- Change `scale_mode` in settings.json
- "fit" = letterbox/pillarbox
- "fill" = crop to fill

### High CPU usage
- Increase `interval_seconds` in settings
- Lower resolution images recommended (1920x1080 max)
