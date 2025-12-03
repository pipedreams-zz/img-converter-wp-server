#!/bin/bash
# Installation script for Ubuntu 24 LTS
# This script installs all dependencies and sets up the asset converter as a systemd service

set -e

echo "=========================================="
echo "WordPress Asset Converter - Server Setup"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./install.sh)"
    exit 1
fi

# Get the actual user who invoked sudo
ACTUAL_USER="${SUDO_USER:-$USER}"
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)

# Determine installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"

echo "Installation directory: $INSTALL_DIR"
echo "Running as user: $ACTUAL_USER"
echo ""

# Update system
echo "Updating system packages..."
apt-get update

# Install system dependencies
echo "Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    poppler-utils \
    cifs-utils \
    git

# Create virtual environment
echo "Creating Python virtual environment..."
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    sudo -u $ACTUAL_USER python3 -m venv venv
fi

# Install Python dependencies
echo "Installing Python dependencies..."
sudo -u $ACTUAL_USER bash -c "
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -r requirements-gui.txt
"

# Create mount points directory
echo "Creating mount points directory..."
mkdir -p /mnt/shares
chown $ACTUAL_USER:$ACTUAL_USER /mnt/shares

# Create configuration directory
echo "Creating configuration directory..."
mkdir -p /etc/asset-converter
cp "$SCRIPT_DIR/path-mapping.conf.example" /etc/asset-converter/path-mapping.conf
chown $ACTUAL_USER:$ACTUAL_USER /etc/asset-converter/path-mapping.conf

# Copy and enable mount script
echo "Setting up mount script..."
cp "$SCRIPT_DIR/mount-shares.sh" /usr/local/bin/mount-asset-converter-shares
chmod +x /usr/local/bin/mount-asset-converter-shares

# Copy credentials template
if [ ! -f "/etc/asset-converter/smb-credentials" ]; then
    cp "$SCRIPT_DIR/smb-credentials.example" /etc/asset-converter/smb-credentials
    chmod 600 /etc/asset-converter/smb-credentials
    echo "WARNING: Please edit /etc/asset-converter/smb-credentials with your network share credentials"
fi

# Install systemd service
echo "Installing systemd service..."
sed "s|__INSTALL_DIR__|$INSTALL_DIR|g; s|__USER__|$ACTUAL_USER|g" \
    "$SCRIPT_DIR/asset-converter.service.template" > /etc/systemd/system/asset-converter.service

# Reload systemd
systemctl daemon-reload

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit /etc/asset-converter/smb-credentials with your network credentials"
echo "2. Edit /etc/asset-converter/path-mapping.conf to map Windows paths to mount points"
echo "3. Run: sudo /usr/local/bin/mount-asset-converter-shares"
echo "4. Enable service: sudo systemctl enable asset-converter"
echo "5. Start service: sudo systemctl start asset-converter"
echo "6. Check status: sudo systemctl status asset-converter"
echo ""
echo "The web interface will be available at: http://$(hostname -I | awk '{print $1}'):7860"
echo ""
