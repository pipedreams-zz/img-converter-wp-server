# Server Deployment Guide - Ubuntu 24 LTS

This guide explains how to deploy the WordPress Asset Converter on an Ubuntu 24 LTS server so it can run independently from your workstation.

## Overview

The server deployment includes:
- Automatic installation of all dependencies
- Network share mounting (Windows/SMB shares)
- Path translation (Windows UNC → Linux paths)
- Systemd service for auto-start
- Web interface accessible from any device on the network

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/pipedreams-zz/img-converter-wp-server.git
cd img-converter-wp-server
git checkout server-branch
```

### 2. Run the Installation Script

```bash
sudo ./server/install.sh
```

This will:
- Install system dependencies (Python, Poppler, CIFS utilities)
- Create a Python virtual environment
- Install all Python packages
- Set up configuration directories
- Install the systemd service

### 3. Configure Network Shares

Edit the SMB credentials file:

```bash
sudo nano /etc/asset-converter/smb-credentials
```

Add your credentials:

```
username=YOUR_USERNAME
password=YOUR_PASSWORD
domain=YOUR_DOMAIN
```

Secure the file:

```bash
sudo chmod 600 /etc/asset-converter/smb-credentials
```

### 4. Configure Path Mappings

Edit the path mapping configuration:

```bash
sudo nano /etc/asset-converter/path-mapping.conf
```

Add your network shares using one of two formats:

**Option 1: Drive Letter Mapping (recommended for users with mapped drives)**

Format: `DRIVE:|//server/share|/mount/point`

```
T:|//fileserver/projects|/mnt/shares/projects
P:|//nas/media|/mnt/shares/media
```

This allows users to enter paths like `T:\00005 Büroportfolio\00_Projekte\02735 WKB - Kita Beuren`

**Option 2: UNC Path Mapping**

Format: `//server/share|/mount/point`

```
//fileserver/projects|/mnt/shares/projects
//nas/media|/mnt/shares/media
//backup-server/archives|/mnt/shares/archives
```

This allows users to enter paths like `\\fileserver\projects\client-abc\images`

**You can use both formats for the same share if needed.**

### 5. Mount the Shares

```bash
sudo /usr/local/bin/mount-asset-converter-shares
```

Verify mounts:

```bash
df -h | grep /mnt/shares
```

### 6. Start the Service

Enable auto-start on boot:

```bash
sudo systemctl enable asset-converter
```

Start the service:

```bash
sudo systemctl start asset-converter
```

Check status:

```bash
sudo systemctl status asset-converter
```

### 7. Access the Web Interface

Open your browser and navigate to:

```
http://YOUR-SERVER-IP:7860
```

Replace `YOUR-SERVER-IP` with your server's IP address.

## Path Translation

The server automatically translates Windows paths to local mount points.

### Example 1: Drive Letter Mapping

If you configure this mapping:

```
T:|//fileserver/projects|/mnt/shares/projects
```

Then when a user enters:

```
T:\00005 Büroportfolio\00_Projekte\02735 WKB - Kita Beuren
```

The server translates it to:

```
/mnt/shares/projects/00005 Büroportfolio/00_Projekte/02735 WKB - Kita Beuren
```

### Example 2: UNC Path Mapping

If you configure this mapping:

```
//fileserver/projects|/mnt/shares/projects
```

Then when a user enters:

```
\\fileserver\projects\client-abc\images
```

The server translates it to:

```
/mnt/shares/projects/client-abc/images
```

### Supported Path Formats

The following formats are automatically recognized:

- **Windows mapped drives**: `T:\folder\subfolder`
- **Windows UNC with backslashes**: `\\server\share\folder`
- **Windows UNC with forward slashes**: `//server/share/folder`
- **Direct Linux paths**: `/mnt/shares/folder`

## Service Management

### Start/Stop/Restart

```bash
# Start the service
sudo systemctl start asset-converter

# Stop the service
sudo systemctl stop asset-converter

# Restart the service
sudo systemctl restart asset-converter
```

### View Logs

```bash
# View recent logs
sudo journalctl -u asset-converter -n 50

# Follow logs in real-time
sudo journalctl -u asset-converter -f

# View logs from a specific time
sudo journalctl -u asset-converter --since "1 hour ago"
```

### Check Status

```bash
sudo systemctl status asset-converter
```

### Enable/Disable Auto-Start

```bash
# Enable auto-start on boot
sudo systemctl enable asset-converter

# Disable auto-start
sudo systemctl disable asset-converter
```

## Network Share Management

### Manually Mount Shares

```bash
sudo /usr/local/bin/mount-asset-converter-shares
```

### Unmount a Share

```bash
sudo umount /mnt/shares/SHARE-NAME
```

### Unmount All Shares

```bash
sudo umount -a -t cifs
```

### Check Mounted Shares

```bash
mount | grep cifs
df -h | grep /mnt/shares
```

### Auto-Mount on Boot

To automatically mount shares on boot, add entries to `/etc/fstab`:

```bash
sudo nano /etc/fstab
```

Add lines like:

```
//fileserver/projects  /mnt/shares/projects  cifs  credentials=/etc/asset-converter/smb-credentials,uid=1000,gid=1000,file_mode=0755,dir_mode=0755,vers=3.0  0  0
```

## Troubleshooting

### Service Won't Start

Check the logs:

```bash
sudo journalctl -u asset-converter -n 100
```

Common issues:
- Python virtual environment not activated
- Missing dependencies
- Port 7860 already in use

### Path Translation Not Working

Verify path mappings:

```bash
cat /etc/asset-converter/path-mapping.conf
```

Test path translation:

```bash
cd /path/to/asset-converter-wordpress
source venv/bin/activate
python server/path_translator.py
```

### Share Won't Mount

Check credentials:

```bash
sudo cat /etc/asset-converter/smb-credentials
```

Test mount manually:

```bash
sudo mount -t cifs //server/share /mnt/shares/test \
  -o credentials=/etc/asset-converter/smb-credentials,vers=3.0
```

Common issues:
- Wrong credentials
- Network connectivity
- SMB version mismatch (try vers=2.0 or vers=1.0)
- Firewall blocking SMB ports (445, 139)

### Port Already in Use

Check what's using port 7860:

```bash
sudo lsof -i :7860
```

Kill the process or change the port in `web_gui_server.py`.

### Permissions Issues

Ensure proper ownership:

```bash
sudo chown -R YOUR_USER:YOUR_USER /path/to/asset-converter-wordpress
sudo chown YOUR_USER:YOUR_USER /mnt/shares
sudo chmod 755 /mnt/shares
```

## Firewall Configuration

If you have a firewall enabled, allow access to port 7860:

### UFW (Ubuntu Firewall)

```bash
sudo ufw allow 7860/tcp
sudo ufw reload
```

### Firewalld

```bash
sudo firewall-cmd --permanent --add-port=7860/tcp
sudo firewall-cmd --reload
```

## Security Considerations

1. **Credentials File**: Always set permissions to 600 on `/etc/asset-converter/smb-credentials`
2. **Network Access**: The web interface is accessible to anyone on the network. Consider:
   - Using a reverse proxy (nginx, Apache) with authentication
   - Restricting firewall rules to specific IP ranges
   - Using a VPN for remote access
3. **HTTPS**: For production use, set up HTTPS with a reverse proxy
4. **Updates**: Keep the system and dependencies updated:

```bash
sudo apt update && sudo apt upgrade
cd /path/to/asset-converter-wordpress
source venv/bin/activate
pip install --upgrade -r requirements.txt -r requirements-gui.txt
```

## Updating the Application

To update to the latest version:

```bash
cd /path/to/img-converter-wp-server
git pull origin server-branch
source venv/bin/activate
pip install --upgrade -r requirements.txt -r requirements-gui.txt
sudo systemctl restart asset-converter
```

## Uninstallation

To remove the service:

```bash
# Stop and disable service
sudo systemctl stop asset-converter
sudo systemctl disable asset-converter

# Remove service file
sudo rm /etc/systemd/system/asset-converter.service
sudo systemctl daemon-reload

# Remove configuration
sudo rm -rf /etc/asset-converter

# Remove mount script
sudo rm /usr/local/bin/mount-asset-converter-shares

# Unmount shares
sudo umount -a -t cifs

# Remove application (optional)
rm -rf /path/to/img-converter-wp-server
```

## Advanced Configuration

### Custom Port

Edit `web_gui_server.py` and change the `server_port` parameter in the `app.launch()` call at the bottom.

### Custom Install Location

The installer detects the installation directory automatically. If you move the application, update the systemd service:

```bash
sudo nano /etc/systemd/system/asset-converter.service
# Update WorkingDirectory and ExecStart paths
sudo systemctl daemon-reload
sudo systemctl restart asset-converter
```

### Multiple Share Groups

You can create multiple configuration files for different share groups and use environment variables or arguments to switch between them.

### Reverse Proxy (nginx)

Example nginx configuration for HTTPS and authentication:

```nginx
server {
    listen 443 ssl http2;
    server_name converter.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    auth_basic "Asset Converter";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support for Gradio
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Support

For issues, questions, or contributions, please visit the GitHub repository:
https://github.com/pipedreams-zz/img-converter-wp-server

## License

MIT License - see LICENSE file for details
