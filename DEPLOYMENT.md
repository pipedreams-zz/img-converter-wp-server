# Deployment Options

This document describes the two deployment modes for the WordPress Asset Converter.

## Workstation Deployment (Default)

**Best for**: Local use, development, or single-user scenarios

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR-USERNAME/asset-converter-wordpress.git
   cd asset-converter-wordpress
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt -r requirements-gui.txt
   ```

3. Run the web interface:
   ```bash
   python web_gui.py
   ```

The interface will open in your browser at `http://localhost:7860`.

### Features

- **Local file access**: Direct access to your workstation's file system
- **Folder picker**: Browse button opens native folder dialogs
- **Simple setup**: No configuration required
- **Auto-open browser**: Automatically opens in your default browser

---

## Server Deployment (Ubuntu 24 LTS)

**Best for**: Team use, running independently from workstation, network access

### Key Features

- **Independent operation**: Runs 24/7 on a server
- **Network shares**: Mount and access Windows/SMB network shares
- **Path translation**: Automatically translate Windows UNC paths to Linux paths
- **Auto-start**: Systemd service starts on boot
- **Multi-user**: Accessible from any device on the network
- **Remote access**: Web interface available at `http://server-ip:7860`

### Architecture

```
User's Workstation                    Ubuntu Server
─────────────────                     ─────────────

Browser                               Web GUI (Port 7860)
  │                                         │
  └─── http://server-ip:7860 ───────────>  │
                                            │
  User enters:                              │
  \\server\share\folder ──────────────> Path Translator
                                            │
                                      Converts to:
                                      /mnt/shares/folder
                                            │
                                            ▼
Windows Network Share              Mounted Share
─────────────────────              ─────────────
//fileserver/projects ────────> /mnt/shares/projects
                    (CIFS/SMB)           (Local)
                                            │
                                            ▼
                                   Batch Converter
                                            │
                                            ▼
                                   Converted Images
```

### Quick Start

```bash
# Clone and switch to server branch
git clone https://github.com/YOUR-USERNAME/asset-converter-wordpress.git
cd asset-converter-wordpress
git checkout server-branch

# Run installation
sudo ./server/install.sh

# Configure credentials
sudo nano /etc/asset-converter/smb-credentials

# Configure path mappings
sudo nano /etc/asset-converter/path-mapping.conf

# Mount shares
sudo /usr/local/bin/mount-asset-converter-shares

# Start service
sudo systemctl enable --now asset-converter

# Check status
sudo systemctl status asset-converter
```

### Detailed Documentation

See [server/README.md](server/README.md) for:
- Complete installation guide
- Configuration examples
- Troubleshooting
- Security considerations
- Advanced setups

---

## Comparison

| Feature | Workstation | Server |
|---------|-------------|--------|
| **Setup Complexity** | Simple | Moderate |
| **Dependencies** | Python, pip | Python, Poppler, CIFS utilities |
| **Configuration** | None | Credentials, path mappings |
| **Access** | Local only | Network-wide |
| **Availability** | When workstation runs | 24/7 |
| **File Access** | Local files | Network shares + local |
| **Path Format** | Local paths | Windows UNC or Linux paths |
| **Auto-start** | No | Yes (systemd) |
| **Multi-user** | No | Yes |
| **Best for** | Personal use | Team use |

---

## Choosing Your Deployment

### Use Workstation Deployment if:
- You're the only user
- You work with local files
- You don't need 24/7 availability
- You want the simplest setup

### Use Server Deployment if:
- Multiple people need access
- Files are on network shares
- You need 24/7 availability
- You want to offload processing from your workstation
- You have an Ubuntu server available

---

## Switching Between Deployments

### From Workstation to Server

1. Set up the server following [server/README.md](server/README.md)
2. Continue using your workstation setup locally if needed
3. Both can coexist independently

### From Server to Workstation

1. Clone the repository on your workstation
2. Use the `main` branch instead of `server-branch`
3. Run `python web_gui.py`

---

## Support

For deployment issues:
- Workstation: See main [README.md](README.md)
- Server: See [server/README.md](server/README.md)
- GitHub Issues: https://github.com/YOUR-USERNAME/asset-converter-wordpress/issues
