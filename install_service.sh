#!/bin/bash
# Systemd service installer for gScreen

set -e

SERVICE_NAME="gscreen"
INSTALL_DIR=$(pwd)
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_DIR="$INSTALL_DIR/venv"

echo "========================================="
echo "gScreen Service Installer"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo ./install_service.sh"
    exit 1
fi

# Get the username of the calling user
REAL_USER=${SUDO_USER:-$USER}
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo "Installing service for user: $REAL_USER"
echo "Installation directory: $INSTALL_DIR"
echo ""

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "WARNING: Virtual environment not found at $VENV_DIR"
    echo "Please run ./install.sh first!"
    exit 1
fi

# Create systemd service file
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=gScreen - Google Drive Photo Slideshow
After=network-online.target graphical.target
Wants=network-online.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="DISPLAY=:1"
Environment="SDL_VIDEO_FULLSCREEN_HEAD=1"
Environment="PATH=$VENV_DIR/bin:/usr/bin"
ExecStart=$VENV_DIR/bin/python3 $INSTALL_DIR/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=false
ReadWritePaths=$INSTALL_DIR/photos $INSTALL_DIR/venv

[Install]
WantedBy=multi-user.target
EOF

echo "Created service file: $SERVICE_FILE"

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable service (but don't start it yet)
echo ""
echo "Enabling service..."
systemctl enable "$SERVICE_NAME"

echo ""
echo "========================================="
echo "Service installation complete!"
echo "========================================="
echo ""
echo "Commands:"
echo "  Start service:  sudo systemctl start $SERVICE_NAME"
echo "  Stop service:   sudo systemctl stop $SERVICE_NAME"
echo "  Check status:   sudo systemctl status $SERVICE_NAME"
echo "  View logs:      sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "The service will start automatically on boot."
echo ""
read -p "Start the service now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl start "$SERVICE_NAME"
    echo "Service started!"
fi
