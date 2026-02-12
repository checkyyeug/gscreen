#!/bin/bash
# Installation script for gScreen on Raspberry Pi

set -e

INSTALL_DIR=$(pwd)
VENV_DIR="$INSTALL_DIR/venv"

echo "========================================="
echo "gScreen Installation Script"
echo "========================================="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Install with: sudo apt install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "Found Python $PYTHON_VERSION"

# Detect if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    MODEL=$(tr -d '\0' < /proc/device-tree/model)
    echo "Detected: $MODEL"
fi

# Update system packages
echo ""
echo "Updating system packages..."
sudo apt update

# Install system dependencies
echo ""
echo "Installing system dependencies..."
sudo apt install -y \
    python3-full \
    python3-venv \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    libportmidi-dev \
    libgtk-3-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libatlas-base-dev \
    ffmpeg \
    git

# Create virtual environment
echo ""
echo "Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

# Activate venv and install packages
echo ""
echo "Installing Python packages..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# Create wrapper scripts for easy use
echo ""
echo "Creating wrapper scripts..."

# Create run script
cat > "$INSTALL_DIR/run.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/main.py" "$@"
EOF
chmod +x "$INSTALL_DIR/run.sh"

# Create sync-only script
cat > "$INSTALL_DIR/sync.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
source "$SCRIPT_DIR/venv/bin/activate"
python3 "$SCRIPT_DIR/main.py" --sync-only
EOF
chmod +x "$INSTALL_DIR/sync.sh"

# Add user to video group for framebuffer access
echo ""
echo "Adding user to video group (required for display access)..."
if ! groups $USER | grep -q '\bvideo\b'; then
    sudo usermod -a -G video $USER
    echo "User $USER added to video group"
    echo "** IMPORTANT: Log out and log back in for this change to take effect **"
else
    echo "User $USER is already in video group"
fi

# Optional: Install rclone for better Google Drive sync
echo ""
read -p "Install rclone for improved Google Drive sync? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo apt install -y rclone
    echo "rclone installed. Configure with: rclone config"
fi

# Make Python scripts executable
chmod +x main.py
chmod +x slideshow.py
chmod +x gdrive_sync.py
chmod +x download.py

# Create media directory
mkdir -p media

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "Display mode will be auto-detected:"
echo "  - With desktop: Uses X11"
echo "  - Without desktop: Uses framebuffer (fbcon)"
echo ""
echo "Features installed:"
echo "  - Image and video playback (via pygame/OpenCV)"
echo "  - Audio support for videos (via ffplay)"
echo "  - Google Drive sync"
echo ""
echo "To run gScreen:"
echo "  ./run.sh"
echo ""
echo "To sync only:"
echo "  ./sync.sh"
echo ""
echo "Next steps:"
echo "1. Log out and log back in (for video group)"
echo "2. Edit settings.json and add your Google Drive URL"
echo "3. (Optional) Enable audio in settings.json: audio.enabled = true"
echo "4. Run: ./run.sh"
echo ""
