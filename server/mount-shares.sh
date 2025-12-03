#!/bin/bash
# Mount network shares for asset converter
# This script mounts Windows/SMB shares to local directories

set -e

CONFIG_FILE="/etc/asset-converter/path-mapping.conf"
CREDENTIALS_FILE="/etc/asset-converter/smb-credentials"
MOUNT_BASE="/mnt/shares"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo $0)"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Check if credentials file exists
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "Credentials file not found: $CREDENTIALS_FILE"
    echo "Please create it with:"
    echo "  username=YOUR_USERNAME"
    echo "  password=YOUR_PASSWORD"
    echo "  domain=YOUR_DOMAIN (optional)"
    exit 1
fi

# Create mount base directory
mkdir -p "$MOUNT_BASE"

echo "Mounting network shares..."
echo ""

# Read mount configurations from config file
# Format: //server/share|/local/mount/point
grep -v '^#' "$CONFIG_FILE" | grep -v '^$' | while IFS='|' read -r share_path mount_point; do
    # Skip empty lines
    [ -z "$share_path" ] && continue

    # Create mount point if it doesn't exist
    if [ ! -d "$mount_point" ]; then
        echo "Creating mount point: $mount_point"
        mkdir -p "$mount_point"
    fi

    # Check if already mounted
    if mountpoint -q "$mount_point"; then
        echo "Already mounted: $mount_point"
    else
        echo "Mounting: $share_path -> $mount_point"
        mount -t cifs "$share_path" "$mount_point" \
            -o credentials="$CREDENTIALS_FILE",uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0

        if [ $? -eq 0 ]; then
            echo "  ✓ Successfully mounted"
        else
            echo "  ✗ Failed to mount"
        fi
    fi
    echo ""
done

echo "Mount summary:"
df -h | grep "$MOUNT_BASE" || echo "No shares mounted"
