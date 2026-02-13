#!/bin/bash
#
# SD Card Protection Installation Script for gScreen
# This script optimizes the system for long-term SD card operation
#

set -e

GSCREEN_DIR="/home/rpi4/gscreen"
USER="rpi4"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Please run as root (use sudo)"
        exit 1
    fi
}

setup_tmpfs() {
    log_info "Setting up RAM disks (tmpfs) for logs and cache..."
    
    # Create RAM directories
    mkdir -p /dev/shm/gscreen_logs
    mkdir -p /dev/shm/gscreen_cache
    chown $USER:$USER /dev/shm/gscreen_logs
    chown $USER:$USER /dev/shm/gscreen_cache
    chmod 755 /dev/shm/gscreen_logs
    chmod 755 /dev/shm/gscreen_cache
    
    # Add to fstab for persistence across reboots
    if ! grep -q "/dev/shm/gscreen_logs" /etc/fstab; then
        log_info "Adding tmpfs entries to /etc/fstab..."
        echo "tmpfs /dev/shm/gscreen_logs tmpfs defaults,noatime,nosuid,size=50m,uid=$USER,gid=$USER,mode=0755 0 0" >> /etc/fstab
        echo "tmpfs /dev/shm/gscreen_cache tmpfs defaults,noatime,nosuid,size=200m,uid=$USER,gid=$USER,mode=0755 0 0" >> /etc/fstab
    fi
    
    log_info "RAM disks configured: 50MB for logs, 200MB for cache"
}

optimize_journald() {
    log_info "Optimizing systemd journald for SD card protection..."
    
    mkdir -p /etc/systemd/journald.conf.d
    
    cat > /etc/systemd/journald.conf.d/gscreen.conf <<EOF
[Journal]
# Store journal in RAM (volatile)
Storage=volatile

# Limit memory usage
SystemMaxUse=50M
SystemMaxFileSize=10M
MaxFileSec=3day

# Compress to save space
Compress=yes
EOF

    systemctl restart systemd-journald
    log_info "Journald optimized: logs stored in RAM, max 50MB"
}

optimize_syslog() {
    log_info "Disabling rsyslog (using journald instead)..."
    
    if systemctl is-active --quiet rsyslog; then
        systemctl stop rsyslog
        systemctl disable rsyslog
        log_info "rsyslog disabled"
    fi
    
    # Also disable other logging services
    for service in syslogd klogd; do
        if systemctl is-enabled $service 2>/dev/null; then
            systemctl disable $service 2>/dev/null || true
            log_info "Disabled $service"
        fi
    done
}

setup_logrotate() {
    log_info "Setting up logrotate for minimal SD card writes..."
    
    cat > /etc/logrotate.d/gscreen <<EOF
/dev/shm/gscreen_logs/*.log {
    daily
    rotate 3
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    size 5M
}
EOF
    
    log_info "Logrotate configured for RAM logs"
}

create_health_monitor() {
    log_info "Creating SD card health monitor..."
    
    cat > $GSCREEN_DIR/check_sd_health.sh <<'SCRIPT'
#!/bin/bash
# SD Card Health Monitor for gScreen

LOG_FILE="/dev/shm/gscreen_logs/sd_health.log"
ALERT_THRESHOLD=80

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check disk space
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USAGE" -gt "$ALERT_THRESHOLD" ]; then
    log "WARNING: Disk usage is ${DISK_USAGE}%"
else
    log "INFO: Disk usage is ${DISK_USAGE}%"
fi

# Check SD card wear level (if available)
for dev in /sys/bus/mmc/devices/*; do
    if [ -f "$dev/life_time" ]; then
        WEAR=$(cat "$dev/life_time")
        WEAR_PERCENT=$((0x$WEAR * 10))
        if [ "$WEAR_PERCENT" -gt "$ALERT_THRESHOLD" ]; then
            log "WARNING: SD card wear level is ${WEAR_PERCENT}%"
        else
            log "INFO: SD card wear level is ${WEAR_PERCENT}%"
        fi
    fi
done

# Check for I/O errors
IO_ERRORS=$(dmesg | grep -c "I/O error" || echo "0")
if [ "$IO_ERRORS" -gt 0 ]; then
    log "WARNING: Found $IO_ERRORS I/O errors since boot"
fi

# Check temperature (if available)
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
    TEMP_C=$((TEMP / 1000))
    if [ "$TEMP_C" -gt 70 ]; then
        log "WARNING: CPU temperature is ${TEMP_C}°C"
    else
        log "INFO: CPU temperature is ${TEMP_C}°C"
    fi
fi

# Check memory usage
MEM_AVAILABLE=$(free | awk 'NR==2{print $7}')
MEM_TOTAL=$(free | awk 'NR==2{print $2}')
MEM_PERCENT=$((100 - (MEM_AVAILABLE * 100 / MEM_TOTAL)))
log "INFO: Memory usage is ${MEM_PERCENT}%"

# Show write statistics (if iostat available)
if command -v iostat &> /dev/null; then
    DISK_WRITE=$(iostat -d 1 1 | grep mmcblk | awk '{print $4}' | tail -1)
    if [ -n "$DISK_WRITE" ]; then
        log "INFO: Current disk write rate: ${DISK_WRITE} KB/s"
    fi
fi
SCRIPT

    chmod +x $GSCREEN_DIR/check_sd_health.sh
    chown $USER:$USER $GSCREEN_DIR/check_sd_health.sh
    
    log_info "Health monitor created at $GSCREEN_DIR/check_sd_health.sh"
}

setup_cron() {
    log_info "Setting up automatic health checks..."
    
    # Create cron job for health checks
    CRON_CONTENT="# gScreen SD Card Health Check
0 */6 * * * $GSCREEN_DIR/check_sd_health.sh >/dev/null 2>&1
# Weekly reboot to clear memory and refresh system
0 3 * * 0 /sbin/reboot
"
    
    echo "$CRON_CONTENT" | crontab -u $USER -
    
    log_info "Cron jobs configured: health check every 6 hours, weekly reboot"
}

install_systemd_service() {
    log_info "Installing optimized systemd service..."
    
    if [ -f "$GSCREEN_DIR/gscreen-protected.service" ]; then
        cp "$GSCREEN_DIR/gscreen-protected.service" /etc/systemd/system/gscreen.service
        systemctl daemon-reload
        log_info "Systemd service installed"
    else
        log_warn "gscreen-protected.service not found, skipping"
    fi
}

update_settings() {
    log_info "Updating settings for SD card protection..."
    
    if [ -f "$GSCREEN_DIR/settings.json" ]; then
        # Backup original
        cp "$GSCREEN_DIR/settings.json" "$GSCREEN_DIR/settings.json.backup"
        
        # Update settings if using jq
        if command -v jq &> /dev/null; then
            # Update sync and add system settings for SD card protection
            jq '.sync.check_interval_minutes = 60 |
                .sync.local_cache_dir = "/dev/shm/gscreen_cache" |
                .system = {
                    "_comment": "System-level settings for SD card protection and maintenance",
                    "weekly_auto_restart": true,
                    "weekly_restart_day": 0,
                    
                    "log_to_ram": false,
                    "ram_log_size_mb": 50,
                    "enable_health_monitoring": true,
                    "health_check_interval_hours": 6
                }' \
               "$GSCREEN_DIR/settings.json" > "$GSCREEN_DIR/settings.json.new"
            mv "$GSCREEN_DIR/settings.json.new" "$GSCREEN_DIR/settings.json"
            log_info "Settings updated with SD card protection config"
            log_info "  - Sync interval: 60 minutes"
            log_info "  - Cache: RAM (/dev/shm/gscreen_cache)"
            log_info "  - Weekly auto-restart: enabled (Sunday 03:00)"
            log_info "  - Log to RAM: disabled (logs to stdout only)"
        else
            log_warn "jq not installed, please manually update settings.json"
            echo ""
            echo "Add the following to your settings.json:"
            echo '"system": {'
            echo '    "weekly_auto_restart": true,'
            echo '    "weekly_restart_day": 0,'
            echo '    '
            echo '    "log_to_ram": false,'
            echo '    "ram_log_size_mb": 50,'
            echo '    "enable_health_monitoring": true,'
            echo '    "health_check_interval_hours": 6'
            echo '}'
        fi
    fi
}

disable_swap() {
    log_info "Checking swap configuration..."
    
    # Check if using swap on SD card
    if [ -f /var/swap ]; then
        log_warn "Swap file detected on SD card"
        # Option to disable or move to USB
        read -p "Disable swap? (recommended for SD card) [Y/n]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            dphys-swapfile swapoff
            dphys-swapfile uninstall
            update-rc.d dphys-swapfile disable
            log_info "Swap disabled"
        fi
    fi
}

install_iostat() {
    log_info "Installing iostat for disk monitoring..."
    apt-get update -qq
    apt-get install -y -qq sysstat
    
    # Enable sysstat data collection
    sed -i 's/ENABLED="false"/ENABLED="true"/' /etc/default/sysstat
    systemctl restart sysstat
}

create_readonly_mode() {
    log_info "Creating read-only mode script..."
    
    cat > $GSCREEN_DIR/readonly_mode.sh <<'SCRIPT'
#!/bin/bash
# Switch system to read-only mode (for maximum SD card protection)

set -e

echo "Switching to read-only mode..."

# Remount filesystems as read-only
mount -o remount,ro /
mount -o remount,ro /boot

# Note: This is experimental and may cause issues
echo "System is now in read-only mode"
echo "To return to read-write mode, run: mount -o remount,rw /"
SCRIPT

    chmod +x $GSCREEN_DIR/readonly_mode.sh
    log_info "Read-only mode script created (experimental)"
}

show_summary() {
    echo
    echo "=========================================="
    echo "    SD Card Protection Setup Complete"
    echo "=========================================="
    echo
    echo "Changes made:"
    echo "  ✓ RAM disks configured for logs and cache"
    echo "  ✓ Journald optimized (logs in RAM)"
    echo "  ✓ Rsyslog disabled (redundant with journald)"
    echo "  ✓ Logrotate configured"
    echo "  ✓ Health monitoring enabled"
    echo "  ✓ Weekly auto-reboot scheduled"
    echo "  ✓ Systemd service installed"
    echo
    echo "Important paths:"
    echo "  - Logs: /dev/shm/gscreen_logs/"
    echo "  - Cache: /dev/shm/gscreen_cache/"
    echo "  - Health log: /dev/shm/gscreen_logs/sd_health.log"
    echo
    echo "Commands:"
    echo "  - Check health: $GSCREEN_DIR/check_sd_health.sh"
    echo "  - View logs: journalctl -u gscreen -f"
    echo "  - View status: systemctl status gscreen"
    echo
    echo "Next steps:"
    echo "  1. Reboot the system: sudo reboot"
    echo "  2. Check service status: systemctl status gscreen"
    echo "  3. Monitor health: tail -f /dev/shm/gscreen_logs/sd_health.log"
    echo
    echo "Recommended: Use an industrial-grade SD card for best longevity"
    echo
}

main() {
    log_info "Starting SD Card Protection Setup..."
    
    check_root
    
    # Install required packages
    apt-get update -qq
    apt-get install -y -qq sysstat
    
    setup_tmpfs
    optimize_journald
    optimize_syslog
    setup_logrotate
    create_health_monitor
    setup_cron
    install_systemd_service
    update_settings
    disable_swap
    install_iostat
    create_readonly_mode
    
    show_summary
}

# Run main function
main "$@"
